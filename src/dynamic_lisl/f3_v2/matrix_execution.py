"""Ordered matrix execution and failure-first sealing on the shared episode loop.

Engineering fixture orchestration is explicit and cannot authorize registered
runs. The formal entry validates frozen inputs/evidence/human authority before
constructing any engine. No result-based candidate or run selection exists.
"""
from pathlib import Path
import json
import math
from .episode_execution import execute_episode
from .evidence import file_sha256, write_new_json, engine_invariants, persist_run_evidence
from .joint_action import canonical_sha256
from .preflight import checked_file, positive_number, validate_preflight
from .result_analysis import load_sealed_registered_results, analyze_registered_results


SCIENCE_FIELDS = ('controller', 'scale', 'rho', 'topology_regime', 'router', 'traffic',
    'traffic_asset', 'decision_cadence_s', 'max_batch_replace', 'rollout_horizon_nominal_s',
    'minimum_hold_s', 'hysteresis_threshold')
SUPPORTED_SOURCE_POLICY = 'UNCAPPED_PHYSICAL_SCAN_THEN_STRATIFIED_OUTPUT_CAPS_V1'
REQUIRED_RUNTIME_FIELDS = {'frame_id', 'physical_windows_path', 'hardware_path', 'D0_contract_path',
    'OD_manifest_path', 'sgp4_asset_folder', 'sgp4_asset_paths', 'safety_mode', 'source_policy',
    'raw_budget', 'search_budget_by_batch', 'B3_eta_aggregation', 'B2_initial_age_s',
    'initialization_convention', 'capacity_tolerance_bit_s', 'clip_horizon_at_end',
    'load_aware_router_parameters', 'worker_count'}

FROZEN_ROUTER_MANIFEST = 'configs/gate_e0_sweep_manifest.json'


def validate_inherited_runtime_parameters(root, config):
    """Inherited numerical/router choices, never a new v2 tuning authority."""
    root = Path(root)
    d0 = json.loads((root / config['D0_contract_path']).read_text(encoding='utf-8'))
    inherited_capacity_limit = max(1e-9, d0['link_capacity_bit_s_per_direction'] * 1e-12)
    if config['capacity_tolerance_bit_s'] != inherited_capacity_limit:
        raise ValueError('INHERITED_CAPACITY_TOLERANCE_MISMATCH')
    parent = json.loads((root / FROZEN_ROUTER_MANIFEST).read_text(encoding='utf-8'))
    robustness = parent['routing_configs']['robustness']
    from ..load_aware_router import DeterministicLoadAwareRouter
    expected = {k: robustness[k] for k in ('utilization_penalty_s', 'queue_penalty_s', 'queue_scale_bits')}
    expected['time_tolerance_s'] = DeterministicLoadAwareRouter().time_tolerance_s
    if config['load_aware_router_parameters'] != expected:
        raise ValueError('INHERITED_COMMON_ROUTER_PARAMETERS_MISMATCH')


