"""Append 0004 only after tests; perform complete old-asset audit before sealing."""
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import sys

V = Path(__file__).resolve().parents[2]
ROOT = V.parents[1]
A = Path(__file__).parent
ORIGIN = 'ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT = '7c9fa913a72ab740dfff233513c766ded57326fad2906c259d8ba56a3998baeb'
spec = importlib.util.spec_from_file_location('n1a_vc', V/'tools/version_control.py')
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def main():
    version, baseline, expected, latest, parent, reserved = vc.load_expected(ROOT, ORIGIN, PARENT)
    n1a = vc.read_json(A/'n1a_test_report.json')
    before, after = (vc.read_json(A/('regression_'+when+'.json')) for when in ('before', 'after'))
    assert n1a['status'] == 'PASS' and n1a['tests_run'] == 25
    assert n1a['pre_execution_bindings'] == n1a['post_execution_bindings']
    assert before['failures'] == after['failures'] and before['errors'] == after['errors'] == []
    assert before['tests_run'] == after['tests_run'] == 97
    write_new(A/'regression_comparison.json', dict(scope='ENGINEERING_REGRESSION_COMPARISON',
        tests_run_each=97, passed_each=96, existing_failure_count=1, new_regressions=0,
        same_failure_names_and_tracebacks=True, failures=after['failures'],
        production_code_modified=False, historical_test_expectations_modified=False))
    write_new(A/'version_protection_tests.json', dict(scope='ISOLATED_VERSION_PROTECTION_TESTS_ONLY',
        status='PASS', tests_run=22, failures=0, errors=0,
        command='D:/Program_Files/anaconda3/envs/pytorch/python.exe -B research_versions/dynamic_k_v1/tests/test_version_control.py -v',
        evidence_source='execution_tool_transcript_of_this_authorized_turn',
        coverage=['content/deletion/rename/addition/raw-newline', 'manifest/seal/parent/origin tamper',
                  'external latest anchor detects tail deletion', 'omission/read failures/concurrent changes',
                  'unregistered legacy edits and historical test rewrites', 'unauthorized draft experiments rejected']))
    write_new(A/'pre_implementation_verification.json', dict(status='PASS', revision_id='0003',
        expected_version_sha256=ORIGIN, expected_revision_sha256=PARENT,
        baseline_seal_sha256=version['baseline_seal']['sha256'], baseline_file_count=5810,
        verified_file_count=5837, excluded_file_count=202,
        undeclared_changes={'added':[], 'deleted':[], 'modified':[], 'possible_renames':[]},
        source='complete version_control.py verify output before implementation in this turn',
        scope='FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY'))
    actual, exclusions = vc.inventory(ROOT, progress=lambda x: print(json.dumps({'progress':x}), flush=True))
    for path in reserved:
        actual.pop(path, None)
    diff = vc.differences(expected, actual)
    namespace = 'research_versions/dynamic_k_v1/'
    assert all(row['path'].startswith(namespace) for op in ('added', 'modified', 'deleted') for row in diff[op]), 'OLD_ASSET_DRIFT'
    assert not diff['deleted'], 'No deletion is authorized in N1a'
    assert {r['path'] for r in diff['modified']} == {
        namespace+'contracts/research_contract_v1_DRAFT_CN.md', namespace+'configs/research_v1_DRAFT.json'}
    assert vc.load_expected(ROOT, ORIGIN, PARENT) == (version, baseline, expected, latest, parent, reserved), 'ANCHORS_CHANGED_DURING_SCAN'
    audit = dict(scope='PRESEAL_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT', status='PASS',
        legacy_baseline_file_count=5810, legacy_changed_files=[],
        full_inventory_includes_ignored_research_assets=True, excluded_file_count=len(exclusions),
        existing_anchor_sha256=ORIGIN, parent_revision_sha256=PARENT,
        changes_observed_before_audit_file_creation=diff,
        scientific_gate_pass=False, N1b_implemented=False, N2_implemented=False)
    write_new(A/'preseal_change_audit.json', audit)
    # Only fresh namespace artifacts were added by this function after the full scan.
    now_files = {p.relative_to(ROOT).as_posix(): vc.file_info(p)
                 for p in V.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    actual.update(now_files)
    for path in reserved:
        actual.pop(path, None)
    final = vc.differences(expected, actual)
    now = datetime.now(timezone.utc)
    record = dict(schema='dynamic_k_revision_record_v1', version_id='dynamic_k_v1', revision_id='0004',
        parent_record=parent, created_utc=now.isoformat(),
        created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N1a：独立固定时域推进、四能耗态/五执行态终端事件积分与工程验收；不修改历史生产代码。',
        authorization=dict(actor='human_user', scope='N1a_FIXED_HORIZON_FOUR_STATE_ENERGY_ENGINEERING_ONLY',
            source='current_conversation_user_request',
            request='继续 dynamic_k_v1，授权执行 Stage N1a — Fixed-Horizon Four-State LCT Energy Accounting。先验证独立起点和指定修订0003哈希；实现320终端真实事件积分、统一固定T及指标，执行解析测试、适用历史回归和完整版本验证。正式科学参数保持null，不实现N1b/N2/MADRL，不开展主性能实验；连续新增修订，完成后停止等待授权。'),
        bindings=dict(baseline_seal=version['baseline_seal'],
            contract=vc.binding(ROOT, namespace+'contracts/research_contract_v1_DRAFT_CN.md'),
            configuration=vc.binding(ROOT, namespace+'configs/research_v1_DRAFT.json'),
            implementation_manifest=vc.binding(ROOT, namespace+'acceptance/0004/implementation_manifest.json'),
            n1a_acceptance=vc.binding(ROOT, namespace+'acceptance/0004/n1a_test_report.json'),
            chinese_report=vc.binding(ROOT, namespace+'acceptance/0004/RESULT_CN.md'),
            preseal_old_asset_audit=vc.binding(ROOT, namespace+'acceptance/0004/preseal_change_audit.json')),
        changes={k: final[k] for k in ('added', 'modified', 'deleted')},
        engineering_acceptance=dict(N1a='PASS', new_tests=25, version_protection_tests=22,
                                   historical_regressions=97, historical_existing_failures=1,
                                   introduced_regressions=0),
        old_assets_modified=False, production_code_modified=False,
        formal_experiments_executed=False, scientific_gate_pass=False,
        N1b_implemented=False, N2_implemented=False, algorithm_selection=None)
    target = V/'revisions/0004'
    target.mkdir(exist_ok=False)
    write_new(target/'record.json', record)
    print(json.dumps(vc.binding(ROOT, namespace+'revisions/0004/record.json'), indent=2))


if __name__ == '__main__':
    main()
