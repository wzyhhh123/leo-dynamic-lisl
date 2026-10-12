"""Real tiny kernel orchestration; fictional authority schema is never executed."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_f3_v2_engineering_episode import scene
from dynamic_lisl.f3_v2.matrix_execution import (run_matrix, validate_registered_request,
    validate_inherited_runtime_parameters, FROZEN_ROUTER_MANIFEST)
from dynamic_lisl.f3_v2.engineering_episode import run_engineering_episode
from dynamic_lisl.f3_v2.service_adapter import BatchCadenceAdapter
from dynamic_lisl.f3_v2.evidence import file_sha256
from dynamic_lisl.f3_v2.joint_action import canonical_sha256

ROOT = Path(__file__).resolve().parents[1]


def rows(*controllers):
    return [{'run_id': 'ENGINEERING-MATRIX-%02d' % i, 'controller': cid,
        'scale': 8, 'rho': .5, 'K': 2, 'topology_regime': 'TINY_ONLY', 'router': 'TINY_ROUTER',
        'traffic': 'TINY_FIXED_TRACE', 'decision_cadence_s': 2, 'max_batch_replace': 2}
        for i, cid in enumerate(controllers)]


def factory(calls, cleanup_calls, rate=1, fail_index=None, corrupt_index=None):
    def make(row):
        index = len(calls)
        calls.append(row['run_id'])
        args = scene(row['controller'], rate=rate)
        args.pop('fixture_id')
        if index == fail_index:
            def broken_source(*unused):
                raise RuntimeError('ENGINEERING_SOURCE_FAILURE_ONLY')
            args['source'] = broken_source
        if index == corrupt_index:
            args['engine'].queues.bits[(args['engine'].nodes[0], 'f0')] += 1
        args['cleanup'] = lambda: cleanup_calls.append(row['run_id'])
        return args
    return make


def protocol_fixture(root):
    """Fictional on-disk authority parser fixture; no runtime is ever built.

    All reports are literal schema test data, never evidence of actual K*/8w
    acceptance. Files live exclusively in TemporaryDirectory and are removed.
    """
    def write(path, doc):
        target = root / path; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc), encoding='utf-8')
    def frozen(doc):
        doc.update(status='FROZEN', frozen=True)
        doc['canonical_sha256'] = canonical_sha256(doc)
        return doc
    original = json.loads((ROOT / 'configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json').read_text(encoding='utf-8'))
    write('matrix.json', original)
    assets = {r['traffic_asset'] for r in original['runs']}
    assets |= {r['topology_artifact'] for r in original['runs'] if r['topology_regime'] == 'K4_HISTORICAL_REFERENCE'}
    assets |= {'windows.jsonl', 'hardware.json', 'D0.json', 'OD.json', 'topology.json',
        'sgp4/manifest.json', 'sgp4/hashes.json', 'sgp4/constellation.tle'}
    for path in assets:
        write(path, {'scope': 'TEMP_PARSER_FIXTURE_ONLY_NOT_A_PHYSICAL_ASSET'})
    write('D0.json', {'scope': 'TEMP_SCHEMA_ONLY', 'link_capacity_bit_s_per_direction': 1e10})
    path = root / FROZEN_ROUTER_MANIFEST; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((ROOT / FROZEN_ROUTER_MANIFEST).read_bytes())
    assets.add(FROZEN_ROUTER_MANIFEST)
    config = {'frame_id': 'TEMP_PARSER_WORLD', 'physical_windows_path': 'windows.jsonl',
        'hardware_path': 'hardware.json', 'D0_contract_path': 'D0.json', 'OD_manifest_path': 'OD.json',
        'sgp4_asset_folder': 'sgp4', 'sgp4_asset_paths': ['sgp4/manifest.json', 'sgp4/hashes.json', 'sgp4/constellation.tle'],
        'safety_mode': 'STRICT_CONNECTED', 'source_policy': 'UNCAPPED_PHYSICAL_SCAN_THEN_STRATIFIED_OUTPUT_CAPS_V1',
        'raw_budget': {'BBM_cap': 32, 'MBB_cap': 32, 'total_cap': 64},
        'search_budget_by_batch': {'1': {'singleton_cap': 16, 'per_stratum_slots': 8, 'beam_width': 4,
            'max_non_hold': 16, 'max_members': 1, 'expansion_cap': 16, 'validation_cap': 16, 'rollout_cap': 17},
            '4': {'singleton_cap': 16, 'per_stratum_slots': 8, 'beam_width': 4, 'max_non_hold': 32,
            'max_members': 4, 'expansion_cap': 184, 'validation_cap': 184, 'rollout_cap': 33}},
        'B3_eta_aggregation': 'min', 'B2_initial_age_s': 0, 'worker_count': 8,
        'initialization_convention': 'PREESTABLISHED_AT_ZERO_WITH_FORWARD_GATE_C_CERTIFICATE',
        'capacity_tolerance_bit_s': .01, 'clip_horizon_at_end': True,
        'load_aware_router_parameters': {'utilization_penalty_s': .05, 'queue_penalty_s': .02,
            'queue_scale_bits': 1e9, 'time_tolerance_s': 1e-12}}
    science = frozen({'action_kinds': ['HOLD', 'BATCH_REPLACE'],
        'runtime_configuration_canonical_sha256': canonical_sha256(config), 'scope': 'TEMP_SCHEMA_ONLY'})
    write('science.json', science)
    code = []
    for parent in ('src/dynamic_lisl', 'src/dynamic_lisl/f3_v2'):
        for p in (ROOT / parent).glob('*.py'):
            path = root / p.relative_to(ROOT); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(p.read_bytes()); code.append(path.relative_to(root).as_posix())
    cli = 'tools/run_f3_v2_registered_matrix.py'
    path = root / cli; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((ROOT / cli).read_bytes()); code.append(cli)
    k0 = {'status': 'PASS', 'full_audit_complete': True, 'human_authorization_verified': True,
          'K_star': 8, 'scope': 'TEMP_SCHEMA_ONLY_NOT_REAL_ACCEPTANCE'}
    k1 = {'status': 'PASS', 'approved_K_star': 8, 'batch_compatibility_checked': True,
          'topology_artifact': 'topology.json', 'topology_sha256': file_sha256(root / 'topology.json')}
    eng = {key: 'PASS' for key in ('V2_A', 'V2_B', 'V2_C', 'V2_D', 'V2_E', 'V2_F',
        'full_regression', 'serial_8worker_natural_geometry', 'no_performance_leakage', 'historical_integrity')}
    eng['runtime_configuration_canonical_sha256'] = canonical_sha256(config)
    budget = {'status': 'MEASURED_AND_APPROVED', 'matrix_wall_budget_s': 100}
    references = {}
    for key, doc in (('K0', k0), ('K1', k1), ('ENGINEERING', eng), ('RUNTIME', budget)):
        write(key + '.json', doc)
        references[key] = {'path': key + '.json', 'sha256': file_sha256(root / (key + '.json'))}
    hashes = {p: file_sha256(root / p) for p in [*assets, *code, 'matrix.json', 'science.json']}
    hashes.update({r['path']: r['sha256'] for r in references.values()})
    runs = deepcopy(original['runs'])
    for r in runs:
        r['K'] = 4 if r['topology_regime'] == 'K4_HISTORICAL_REFERENCE' else 8
        if r['K'] == 8:r['topology_artifact'] = 'topology.json'
        r['runtime_budget']['estimated_wall_clock_s'] = 1
        r['runtime_budget']['approved_operational_timeout_s'] = 2
    provenance = {r['run_id']: {'code': {p: hashes[p] for p in code},
        'inputs': {p: hashes[p] for p in assets}} for r in runs}
    manifest = frozen({'runs': runs, 'file_hashes': hashes, 'acceptance_evidence': references,
        'scientific_contract_canonical_sha256': science['canonical_sha256'], 'source_matrix_path': 'matrix.json',
        'science_contract_path': 'science.json', 'authorization_path': 'approval.json',
        'execution_manifest_path': 'manifest.json', 'runtime_configuration': config,
        'result_provenance': provenance, 'contrasts': original['contrasts'],
        'registered_opening_figure_proposal': original['registered_opening_figure_proposal']})
    write('manifest.json', manifest)
    auth = {'actor': 'HUMAN', 'status': 'APPROVED', 'scope': 'REGISTERED_F3_V2',
        'manifest_canonical_sha256': manifest['canonical_sha256'], 'authorized_run_ids': [r['run_id'] for r in runs]}
    write('approval.json', auth)
    return dict(manifest=manifest, science_contract=science, k0_report=k0, k1_report=k1,
        engineering_report=eng, runtime_budget=budget, authorization=auth)


class MatrixExecutionTests(unittest.TestCase):
    def test_original_order_all_baselines_real_kernel_no_registered_results(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
            calls, closed = [], []
            requested = rows('B0-v2', 'B1-v2', 'B2-v2', 'B3-v2', 'B4-v2')
            report = run_matrix(ROOT, Path(tmp) / 'attempt', runs=requested,
                runtime_factory=factory(calls, closed), engineering_only=True)
            self.assertEqual(report['status'], 'ENGINEERING_MATRIX_PASS', report)
            self.assertEqual(calls, [r['run_id'] for r in requested])
            self.assertEqual(closed, calls)
            self.assertFalse(report['registered_P1_v2_executed'])
            self.assertFalse(report['result_seal'])
            self.assertFalse((Path(tmp) / 'attempt/paired_analysis.json').exists())
            for i, item in enumerate(report['run_ledger']):
                data = json.loads((Path(tmp) / ('attempt/run_%03d/run_evidence/metrics.json' % i)).read_text())
                self.assertTrue(data['engineering_only'])
                self.assertEqual(data['run_id'], item['run_id'])
            seal = json.loads((Path(tmp) / 'attempt/artifact_hashes.json').read_text())
            for path, digest in seal.items():
                self.assertEqual(file_sha256(Path(tmp) / 'attempt' / path), digest)

    def test_shared_orchestrator_equals_direct_existing_adapter_state_chain(self):
        for cid in ('B0-v2', 'B1-v2', 'B3-v2', 'B4-v2'):
            with self.subTest(controller=cid), tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
                a, b = scene(cid), scene(cid)
                wrapped = run_engineering_episode(output_dir=Path(tmp) / 'wrapped', **a)
                def observe(engine, root, horizon):
                    members, _ = b['source'](engine, b['validator'])
                    pool = b['proposer'].propose(engine.executor, members, decision_root_sha256=root)
                    if cid == 'B4-v2':
                        return b['controller'].observe(engine, pool, horizon_s=horizon).action
                    return b['controller'].observe(engine, pool).action
                direct = BatchCadenceAdapter(b['engine'], b['schedule'], b['validator']).run(observe)
                self.assertEqual(wrapped['checkpoints'], direct['checkpoints'])
                self.assertEqual(a['engine'].canonical_state(), b['engine'].canonical_state())

    def test_failure_persists_all_raw_evidence_before_stop_no_later_factory(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
            calls, closed = [], []
            requested = rows('B0-v2', 'B1-v2', 'B3-v2')
            report = run_matrix(ROOT, Path(tmp) / 'attempt', runs=requested,
                runtime_factory=factory(calls, closed, fail_index=0), engineering_only=True)
            self.assertEqual(report['status'], 'MATRIX_FAIL_STOP')
            self.assertEqual(calls, [requested[0]['run_id']])
            self.assertEqual(closed, calls)
            self.assertFalse((Path(tmp) / 'attempt/run_001').exists())
            directory = Path(tmp) / 'attempt/run_000/run_evidence'
            for name in ('invariant_report.json', 'failure_summary.json', 'final_state_evidence.json',
                'metrics.json', 'action_timeline.json', 'transition_timeline.json',
                'candidate_source_audit.json', 'timeseries.json', 'input_code_hashes.json', 'artifact_hashes.json'):
                self.assertTrue((directory / name).is_file())
            self.assertEqual(report['run_ledger'][0]['outcome'], 'EXECUTION_BLOCKED')

    def test_censored_is_legal_and_continues_manifest_order(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
            calls, closed = [], []
            report = run_matrix(ROOT, Path(tmp) / 'attempt', runs=rows('B0-v2', 'B3-v2'),
                runtime_factory=factory(calls, closed, rate=1000), engineering_only=True)
            self.assertEqual(report['status'], 'ENGINEERING_MATRIX_PASS', report)
            self.assertEqual(report['CENSORED_count'], 2)
            self.assertEqual(len(calls), 2)
            self.assertEqual(closed, calls)

    def test_paired_initial_mismatch_preserves_failed_state_and_closes_runtime(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
            calls, closed = [], []
            report = run_matrix(ROOT, Path(tmp) / 'attempt', runs=rows('B0-v2', 'B3-v2'),
                runtime_factory=factory(calls, closed, corrupt_index=1), engineering_only=True)
            self.assertEqual(report['status'], 'MATRIX_FAIL_STOP')
            self.assertEqual(report['run_ledger'][1]['outcome'], 'EXECUTION_BLOCKED')
            self.assertEqual(closed, calls)
            failure = json.loads((Path(tmp) / 'attempt/run_001/run_evidence/failure_summary.json').read_text())
            self.assertEqual(failure['failure']['reason'], 'PAIRED_INITIAL_STATE_MISMATCH')

    def test_cleanup_failure_blocks_before_metrics_can_claim_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
            def make(row):
                args = scene('B0-v2'); args.pop('fixture_id')
                def cleanup():
                    raise RuntimeError('ENGINEERING_CLEANUP_FAILURE')
                args['cleanup'] = cleanup
                return args
            report = run_matrix(ROOT, Path(tmp) / 'attempt', runs=rows('B0-v2'), runtime_factory=make, engineering_only=True)
            self.assertEqual(report['status'], 'MATRIX_FAIL_STOP')
            metrics = json.loads((Path(tmp) / 'attempt/run_000/run_evidence/metrics.json').read_text())
            self.assertEqual(metrics['outcome'], 'EXECUTION_BLOCKED')

    def test_existing_attempt_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
            directory = Path(tmp) / 'attempt'; directory.mkdir()
            (directory / 'history.txt').write_text('KEEP')
            with self.assertRaises(FileExistsError):
                run_matrix(ROOT, directory, runs=rows('B0-v2'), runtime_factory=factory([], []), engineering_only=True)
            self.assertEqual((directory / 'history.txt').read_text(), 'KEEP')

    def test_registered_ids_and_forged_admission_rejected_before_factory(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as tmp:
            called = []
            run = {'run_id': 'OCT26-CORE-01'}
            with self.assertRaisesRegex(ValueError, 'ENGINEERING_MATRIX_CANNOT_EXECUTE_REGISTERED_IDS'):
                run_matrix(ROOT, Path(tmp) / 'engineering', runs=[run], runtime_factory=lambda r: called.append(r), engineering_only=True)
            with self.assertRaisesRegex(ValueError, 'FORMAL_MATRIX_ADMISSION_REQUIRED'):
                run_matrix(ROOT, Path(tmp) / 'registered', runs=[run], runtime_factory=lambda r: called.append(r),
                    engineering_only=False, manifest={'runs': [run]}, admission_inputs={})
            self.assertEqual(called, [])
            self.assertFalse((Path(tmp) / 'registered').exists())

    def test_actual_DRAFT_prefight_cannot_construct_engine(self):
        matrix = json.loads((ROOT / 'configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json').read_text(encoding='utf-8'))
        science = json.loads((ROOT / 'configs/gate_f3_v2_execution_contract_DRAFT.json').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError, 'REGISTERED_PREFLIGHT_NOT_READY'):
            validate_registered_request(ROOT, manifest=matrix, science_contract=science,
                k0_report={}, k1_report={}, engineering_report={}, runtime_budget={}, authorization={})

    def test_complete_temp_authority_schema_without_any_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); documents = protocol_fixture(root)
            gate = validate_registered_request(root, **documents)
            self.assertEqual(gate['status'], 'REGISTERED_ENTRY_READY')
            self.assertEqual(gate['registered_runs'], 42)
            self.assertFalse(gate['registered_experiment_started'])
            self.assertEqual(set(gate['detached_authority_hashes']), {'manifest.json', 'approval.json'})

    def test_schema_tamper_and_missing_runtime_provenance_fail_closed(self):
        for mode in ('source_tamper', 'manifest_tamper', 'approval_tamper', 'missing_code'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); documents = protocol_fixture(root)
                if mode == 'source_tamper':
                    (root / 'src/dynamic_lisl/f3_v2/matrix_execution.py').write_text('changed')
                elif mode == 'manifest_tamper':
                    value = json.loads((root / 'manifest.json').read_text()); value['runtime_configuration']['worker_count'] = 1
                    (root / 'manifest.json').write_text(json.dumps(value))
                elif mode == 'approval_tamper':
                    value = json.loads((root / 'approval.json').read_text()); value['actor'] = 'AUTOMATION'
                    (root / 'approval.json').write_text(json.dumps(value))
                else:
                    documents['manifest']['result_provenance'][documents['manifest']['runs'][0]['run_id']]['code'].pop('src/dynamic_lisl/f3_v2/episode_execution.py')
                with self.assertRaises(ValueError):
                    validate_registered_request(root, **documents)

    def test_runtime_cannot_relax_inherited_capacity_or_router_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); documents = protocol_fixture(root)
            original = documents['manifest']['runtime_configuration']
            validate_inherited_runtime_parameters(root, original)
            for mode in ('capacity', 'router_weight', 'router_time_tolerance'):
                with self.subTest(mode=mode):
                    config = deepcopy(original)
                    if mode == 'capacity':config['capacity_tolerance_bit_s'] = 1
                    elif mode == 'router_weight':config['load_aware_router_parameters']['queue_penalty_s'] = .03
                    else:config['load_aware_router_parameters']['time_tolerance_s'] = 1
                    with self.assertRaisesRegex(ValueError, 'INHERITED_'):
                        validate_inherited_runtime_parameters(root, config)


if __name__ == '__main__':
    unittest.main()