def validate_registered_request(root, *, manifest, science_contract, k0_report, k1_report,
                                engineering_report, runtime_budget, authorization):
    """Stronger entry validation than the general preflight's report status alone."""
    root = Path(root).resolve()
    gate = validate_preflight(root, manifest, science_contract, k0_report, k1_report,
        engineering_report, runtime_budget, authorization)
    if gate['status'] != 'READY':
        raise ValueError('REGISTERED_PREFLIGHT_NOT_READY:' + ','.join(gate['blockers']))
    detached = {}
    for key, document in (('science_contract_path', science_contract), ('authorization_path', authorization),
                          ('execution_manifest_path', manifest)):
        relative = manifest.get(key)
        if (not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts
            or not (root / relative).resolve().is_relative_to(root)
            or not (root / relative).is_file()
            or json.loads((root / relative).read_text(encoding='utf-8')) != document):
            raise ValueError('EXACT_ON_DISK_AUTHORITY_REQUIRED:' + key)
        if key == 'science_contract_path':
            if not checked_file(root, relative, manifest['file_hashes'].get(relative)):
                raise ValueError('SCIENTIFIC_AUTHORITY_NOT_PINNED')
        else:
            if relative in manifest['file_hashes']:
                raise ValueError('CIRCULAR_MANIFEST_AUTHORIZATION_HASH_BINDING')
            detached[relative] = file_sha256(root / relative)
    source_path = manifest.get('source_matrix_path')
    hashes = manifest['file_hashes']
    if not checked_file(root, source_path, hashes.get(source_path)):
        raise ValueError('PINNED_ORIGINAL_MATRIX_REQUIRED')
    original = json.loads((root / source_path).read_text(encoding='utf-8'))
    unsigned = {k: v for k, v in original.items() if k != 'draft_canonical_sha256'}
    if (original.get('target_run_count') != 42 or original.get('status') != 'DRAFT_NOT_FROZEN'
        or original.get('draft_canonical_sha256') != canonical_sha256(unsigned)):
        raise ValueError('ORIGINAL_42_RUN_DRAFT_REQUIRED')
    runs = manifest['runs']
    if ([r.get('run_id') for r in runs] != [r['run_id'] for r in original['runs']]
        or [r.get('execution_order') for r in runs] != list(range(1, 43))):
        raise ValueError('REGISTERED_42_IDS_OR_ORDER_MISMATCH')
    for run, parent in zip(runs, original['runs']):
        if any(run.get(k) != parent.get(k) for k in SCIENCE_FIELDS):
            raise ValueError('REGISTERED_MATRIX_SCIENTIFIC_CONFIG_DRIFT:' + run['run_id'])
        if run['topology_regime'] == 'K4_HISTORICAL_REFERENCE':
            if run['topology_artifact'] != parent['topology_artifact']:
                raise ValueError('HISTORICAL_K4_ARTIFACT_SUBSTITUTION')
        elif (run['topology_artifact'] != k1_report.get('topology_artifact')
              or manifest['file_hashes'].get(run['topology_artifact']) != k1_report.get('topology_sha256')):
            raise ValueError('REGISTERED_K_STAR_NOT_BOUND_TO_K1_ARTIFACT')
        if (not positive_number(run['runtime_budget'].get('approved_operational_timeout_s'))
            or run['runtime_budget']['approved_operational_timeout_s'] < run['runtime_budget']['estimated_wall_clock_s']):
            raise ValueError('APPROVED_PER_RUN_OPERATIONAL_LIMIT_REQUIRED')
    if (manifest.get('contrasts') != original['contrasts']
        or manifest.get('registered_opening_figure_proposal') != original['registered_opening_figure_proposal']):
        raise ValueError('REGISTERED_ANALYSIS_OR_OPENING_CASE_DRIFT')
    config = manifest.get('runtime_configuration', {})
    if set(config) != REQUIRED_RUNTIME_FIELDS:
        raise ValueError('EXACT_EXPLICIT_RUNTIME_SCHEMA_REQUIRED')
    config_hash = canonical_sha256(config)
    if (science_contract.get('runtime_configuration_canonical_sha256') != config_hash
        or engineering_report.get('runtime_configuration_canonical_sha256') != config_hash):
        raise ValueError('RUNTIME_NOT_BOUND_TO_SCIENCE_AND_CURRENT_ACCEPTANCE')
    if config['source_policy'] != SUPPORTED_SOURCE_POLICY:
        raise ValueError('APPROVED_CANDIDATE_POLICY_IMPLEMENTATION_REQUIRED')
    if (config['worker_count'] != 8 or config['safety_mode'] != 'STRICT_CONNECTED'
        or config['B3_eta_aggregation'] != 'min' or config['clip_horizon_at_end'] is not True
        or config['initialization_convention'] != 'PREESTABLISHED_AT_ZERO_WITH_FORWARD_GATE_C_CERTIFICATE'):
        raise ValueError('EXPLICIT_IMPLEMENTED_RUNTIME_SEMANTICS_REQUIRED')
    if type(config['B2_initial_age_s']) not in (int, float) or config['B2_initial_age_s'] < 0:
        raise ValueError('EXPLICIT_B2_INITIAL_AGE_REQUIRED')
    if (not math.isfinite(config['B2_initial_age_s'])
        or type(config['capacity_tolerance_bit_s']) not in (int, float)
        or not math.isfinite(config['capacity_tolerance_bit_s']) or config['capacity_tolerance_bit_s'] < 0):
        raise ValueError('FINITE_EXPLICIT_RUNTIME_LIMITS_REQUIRED')
    router_keys = {'utilization_penalty_s', 'queue_penalty_s', 'queue_scale_bits', 'time_tolerance_s'}
    if set(config['load_aware_router_parameters']) != router_keys:
        raise ValueError('EXPLICIT_FROZEN_COMMON_ROUTER_PARAMETERS_REQUIRED')
    if not isinstance(config['frame_id'], str) or not config['frame_id']:
        raise ValueError('EXPLICIT_ABSOLUTE_FRAME_REQUIRED')
    from .candidate_source import RawCandidateBudget
    from .joint_proposer import JointSearchBudget
    RawCandidateBudget(**config['raw_budget'])
    if set(config['search_budget_by_batch']) != {'1', '4'}:
        raise ValueError('EXPLICIT_BATCH1_AND_BATCH4_BUDGETS_REQUIRED')
    for size, values in config['search_budget_by_batch'].items():
        budget = JointSearchBudget(**values)
        if budget.max_members != int(size):
            raise ValueError('SEARCH_BUDGET_ACTION_PERMISSION_MISMATCH')
    consumed = [config[k] for k in ('physical_windows_path', 'hardware_path', 'D0_contract_path', 'OD_manifest_path')]
    consumed += config['sgp4_asset_paths'] + [FROZEN_ROUTER_MANIFEST]
    consumed += [r['topology_artifact'] for r in runs] + [r['traffic_asset'] for r in runs]
    required_code = ['src/dynamic_lisl/f3_v2/' + name for name in
        ('matrix_execution.py', 'registered_runtime.py', 'episode_execution.py', 'service_adapter.py',
         'batch_executor.py', 'joint_action.py', 'joint_proposer.py', 'candidate_source.py',
         'snapshot_controllers.py', 'batch_rollout.py', 'natural_engine.py', 'evidence.py',
         'preflight.py', 'result_analysis.py', 'physical_trial.py', 'structural.py', 'epoch_validation.py')]
    required_code += ['tools/run_f3_v2_registered_matrix.py']
    required_code += ['src/dynamic_lisl/' + name for name in
        ('terminal_executor.py', 'terminal_pair_intervals.py', 'gate_c_simplified_feasibility.py',
         'transition_profiler.py', 'transition_service_orchestrator.py', 'gate_e2_experiments.py',
         'common_router.py', 'load_aware_router.py', 'scientific_snapshot.py', 'traffic_trace.py',
         'commodity.py', 'sgp4_model.py', 'b4_branch_multiprocessing.py', 'operational_policy.py')]
    required_code += ['src/dynamic_lisl/' + name for name in
        ('queue_state.py', 'in_flight.py', 'service_scheduler.py', 'outage_metrics.py',
         'common.py', 'gate_d_scenarios.py', 'mechanism_validation.py')]
    for path in consumed + required_code:
        if not checked_file(root, path, hashes.get(path)):
            raise ValueError('UNPINNED_RUNTIME_INPUT_OR_CODE:' + str(path))
    validate_inherited_runtime_parameters(root, config)
    folder = Path(config['sgp4_asset_folder'])
    if folder.is_absolute() or '..' in folder.parts:
        raise ValueError('EXACT_LOCAL_SGP4_BUNDLE_REQUIRED')
    actual = {(root / folder / name).relative_to(root).as_posix()
        for name in ('manifest.json', 'hashes.json', 'constellation.tle')}
    if not actual <= set(config['sgp4_asset_paths']):
        raise ValueError('SGP4_CONSUMED_BUNDLE_FILES_NOT_PINNED')
    for r in runs:
        expected = manifest.get('result_provenance', {}).get(r['run_id'], {})
        if (not expected.get('inputs') or not expected.get('code')
            or not set(required_code) <= set(expected['code'])
            or not {r['topology_artifact'], r['traffic_asset'], *config['sgp4_asset_paths'],
                config['physical_windows_path'], config['hardware_path'], config['D0_contract_path'],
                config['OD_manifest_path'], FROZEN_ROUTER_MANIFEST} <= set(expected['inputs'])
            or any(hashes.get(p) != h for group in ('inputs', 'code') for p, h in expected[group].items())):
            raise ValueError('INCOMPLETE_EXACT_REGISTERED_PROVENANCE:' + r['run_id'])
    return {'status': 'REGISTERED_ENTRY_READY', 'preflight': gate,
        'runtime_configuration_sha256': config_hash, 'registered_runs': 42,
        'detached_authority_hashes': detached, 'registered_experiment_started': False}


