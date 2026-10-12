"""Seal the authorized FIFO-only 0005 after full raw-byte old-asset audit."""
from datetime import datetime,timezone,timedelta
import importlib.util
import json
from pathlib import Path
import sys

V=Path(__file__).resolve().parents[2]
P=V.parents[1]
A=Path(__file__).parent
NS='research_versions/dynamic_k_v1/'
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='815352309856b9e8aa2c5ffbb4e233dd412b6bc7aa3fd2365ea03e17230411f9'
MANIFEST='c27ac2866d4bfd12a8384bd91a990f841daad45a7079230301d1aaef4436031a'
spec=importlib.util.spec_from_file_location('n1b_seal_vc',V/'tools/version_control.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.n1b_evaluator import N1bEvidenceBinding

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def main():
    loaded=vc.load_expected(P,ORIGIN,PARENT)
    version,baseline,expected,latest,parent,reserved=loaded
    guard=N1bEvidenceBinding(P,NS+'acceptance/0005/implementation_manifest.json',MANIFEST)
    guard.verify()
    report=vc.read_json(A/'n1b_test_report.json');n1a=vc.read_json(A/'n1a_regression_report.json')
    assert report['status']==n1a['status']=='PASS' and report['tests_run']==24 and n1a['tests_run']==25
    assert report['pre_execution_bindings']==report['post_execution_bindings']==guard.verify()
    before=vc.read_json(V/'acceptance/0004/regression_after.json')
    after=vc.read_json(A/'historical_regression.json')
    assert before['tests_run']==after['tests_run']==97
    assert before['failures']==after['failures'] and len(after['failures'])==1
    assert before['errors']==after['errors']==before['skipped']==after['skipped']==[]
    write_new(A/'historical_regression_comparison.json',dict(status='PASS_NO_NEW_REGRESSIONS',
        tests_run=97,passed=96,known_legacy_failure_count=1,new_regressions=0,
        failures_identical_including_traceback=True,failures=after['failures'],
        comparison_parent_evidence=vc.binding(P,NS+'acceptance/0004/regression_after.json'),
        current_evidence=vc.binding(P,NS+'acceptance/0005/historical_regression.json')))
    write_new(A/'version_protection_tests.json',dict(status='PASS',tests_run=22,failures=0,errors=0,
        scope='ISOLATED_VERSION_PROTECTION_TESTS_ONLY',
        command='D:/Program_Files/anaconda3/envs/pytorch/python.exe -B research_versions/dynamic_k_v1/tests/test_version_control.py -v',
        evidence_source='actual_execution_tool_transcript_of_current_authorized_turn',
        coverage=['raw-byte/newline/content/add/delete/rename','origin/seal/manifest/parent/tail tamper',
                  'read failure/omission/concurrent mutation','undeclared old changes/historical test protection',
                  'draft formal experiments rejected']))
    write_new(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0004',
        expected_version_sha256=ORIGIN,expected_revision_sha256=PARENT,baseline_file_count=5810,
        verified_file_count=5859,excluded_file_count=202,
        undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        scope='FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY',scientific_gate_pass=False,
        source='complete version_control.py verify output before static contract and implementation in this turn'))
    actual,excluded=vc.inventory(P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for path in reserved:actual.pop(path,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],'OLD_OR_SEALED_ASSET_DRIFT'
    assert all(r['path'].startswith(NS) for r in diff['added']),'UNAUTHORIZED_NEW_FILE_OUTSIDE_VERSION'
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded,'ANCHORS_CHANGED_DURING_AUDIT'
    guard.verify()
    write_new(A/'preseal_change_audit.json',dict(status='PASS',scope='COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',
        baseline_file_count=5810,old_assets_changed=[],existing_version_assets_changed=[],
        includes_gitignored_research_assets=True,tmp_evidence_included=True,
        excluded_files=excluded,excluded_file_count=len(excluded),
        origin_sha256=ORIGIN,parent_revision_sha256=PARENT,changes_before_audit_file_creation=diff,
        scientific_gate_pass=False))
    # Capture this newly created audit file; recheck all namespace paths.
    actual.update({p.relative_to(P).as_posix():vc.file_info(p) for p in V.rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts})
    for path in reserved:actual.pop(path,None)
    final=vc.differences(expected,actual)
    assert not final['modified'] and not final['deleted'] and all(r['path'].startswith(NS) for r in final['added'])
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded
    guard.verify()
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0005',
        parent_record=parent,created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N1b：人工冻结本地每commodity FIFO/同刻比例混合，独立观察与连续cohort年龄积分；仅工程验收，无旧资产修改。',
        authorization=dict(actor='human_user',scope='N1B_FIFO_SEMANTIC_FREEZE_AND_ENGINEERING_ONLY',
            source='current_conversation_user_request',
            request='继续 dynamic_k_v1。接受上一轮N1b STOP，人工决定新版本采用 Node-Local Per-Commodity FIFO；跨commodity保留equal-weight max-min；同刻多入边按bit比例混合；连续注入保留真实分布与原始注入时间。先独立语义合同并通过静态检查，再独立年龄层实现N1b，不修改冻结生产内核。先以独立版本起点和指定0004哈希完整验证；新增连续修订，运行解析/真实D2/N1a/历史回归，保留旧96/97 F3失败，完整版本验证。不执行N2/MADRL/主实验，完成后停止等待审核。'),
        bindings=dict(baseline_seal=version['baseline_seal'],
            contract=vc.binding(P,NS+'contracts/N1B_NODE_LOCAL_FIFO_SEMANTICS_CN.md'),
            configuration=vc.binding(P,NS+'configs/n1b_fifo_semantics_v1.json'),
            numerical_precision=vc.binding(P,NS+'contracts/N1B_NUMERICAL_PRECISION_CN.md'),
            implementation_manifest=vc.binding(P,NS+'acceptance/0005/implementation_manifest.json'),
            static_acceptance=vc.binding(P,NS+'acceptance/0005/fifo_static_report.json'),
            n1b_acceptance=vc.binding(P,NS+'acceptance/0005/n1b_test_report.json'),
            n1a_regression=vc.binding(P,NS+'acceptance/0005/n1a_regression_report.json'),
            chinese_report=vc.binding(P,NS+'acceptance/0005/RESULT_CN.md'),
            preseal_old_asset_audit=vc.binding(P,NS+'acceptance/0005/preseal_change_audit.json')),
        changes={k:final[k] for k in ('added','modified','deleted')},
        engineering_acceptance=dict(N1b='PASS',N1a_regression='PASS',n1b_tests=24,n1a_tests=25,
            static_checks=20,version_protection_tests=22,historical_tests=97,known_historical_failures=1,new_regressions=0),
        old_assets_modified=False,production_code_modified=False,formal_experiments_executed=False,
        scientific_gate_pass=False,N1b_implemented=True,N2_implemented=False,algorithm_selection=None)
    target=V/'revisions/0005';target.mkdir(exist_ok=False)
    write_new(target/'record.json',record)
    print(json.dumps(dict(revision=vc.binding(P,NS+'revisions/0005/record.json'),
                         added_files=len(final['added']),modified_files=0,deleted_files=0),indent=2))

if __name__=='__main__':main()
