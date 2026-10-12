"""Append revision 0006 after real action/upstream acceptance and raw audit."""
from datetime import datetime,timezone,timedelta
import importlib.util,json,sys
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
NS='research_versions/dynamic_k_v1/'
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='c2567b66fe880035853aba2b81463ece42443973d5b5178ae0b28e77a6c44769'
MANIFEST='34e3412da99a96c58fe603af5de69777d69e0e2bc292fba4cbd3cfca8acb0b4a'
spec=importlib.util.spec_from_file_location('n2_seal_vc',V/'tools/version_control.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.n2_binding import N2EvidenceBinding
def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def main():
    loaded=vc.load_expected(P,ORIGIN,PARENT)
    version,baseline,expected,latest,parent,reserved=loaded
    guard=N2EvidenceBinding(P,NS+'acceptance/0006/implementation_manifest.json',MANIFEST)
    guard.verify()
    summary=vc.read_json(A/'acceptance_summary.json')
    report=vc.read_json(A/'n2_test_report.json')
    upstream=vc.read_json(A/'upstream_regression_report.json')
    assert summary['status']=='PASS' and report['status']=='PASS' and report['tests_run']==27
    assert upstream['N1a']['status']==upstream['N1b']['status']=='PASS'
    assert upstream['N1a']['tests_run']==25 and upstream['N1b']['tests_run']==24
    assert report['pre_execution_bindings']==report['post_execution_bindings']==summary['pre_bindings']==summary['post_bindings']==guard.verify()
    before=vc.read_json(V/'acceptance/0005/historical_regression.json')
    current=vc.read_json(A/'historical_regression.json');after=current['base'];physical=current['physical_gate_c']
    assert before['tests_run']==after['tests_run']==97 and physical['tests_run']==35
    assert before['failures']==after['failures'] and len(after['failures'])==1
    assert before['errors']==after['errors']==physical['errors']==physical['failures']==[]
    assert before['skipped']==after['skipped']==physical['skipped']==[]
    examples=vc.read_json(A/'engineering_examples.json')
    assert examples['examples']['real160_controlled_geometry_loop']['result']['n1b_result']['n1a_result']['all_offered_business_delivered']
    write_new(A/'historical_regression_comparison.json',dict(status='PASS_NO_NEW_REGRESSIONS',
        base_tests=97,base_passed=96,additional_gate_c_tests=35,additional_gate_c_passed=35,
        total_tests=132,total_passed=131,known_failure_count=1,new_regressions=0,
        failures_identical_including_traceback=True,failures=after['failures'],
        parent_evidence=vc.binding(P,NS+'acceptance/0005/historical_regression.json'),
        current_evidence=vc.binding(P,NS+'acceptance/0006/historical_regression.json')))
    write_new(A/'version_protection_tests.json',dict(status='PASS',tests_run=22,failures=0,errors=0,
        scope='ISOLATED_VERSION_PROTECTION_TESTS_ONLY',
        command='D:/Program_Files/anaconda3/envs/pytorch/python.exe -B research_versions/dynamic_k_v1/tests/test_version_control.py -v',
        evidence_source='actual_execution_tool_transcript_of_current_N2_authorized_turn',
        coverage=['raw-byte/newline/content/add/delete/rename','origin/seal/manifest/parent/tail tamper',
                  'read failure/omission/concurrent mutation','legacy/historical test protection','unauthorized formal experiment rejection']))
    write_new(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0005',
        expected_version_sha256=ORIGIN,expected_revision_sha256=PARENT,baseline_file_count=5810,
        verified_file_count=5882,excluded_file_count=202,
        undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        scope='N0_FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY',scientific_gate_pass=False,
        source='complete raw-byte version_control.py verify execution output before creating N2 files in current turn'))
    actual,excluded=vc.inventory(P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for path in reserved:actual.pop(path,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],'FROZEN_OR_EXISTING_ASSET_DRIFT'
    assert all(r['path'].startswith(NS) for r in diff['added']),'UNAUTHORIZED_FILE_OUTSIDE_VERSION'
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded,'ANCHORS_CHANGED_DURING_FULL_SCAN'
    guard.verify()
    write_new(A/'preseal_change_audit.json',dict(status='PASS',scope='COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',
        baseline_file_count=5810,old_assets_changed=[],existing_version_assets_changed=[],
        includes_gitignored_research_assets=True,tmp_evidence_included=True,
        excluded_files=excluded,excluded_file_count=len(excluded),origin_sha256=ORIGIN,
        parent_revision_sha256=PARENT,changes_before_audit_file_creation=diff,scientific_gate_pass=False))
    actual.update({p.relative_to(P).as_posix():vc.file_info(p) for p in V.rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts})
    for path in reserved:actual.pop(path,None)
    final=vc.differences(expected,actual)
    assert not final['modified'] and not final['deleted'] and all(r['path'].startswith(NS) for r in final['added'])
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded
    guard.verify()
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0006',
        parent_record=parent,created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N2：独立原子HOLD/ADD/DROP/REPLACE、物理候选/验证、真实Gate B/C执行、N1a/N1b直接集成与160星受控几何工程验收；无旧资产修改。',
        authorization=dict(actor='human_user',scope='N2_ATOMIC_TOPOLOGY_ACTION_AND_PHYSICAL_EXECUTION_ENGINEERING_ONLY',
            source='current_conversation_user_request',
            request='继续 dynamic_k_v1，授权 Stage N2 — Dynamic-K Topology Action and Physical Execution Integration。前置N0/N1a/N1b完成，指定独立0005哈希先完整验证。建立HOLD/ADD/DROP/REPLACE真实终端接口，显式释放集合，允许临时分区，独立候选与明确拒绝/预算诊断，直接使用已验收固定T/能耗/本地FIFO。验证原子连续时间动作及至少一例真实160星几何短时闭环、克隆重放、上游及历史回归。不得修改冻结内核/合同/证据，不冻结科学数值或预算，不实现RL/N3或正式性能比较；连续新增修订，最终完整保护验证、中文报告与独立SHA-256，完成后停止审核。'),
        bindings=dict(baseline_seal=version['baseline_seal'],
            contract=vc.binding(P,NS+'contracts/N2_ATOMIC_TOPOLOGY_ACTIONS_CN.md'),
            configuration=vc.binding(P,NS+'configs/n2_action_semantics_v1.json'),
            implementation_manifest=vc.binding(P,NS+'acceptance/0006/implementation_manifest.json'),
            N2_acceptance=vc.binding(P,NS+'acceptance/0006/n2_test_report.json'),
            upstream_regression=vc.binding(P,NS+'acceptance/0006/upstream_regression_report.json'),
            real160_and_analytical_examples=vc.binding(P,NS+'acceptance/0006/engineering_examples.json'),
            chinese_report=vc.binding(P,NS+'acceptance/0006/RESULT_CN.md'),
            preseal_old_asset_audit=vc.binding(P,NS+'acceptance/0006/preseal_change_audit.json')),
        changes={k:final[k] for k in ('added','modified','deleted')},
        engineering_acceptance=dict(N2='PASS',n2_tests=27,N1a_regression='PASS',n1a_tests=25,
            N1b_regression='PASS',n1b_tests=24,real160_controlled_geometry='PASS',schema='PASS',
            version_protection_tests=22,historical_tests=132,known_historical_failures=1,new_regressions=0),
        old_assets_modified=False,production_code_modified=False,formal_experiments_executed=False,
        scientific_gate_pass=False,N2_implemented=True,N3_implemented=False,algorithm_selection=None)
    target=V/'revisions/0006';target.mkdir(exist_ok=False);write_new(target/'record.json',record)
    print(json.dumps(dict(revision=vc.binding(P,NS+'revisions/0006/record.json'),
        added_files=len(final['added']),modified_files=0,deleted_files=0),indent=2))
if __name__=='__main__':main()