def _seal(directory):
    write_new_json(directory / 'artifact_hashes.json', {p.relative_to(directory).as_posix(): file_sha256(p)
        for p in directory.rglob('*') if p.is_file()})


def run_matrix(root, output_dir, *, runs, runtime_factory, engineering_only,
               manifest=None, admission_inputs=None):
    """Original order, independent episodes, cleanup before evidence and STOP.

    Runtime factory returns the already implemented kernel/controller components
    and a cleanup callable. Engineering runs must use ENGINEERING-* IDs.
    Formal calls require the independently computed admission from frozen data.
    """
    root = Path(root).resolve()
    out = Path(output_dir).resolve()
    if not out.is_relative_to(root):
        raise ValueError('EXACT_LOCAL_NEW_ATTEMPT_REQUIRED')
    if type(engineering_only) is not bool:
        raise ValueError('EXPLICIT_MATRIX_SCOPE_REQUIRED')
    if not runs or len({r.get('run_id') for r in runs}) != len(runs):
        raise ValueError('UNIQUE_ORDERED_RUN_IDS_REQUIRED')
    admission = None
    if engineering_only:
        if any(not r['run_id'].startswith('ENGINEERING-') for r in runs):
            raise ValueError('ENGINEERING_MATRIX_CANNOT_EXECUTE_REGISTERED_IDS')
    else:
        if (not manifest or not isinstance(admission_inputs, dict)
            or admission_inputs.get('manifest') != manifest or runs != manifest.get('runs')):
            raise ValueError('FORMAL_MATRIX_ADMISSION_REQUIRED')
        admission = validate_registered_request(root, **admission_inputs)
    protected = {} if engineering_only else {**manifest['file_hashes'], **admission['detached_authority_hashes']}
    out.mkdir(parents=True, exist_ok=False)
    ledger = []
    mapping = {}
    initial_states = {}
    current = None
    try:
        write_new_json(out / 'execution_request.json', {'engineering_only': engineering_only,
            'run_ids': [r['run_id'] for r in runs], 'admission': admission,
            'execution_manifest_canonical_sha256': None if engineering_only else manifest['canonical_sha256']})
        with (out / 'run_ledger.jsonl').open('x', encoding='utf-8') as stream:
            for index, run in enumerate(runs):
                current = run['run_id']
                components = None
                cleanup = None
                engine = None
                cleanup_called = [False]
                if any(not checked_file(root, p, h) for p, h in protected.items()):
                    raise ValueError('FROZEN_INPUT_CHANGED_BEFORE_RUN:' + current)
                try:
                    components = runtime_factory(run)
                    cleanup = components.pop('cleanup')
                    engine = components['engine']
                    group = tuple(run.get(k) for k in ('scale', 'rho', 'K', 'topology_regime',
                        'router', 'traffic', 'decision_cadence_s', 'max_batch_replace'))
                    initial = engine.canonical_state_sha256()
                    if group in initial_states and initial_states[group] != initial:
                        raise AssertionError('PAIRED_INITIAL_STATE_MISMATCH')
                    initial_states[group] = initial
                    write_new_json(out / ('initial_%03d.json' % index), {'run_id': current,
                        'canonical_initial_state_sha256': initial, 'fairness_group': group})
                    def close_and_check():
                        cleanup_called[0] = True
                        cleanup()
                        if any(not checked_file(root, p, h) for p, h in protected.items()):
                            raise ValueError('FROZEN_INPUT_CHANGED_DURING_RUN:' + current)
                    binding = None if engineering_only else {
                        'execution_manifest_canonical_sha256': manifest['canonical_sha256'],
                        'registered_run_configuration_sha256': canonical_sha256(run)}
                    report = execute_episode(**components, output_dir=out / ('run_%03d' % index),
                        fixture_id=current, engineering_only=engineering_only, execution_binding=binding,
                        before_persistence=close_and_check,
                        wall_limit_s=None if engineering_only else run['runtime_budget']['approved_operational_timeout_s'])
                except Exception as exc:
                    if engine is None:
                        write_new_json(out / ('initialization_failure_%03d.json' % index),
                            {'run_id': current, 'exception_type': type(exc).__name__, 'reason': str(exc),
                             'engine_created': False, 'no_scientific_result_created': True})
                        raise
                    failure = {'type': type(exc).__name__, 'reason': str(exc), 'time_s': engine.now,
                               'initialization_or_reporting_failure': True, 'do_not_continue': True}
                    if cleanup is not None and not cleanup_called[0]:
                        cleanup_called[0] = True
                        try:cleanup()
                        except Exception as cleanup_exc:
                            failure['cleanup_failure'] = str(cleanup_exc)
                    failed_dir = out / ('run_%03d' % index)
                    if not failed_dir.exists():
                        failed_dir.mkdir(exist_ok=False)
                    if not (failed_dir / 'run_evidence').exists():
                        invariant = engine_invariants(engine, expected_trace_sha256=engine.trace.sha256(),
                            complete_threshold_bits=components['schedule'].complete_threshold_bits,
                            drain_limit_s=components['schedule'].simulation_end_s,
                            capacity_tolerance_bit_s=components['capacity_tolerance_bit_s'])
                        binding = None if engineering_only else {
                            'execution_manifest_canonical_sha256': manifest['canonical_sha256'],
                            'registered_run_configuration_sha256': canonical_sha256(run)}
                        persist_run_evidence(failed_dir / 'run_evidence', engine, run_id=current,
                            invariant_report=invariant, decision_records=[], candidate_audits=[],
                            code_hashes=components['code_hashes'], input_hashes=components['input_hashes'],
                            failure=failure, engineering_only=engineering_only, execution_binding=binding)
                    else:
                        # Never rewrite a partially sealed episode attempt.
                        write_new_json(failed_dir / 'reporting_failure.json', failure)
                    report = {'status': 'FAIL_STOP', 'scientific_outcome': 'EXECUTION_BLOCKED'}
                finally:
                    if cleanup is not None and not cleanup_called[0]:
                        # Includes a mismatch before episode construction. No pool
                        # or live branch survives a failed initialization check.
                        cleanup()
                directory = out / ('run_%03d' % index) / 'run_evidence'
                item = {'run_id': current, 'execution_order': index + 1, 'status': report['status'],
                    'outcome': report['scientific_outcome'], 'directory': directory.relative_to(root).as_posix(),
                    'artifact_seal_sha256': file_sha256(directory / 'artifact_hashes.json')}
                ledger.append(item)
                stream.write(json.dumps(item, sort_keys=True) + '\n')
                stream.flush()
                if report['status'] == 'FAIL_STOP':
                    raise RuntimeError('MATRIX_STOPPED_BY_RUN_FAILURE:' + current)
                if item['outcome'] not in ('COMPLETE', 'CENSORED_AT_DRAIN_LIMIT'):
                    raise ValueError('INVALID_REGISTERED_RUN_OUTCOME')
                mapping[current] = item['directory']
        summary = {'status': 'ENGINEERING_MATRIX_PASS' if engineering_only else 'REGISTERED_MATRIX_EXECUTION_PASS',
            'registered_runs': len(runs), 'completed_runs': len(ledger), 'run_ledger': ledger,
            'COMPLETE_count': sum(r['outcome'] == 'COMPLETE' for r in ledger),
            'CENSORED_count': sum(r['outcome'] == 'CENSORED_AT_DRAIN_LIMIT' for r in ledger),
            'engineering_only': engineering_only, 'registered_P1_v2_executed': not engineering_only,
            'P2_started': False, 'RL_started': False, 'result_seal': not engineering_only}
        if not engineering_only:
            metrics, sources = load_sealed_registered_results(root, manifest, mapping)
            analysis = analyze_registered_results(manifest, metrics)
            if analysis['status'] != 'COMPLETE_REGISTERED_EVIDENCE':
                raise ValueError('REGISTERED_MATRIX_RESULT_SEAL_INCOMPLETE')
            write_new_json(out / 'paired_analysis.json', analysis)
            write_new_json(out / 'result_sources.json', sources)
        write_new_json(out / 'result_directory_mapping.json', mapping)
    except Exception as exc:
        summary = {'status': 'MATRIX_FAIL_STOP', 'engineering_only': engineering_only,
            'current_run_id': current, 'completed_runs': len(mapping), 'run_ledger': ledger,
            'exception_type': type(exc).__name__, 'reason': str(exc), 'result_seal': False,
            'registered_P1_v2_executed': not engineering_only and current is not None,
            'P2_started': False, 'RL_started': False}
        write_new_json(out / 'failure_summary.json', summary)
    write_new_json(out / 'report.json', summary)
    _seal(out)
    return summary
