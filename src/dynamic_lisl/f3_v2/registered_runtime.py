"""Build existing v2 components from explicitly approved, hash-bound inputs.

No engineering witness source is available here. A newly approved diversity or
scouting policy must first get its implementation and acceptance; unsupported
policy is rejected rather than silently substituted.
"""
import json
import multiprocessing
from pathlib import Path
from .matrix_execution import SUPPORTED_SOURCE_POLICY, validate_inherited_runtime_parameters


def create_runtime(root, manifest, run):
    # Only the validated registered entry uses this factory. It contains no
    # independent authorization, simulation kernel, controller or traffic rule.
    from ..terminal_executor import TerminalExecutor, Connect, pair
    from ..terminal_pair_intervals import TerminalPairCatalog
    from ..gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
    from ..commodity import Commodity
    from ..traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
    from ..common_router import DeterministicShortestPropagationDelayRouter
    from ..load_aware_router import DeterministicLoadAwareRouter
    from ..sgp4_model import Sgp4Model
    from ..gate_e2_experiments import E2Sgp4EdgeDelayProvider
    from ..operational_policy import OperationalPolicy
    from .natural_engine import NaturalGeometryBatchEngine
    from .batch_executor import BatchPhysicalValidator, BatchSafetyValidator
    from .service_adapter import DecisionSchedule
    from .joint_proposer import JointSearchBudget, BoundedJointProposer
    from .candidate_source import RawCandidateBudget, replacement_inventory
    from .epoch_validation import validate_epoch_inputs
    from .snapshot_controllers import StaticBatchController, SnapshotBatchController
    from .batch_rollout import JointRolloutController, PersistentBatchBranchPool
    root = Path(root).resolve()
    config = manifest['runtime_configuration']
    if config['source_policy'] != SUPPORTED_SOURCE_POLICY:
        raise ValueError('APPROVED_CANDIDATE_POLICY_IMPLEMENTATION_REQUIRED')
    validate_inherited_runtime_parameters(root, config)
    read = lambda path: json.loads((root / path).read_text(encoding='utf-8'))
    topology = read(run['topology_artifact'])
    fixed = tuple(tuple(e) for e in topology['fixed_edges'])
    nodes = tuple(sorted({n for e in fixed for n in e}))
    mapping = {n: int(n.split('_')[0][1:]) for n in nodes}
    if len(nodes) != 160 or set(mapping.values()) != set(range(4)) or any(
            sum(p == plane for p in mapping.values()) != 40 for plane in range(4)):
        raise ValueError('REGISTERED_NATURAL_160_FOUR_PLANE_SCENE_REQUIRED')
    records = [json.loads(line) for line in (root / config['physical_windows_path']).read_text(encoding='utf-8').splitlines()]
    physical = TerminalPairPhysicalFeasibility(TerminalPairCatalog.from_records(records, mapping))
    hardware = read(config['hardware_path'])['audit_setup_fixture']
    setup = {k: hardware[k] for k in ('retarget_a_s', 'retarget_b_s', 'acquisition_s')}
    executor = TerminalExecutor(nodes)
    bindings = []
    commands = []
    for row in topology['bindings']:
        endpoints = pair(tuple(row['a']), tuple(row['b'])) if isinstance(row, dict) else pair(*row)
        if mapping[endpoints[0][0]] == mapping[endpoints[1][0]]:
            raise ValueError('INITIAL_DYNAMIC_BINDING_NOT_INTER_PLANE')
        p = physical.evaluate(executor, *endpoints, retarget_a=setup['retarget_a_s'],
            retarget_b=setup['retarget_b_s'], acquisition=setup['acquisition_s'])
        if not p['accepted']:
            raise ValueError('INITIAL_FORWARD_GATE_C_REJECT:' + p['reason'])
        end = p['geometry']['window']['end_s']
        if isinstance(row, dict) and row['end_s'] != end:
            raise ValueError('INITIAL_BINDING_WINDOW_NOT_BOUND_TO_GATE_C')
        bindings.append(endpoints)
        commands.append(Connect(*endpoints, end, 0., 0., 0.))
    if len(bindings) != run['K']:
        raise ValueError('INITIAL_EXACT_K_MISMATCH')
    if run['topology_regime'] == 'K4_HISTORICAL_REFERENCE':
        # Preserve the historical K4 pre-establishment event sequence exactly.
        for command in commands:
            executor.submit((command,))
    else:
        # Same all-command initialization as the K1 candidate constructor.
        executor.submit(commands)
    executor.assert_invariants()
    from .structural import graph_structure
    if not graph_structure(nodes, fixed, bindings)['connected']:
        raise ValueError('INITIAL_REGISTERED_GRAPH_DISCONNECTED')
    d0 = read(config['D0_contract_path'])
    traffic = read(run['traffic_asset'])
    od = read(config['OD_manifest_path'])
    commodities = tuple(Commodity.from_dict(row) for row in od['commodities'])
    if len(commodities) != 16:
        raise ValueError('FROZEN_16_OD_TRAFFIC_REQUIRED')
    trace = PiecewiseConstantTrafficTrace(tuple(c.commodity_id for c in commodities), tuple(
        TrafficSegment(row['start_s'], row['end_s'], {c.commodity_id:
            run['rho'] * traffic['alpha_star_bit_s'] * row['g'][c.commodity_id] for c in commodities}, row['label'])
        for row in traffic['segments']))
    if trace.arrival_horizon_s != 240:
        raise ValueError('REGISTERED_TRAFFIC_ARRIVAL_WINDOW_MISMATCH')
    if run['router'] == 'SHORTEST_PROPAGATION_DELAY':
        router = DeterministicShortestPropagationDelayRouter()
    elif run['router'] == 'CURRENT_STATE_LOAD_AWARE':
        router = DeterministicLoadAwareRouter(**config['load_aware_router_parameters'])
    else:
        raise ValueError('UNREGISTERED_COMMON_ROUTER')
    engine = NaturalGeometryBatchEngine(nodes, fixed, d0['link_capacity_bit_s_per_direction'], commodities,
        trace, E2Sgp4EdgeDelayProvider(Sgp4Model.load(root / config['sgp4_asset_folder']), nodes), executor,
        router=router, absolute_time_frame_id=config['frame_id'],
        conservation_abs_tolerance_bits=d0['conservation_abs_tolerance_bits'],
        conservation_relative_tolerance=d0['conservation_relative_tolerance'], state_tolerance_bits=d0['state_tolerance_bits'])
    validator = BatchSafetyValidator(BatchPhysicalValidator(physical, max_batch_replace=run['max_batch_replace'],
        observation_end_s=600, absolute_time_frame_id=config['frame_id']), fixed, OperationalPolicy(config['safety_mode']))
    budget = JointSearchBudget(**config['search_budget_by_batch'][str(run['max_batch_replace'])])
    proposer = BoundedJointProposer(validator, budget)
    raw_budget = RawCandidateBudget(**config['raw_budget'])
    def source(live, _validator):
        if run['controller'] == 'B0-v2':
            return (), {'role': 'STATIC_NO_CANDIDATE_SEARCH', 'performance_input_read': False}
        result = replacement_inventory(live.executor, physical, plane_by_satellite=mapping,
            **setup, observation_end_s=600, raw_budget=raw_budget)
        return result['members'], result['audit']
    children_before = {p.pid for p in multiprocessing.active_children()}
    pool = None
    if run['controller'] == 'B0-v2':
        controller = StaticBatchController()
    elif run['controller'] == 'B4-v2':
        pool = PersistentBatchBranchPool(worker_count=config['worker_count'],
            sgp4_asset_folder=str(root / config['sgp4_asset_folder']))
        controller = JointRolloutController(validator, rollout_cap=budget.rollout_cap, branch_pool=pool)
    elif run['controller'] == 'B2-v2':
        controller = SnapshotBatchController('B2-v2', minimum_hold_s=run['minimum_hold_s'],
            initial_age_s=config['B2_initial_age_s'], initial_bindings=bindings)
    else:
        controller = SnapshotBatchController(run['controller'],
            eta_aggregation=config['B3_eta_aggregation'] if run['controller'] == 'B3-v2' else None)
    def cleanup():
        if pool is not None:
            pool.shutdown()
        if {p.pid for p in multiprocessing.active_children()} - children_before:
            raise AssertionError('REGISTERED_RUNTIME_ORPHAN_WORKER')
    provenance = manifest['result_provenance'][run['run_id']]
    return {'engine': engine, 'validator': validator,
        'schedule': DecisionSchedule(run['decision_cadence_s'], 240, 600,
            run['rollout_horizon_nominal_s'], .01, config['clip_horizon_at_end']),
        'source': source, 'proposer': proposer, 'controller': controller,
        'input_hashes': provenance['inputs'], 'code_hashes': provenance['code'],
        'capacity_tolerance_bit_s': config['capacity_tolerance_bit_s'], 'cleanup': cleanup,
        'epoch_audit_validator': lambda live, pool, audit: validate_epoch_inputs(live, pool, audit,
            raw_budget=raw_budget, search_budget=budget)}
