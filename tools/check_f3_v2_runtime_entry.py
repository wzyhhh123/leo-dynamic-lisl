"""Tiny ordered episodes plus t0-only natural factory checks; no registered run."""
from datetime import datetime, timezone
import json
import multiprocessing
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from dynamic_lisl.f3_v2.evidence import write_new_json, file_sha256
from dynamic_lisl.f3_v2.matrix_execution import run_matrix, SUPPORTED_SOURCE_POLICY
from dynamic_lisl.f3_v2.registered_runtime import create_runtime
from test_f3_v2_matrix_execution import rows, factory


def main():
    out = ROOT / 'outputs' / ('f3_v2_runtime_entry_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(exist_ok=False)
    print(str(out), flush=True)
    started = time.perf_counter()
    hashes = {'code': {p.relative_to(ROOT).as_posix(): file_sha256(p)
        for p in sorted((ROOT / 'src/dynamic_lisl/f3_v2').glob('*.py'))},
        'input': {p: file_sha256(ROOT / p) for p in (
            'configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json', 'configs/gate_k0_contract_v1_1_DRAFT.json',
            'configs/gate_f3_v2_execution_contract_DRAFT.json', 'configs/z_moderate_v1.json',
            'configs/gate_d0_traffic_contract.json', 'configs/gate_d0_od_manifest_16.json',
            'configs/gate_e0_sweep_manifest.json',
            'configs/gate_f3_traffic_hotspot_migration_v1.json', 'configs/hardware_gate_c_simplified_v1.json',
            'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',
            'data/raw/sgp4_x720/manifest.json', 'data/raw/sgp4_x720/hashes.json', 'data/raw/sgp4_x720/constellation.tle')}}
    write_new_json(out / 'input_code_hashes.json', hashes)
    write_new_json(out / 'fixture_contract.json', {
        'scope': 'ENGINEERING_ONLY', 'ordered_tiny_controllers': ['B0-v2', 'B1-v2', 'B2-v2', 'B3-v2', 'B4-v2'],
        'natural_factory_fixture': {'K': 4, 'scale': 160, 'rho': .5, 'time_s': 0,
            'controllers': ['B0-v2', 'B1-v2', 'B3-v2', 'B4-v2'], 'advance_s': 0,
            'candidate_evaluations': 0, 'controller_observations': 0},
        'NOT_final_K_star_full_pool_or_5s_B4_acceptance': True, 'registered_experiment_started': False})
    try:
        calls, closed = [], []
        ordered = rows('B0-v2', 'B1-v2', 'B2-v2', 'B3-v2', 'B4-v2')
        matrix = run_matrix(ROOT, out / 'tiny_matrix', runs=ordered, runtime_factory=factory(calls, closed), engineering_only=True)
        if matrix['status'] != 'ENGINEERING_MATRIX_PASS' or closed != calls:
            raise AssertionError('ENGINEERING_ORDERED_MATRIX_NOT_PASS')
        # Existing natural engineering constructor is the reference. No state
        # advances, economic comparison, source search or rollout is performed.
        from check_f3_v2_natural_prefix import load_scene, FRAME
        reference, _, _, _ = load_scene()
        params = {'utilization_penalty_s': .05, 'queue_penalty_s': .02,
                  'queue_scale_bits': 1e9, 'time_tolerance_s': 1e-12}
        single = {'singleton_cap': 16, 'per_stratum_slots': 8, 'beam_width': 4,
            'max_non_hold': 16, 'max_members': 1, 'expansion_cap': 16, 'validation_cap': 16, 'rollout_cap': 17}
        batch = {**single, 'max_non_hold': 32, 'max_members': 4,
                 'expansion_cap': 184, 'validation_cap': 184, 'rollout_cap': 33}
        config = {'frame_id': FRAME, 'physical_windows_path': 'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',
            'hardware_path': 'configs/hardware_gate_c_simplified_v1.json', 'D0_contract_path': 'configs/gate_d0_traffic_contract.json',
            'OD_manifest_path': 'configs/gate_d0_od_manifest_16.json', 'sgp4_asset_folder': 'data/raw/sgp4_x720',
            'sgp4_asset_paths': ['data/raw/sgp4_x720/' + p for p in ('manifest.json', 'hashes.json', 'constellation.tle')],
            'safety_mode': 'STRICT_CONNECTED', 'source_policy': SUPPORTED_SOURCE_POLICY,
            'raw_budget': {'BBM_cap': 32, 'MBB_cap': 32, 'total_cap': 64}, 'search_budget_by_batch': {'1': single, '4': batch},
            'B3_eta_aggregation': 'min', 'B2_initial_age_s': 0, 'initialization_convention': 'PREESTABLISHED_AT_ZERO_WITH_FORWARD_GATE_C_CERTIFICATE',
            'capacity_tolerance_bit_s': .01, 'clip_horizon_at_end': True, 'load_aware_router_parameters': params, 'worker_count': 8}
        initial_rows = []
        children_before = {p.pid for p in multiprocessing.active_children()}
        for cid in ('B0-v2', 'B1-v2', 'B3-v2', 'B4-v2'):
            run = {'run_id': 'ENGINEERING-NATURAL-FACTORY-' + cid, 'K': 4, 'topology_regime': 'K4_HISTORICAL_REFERENCE',
                'topology_artifact': 'configs/z_moderate_v1.json', 'traffic_asset': 'configs/gate_f3_traffic_hotspot_migration_v1.json',
                'rho': .5, 'router': 'SHORTEST_PROPAGATION_DELAY', 'controller': cid,
                'max_batch_replace': 4, 'decision_cadence_s': 5, 'rollout_horizon_nominal_s': 10}
            descriptor = {'runtime_configuration': config, 'result_provenance': {run['run_id']: {
                'inputs': hashes['input'], 'code': hashes['code']}}}
            start = time.perf_counter()
            runtime = create_runtime(ROOT, descriptor, run)
            try:
                engine = runtime['engine']
                equal = engine.canonical_state() == reference.canonical_state()
                initial_rows.append({'controller': cid, 'time_s': engine.now,
                    'initial_state_exact': equal, 'initial_sha256': engine.canonical_state_sha256(),
                    'constructor_wall_s': time.perf_counter() - start,
                    'queue_bits': engine.queues.total(), 'inflight_bits': engine.in_flight.total(),
                    'rollout_executed': False, 'worker_pool_created': getattr(getattr(runtime['controller'], 'branch_pool', None), '_pool', None) is not None})
                write_new_json(out / ('initial_' + cid + '.json'), initial_rows[-1])
                if not equal or engine.now != 0:
                    write_new_json(out / ('mismatch_state_' + cid + '.json'), engine.canonical_state())
                    write_new_json(out / 'reference_initial_state.json', reference.canonical_state())
                    raise AssertionError('NATURAL_FACTORY_INITIAL_STATE_MISMATCH:' + cid)
            finally:
                runtime['cleanup']()
        if {p.pid for p in multiprocessing.active_children()} != children_before:
            raise AssertionError('FACTORY_CREATED_ORPHAN_PROCESS')
        path = 'configs/gate_f3_v2_execution_contract_DRAFT.json'
        command = [sys.executable, 'tools/run_f3_v2_registered_matrix.py', '--manifest', path,
            '--science-contract', path, '--k0-report', path, '--k1-report', path,
            '--engineering-report', path, '--runtime-budget', path, '--authorization', path, '--preflight-only']
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        write_new_json(out / 'registered_cli_negative_control.json', {'command': command, 'cwd': str(ROOT),
            'returncode': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr})
        if process.returncode != 1 or json.loads(process.stdout)['registered_experiment_started'] is not False:
            raise AssertionError('DRAFT_REGISTERED_ENTRY_NOT_REJECTED')
        if any(file_sha256(ROOT / p) != h for values in hashes.values() for p, h in values.items()):
            raise AssertionError('INPUT_SOURCE_CHANGED_DURING_ENGINEERING_GATE')
        report = {'status': 'ENGINEERING_RUNTIME_ENTRY_PASS', 'ordered_tiny_kernel_matrix': matrix,
            'initial_natural_factory_checks': initial_rows, 'scope': 'TINY_EPISODES_PLUS_NATURAL_T0_CONSTRUCTION_ONLY',
            'natural_controller_multi_epoch_acceptance': False, 'new_K_star_full_pool_acceptance': False,
            'DRAFT_registered_entry_denied': True, 'all_runtime_cleanup_PASS': True,
            'formal_P1_started': False, 'P2_started': False, 'RL_started': False, 'K_star_selected': False,
            'production_candidate_policy_frozen': False, 'wall_s': time.perf_counter() - started}
        rc = 0
    except Exception as exc:
        report = {'status': 'ENGINEERING_RUNTIME_ENTRY_FAIL_STOP', 'reason': str(exc),
            'exception_type': type(exc).__name__, 'formal_P1_started': False,
            'K_star_selected': False, 'wall_s': time.perf_counter() - started}
        write_new_json(out / 'failure_summary.json', report)
        rc = 1
    write_new_json(out / 'report.json', report)
    write_new_json(out / 'artifact_hashes.json', {p.relative_to(out).as_posix(): file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    print(json.dumps({'status': report['status'], 'output_dir': str(out), 'formal_P1_started': False}))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
