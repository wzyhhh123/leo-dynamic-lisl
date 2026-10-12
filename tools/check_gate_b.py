"""Run Gate B twice and emit deterministic machine-readable acceptance evidence."""
import sys, json, unittest, io, platform
from pathlib import Path
project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project/'src'))
sys.path.insert(0, str(project/'tests'))
from dynamic_lisl.common import new_output, dump, sha
import test_terminal_executor as testmod

class Result(unittest.TextTestResult):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.cases = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append(dict(test=test.id(), status='PASS'))
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append(dict(test=test.id(), status='FAIL', detail=self._exc_info_to_string(err,test)))
    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append(dict(test=test.id(), status='ERROR', detail=self._exc_info_to_string(err,test)))

if not __debug__:
    raise RuntimeError('Gate B requires Python assertions; do not use -O')

out = new_output('gate_b')
dump(out/'status.json', dict(status='RUNNING'))
traces, results = [], []
for run in range(2):
    testmod.TRACES.clear()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(testmod)
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=Result).run(suite)
    (out/f'unittest_run_{run+1}.txt').write_text(stream.getvalue(), encoding='utf-8')
    print(stream.getvalue(), end='')
    traces.append(json.dumps(testmod.TRACES, sort_keys=True, allow_nan=False))
    results.append(result)
repeat = traces[0] == traces[1]
(out/'traces.json').write_text(traces[0], encoding='utf-8')
inputs = dict(scope='Gate B synthetic terminal lifecycle only', random_seed=None,
              time_unit='s', tx_completion='includes final signal reception',
              geometry_role='accepted interface input only; not consumed by synthetic unit tests',
              scenario_inputs='all commands, times, peers and synthetic orientations in hashed test source',
              fixed_ports='inventory independent; fixed link geometry/capacity not simulated',
              code_hashes={str(p.relative_to(project)):sha(p) for p in [
                  project/'src/dynamic_lisl/terminal_executor.py',
                  project/'tests/test_terminal_executor.py',Path(__file__),
                  project/'src/dynamic_lisl/common.py']},
              geometry_input_hashes={str(p.relative_to(project)):sha(p) for p in [
                  project/'outputs/geometry_20260921T053240_016088Z/summary.json',
                  project/'outputs/visibility_20260921T055451_308214Z/hashes.json',
                  project/'outputs/common_mode_audit_20260921T061043_579554Z/audit.json',
                  project/'configs/gate_a_acceptance_v0.3.json']},
              python=platform.python_version())
dump(out/'inputs.json', inputs)
acceptance = {
    'normal_bilateral_setup': ['normal_bilateral_ready_formula'],
    'occupied_terminal_bbm': ['occupied_bbm_drain_last_reception', 'two_occupied_endpoints_release_both_old_links'],
    'idle_pair_mbb': ['mbb_idle_second_terminals_link_up_before_drain', 'mbb_requires_two_truly_idle_endpoints', 'mbb_old_link_dependency_cannot_be_stolen'],
    'bilateral_reservation_conflict': ['bilateral_reservation_conflict_either_endpoint'],
    'bilateral_release': ['bilateral_disconnect', 'natural_visibility_expiry_releases_active_pair'],
    'draining_no_new_tx': ['draining_rejects_new_tx_both_directions'],
    'visibility_abort': ['expiry_abort_during_retarget_releases_both', 'mbb_abort_keeps_old_link_and_unlocks_it', 'scheduled_visibility_loss_wins_same_time_ready'],
    'stale_event_guard': ['stale_link_ready_cannot_reactivate_reused_ports', 'event_version_guard_rejects_wrong_token', 'stale_down_cannot_disconnect_new_binding'],
    'keep_no_setup': ['repeated_keep_has_no_setup_or_version_change'],
    'same_peer_new_terminal': ['same_peer_changed_terminal_is_bbm_and_new_setup', 'same_peer_one_terminal_changed', 'parallel_same_satellite_pair_mbb_rejected'],
    'atomic_batch': ['multiple_commands_atomic_failure_preserves_old_active', 'multiple_commands_valid_disjoint_commit'],
    'independent_other_ports': ['other_dynamic_and_fixed_ports_unchanged'],
    'setup_target_frozen': ['setup_cannot_change_target_retarget_or_acquiring'],
    'invariant_negative_tests': ['invariants_detect_unilateral_active_and_inventory_corruption'],
}
case_status = {c['test'].split('.')[-1]: c['status'] for c in results[0].cases}
acceptance_report = {name: dict(status='PASS' if all(case_status.get('test_'+x)=='PASS' for x in cases) else 'FAIL', tests=['test_'+x for x in cases]) for name,cases in acceptance.items()}
passed = all(r.wasSuccessful() and r.testsRun >= 34 for r in results) and repeat and all(x['status']=='PASS' for x in acceptance_report.values())
report = dict(status='PASS' if passed else 'FAIL', tests_run=results[0].testsRun,
              repeated_runs=2, deterministic_state_and_log_match=repeat,
              cases=results[0].cases, repeat_cases=results[1].cases, acceptance_checks=acceptance_report,
              invariant_checks=sum(x['invariant_checks'] for t in json.loads(traces[0]) for x in t['runs']),
              scope='Gate B ONLY; no Gate C safety/hardware certification or main performance experiment')
dump(out/'report.json', report)
dump(out/'status.json', dict(status=report['status'], tests_run=report['tests_run']))
dump(out/'hashes.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='hashes.json'})
print('GATE B', report['status'], out)
raise SystemExit(0 if passed else 1)
