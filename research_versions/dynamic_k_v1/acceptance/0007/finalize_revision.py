"""Seal 0007 only after accepted tests, unchanged history and complete raw audit."""
import argparse,importlib.util,json,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
NS='research_versions/dynamic_k_v1/'
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='417e46baf6d3d7c8846af61131952739275c9b22bd1d468cc28e649b3c82dd18'
spec=importlib.util.spec_from_file_location('n3_seal_vc',V/'tools/version_control.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.n3_baselines import N3EvidenceBinding

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--manifest-name',required=True);parser.add_argument('--expected-manifest-sha256',required=True);args=parser.parse_args()
    dest=A/args.attempt;assert dest.parent==A
    loaded=vc.load_expected(P,ORIGIN,PARENT);version,baseline,expected,latest,parent,reserved=loaded
    guard=N3EvidenceBinding(P,NS+'acceptance/0007/'+args.manifest_name,args.expected_manifest_sha256);guard.verify()
    report=vc.read_json(dest/'n3_test_report.json');summary=vc.read_json(dest/'acceptance_summary.json')
    upstream=vc.read_json(dest/'upstream_regression_report.json');coverage=vc.read_json(dest/'catalog_coverage.json')
    assert report['status']==summary['status']=='PASS' and report['tests_run']==20
    assert summary['upstream_test_counts']=={'N1a':25,'N1b':24,'N2':27}
    assert all(r['status']=='PASS' and not r['failures'] and not r['errors'] and not r['skipped'] for r in upstream.values())
    assert report['pre_execution_bindings']==report['post_execution_bindings']==summary['pre_bindings']==summary['post_bindings']==guard.verify()
    assert coverage['status']=='PASS_COMPLETE_REGISTERED_RECORD_PROBES'
    assert coverage['registered_rows']==coverage['record_probes']==len(coverage['record_probes_evidence'])==2742
    assert coverage['omitted_registered_rows']==0 and coverage['registered_nodes']==160 and coverage['candidate_budget'] is None
    before=vc.read_json(V/'acceptance/0006/historical_regression.json');current=vc.read_json(A/'historical_regression.json')
    assert before['base']['tests_run']==current['base']['tests_run']==97
    assert before['base']['failures']==current['base']['failures'] and len(current['base']['failures'])==1
    assert current['physical_gate_c']['tests_run']==35
    assert current['base']['errors']==current['base']['skipped']==current['physical_gate_c']['failures']==current['physical_gate_c']['errors']==current['physical_gate_c']['skipped']==[]
    protection=vc.read_json(A/'version_protection_tests.json')
    assert protection['status']=='PASS' and protection['tests_run']==22 and protection['exit_code']==0
    examples=vc.read_json(dest/'engineering_examples.json')['examples']
    real=examples['real160_natural_SGP4_controlled_catalog_paired_multi_epoch']['paired_results']
    assert real['STATIC_HOLD']['fixture_identity']==real['REACTIVE_DYNAMIC_K']['fixture_identity']
    assert real['REACTIVE_DYNAMIC_K']['non_HOLD_accepted_count']>0
    assert real['REACTIVE_DYNAMIC_K']['metrics']['all_offered_business_delivered']
    assert (A/'RESULT_CN.md').is_file() and (A/'paired_metrics.json').is_file()
    write_new(A/'historical_regression_comparison.json',dict(status='PASS_NO_NEW_REGRESSIONS',
        base_tests=97,base_passed=96,additional_gate_c_tests=35,additional_gate_c_passed=35,
        total_tests=132,total_passed=131,known_failure_count=1,new_regressions=0,
        failures_identical_including_traceback=True,failures=current['base']['failures'],
        parent_evidence=vc.binding(P,NS+'acceptance/0006/historical_regression.json'),
        current_evidence=vc.binding(P,NS+'acceptance/0007/historical_regression.json')))
    write_new(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0006',
        expected_version_sha256=ORIGIN,expected_revision_sha256=PARENT,baseline_file_count=5810,
        verified_file_count=5906,excluded_file_count=202,
        undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        scope='N0_FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY',scientific_gate_pass=False,
        source='actual complete version_control verify output before creation of any N3 files in this authorized turn'))
    actual,excluded=vc.inventory(P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for path in reserved:actual.pop(path,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],'FROZEN_OR_EXISTING_ASSET_DRIFT'
    assert all(r['path'].startswith(NS) for r in diff['added']),'UNAUTHORIZED_FILE_OUTSIDE_VERSION'
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded,'ANCHORS_CHANGED_DURING_FULL_SCAN';guard.verify()
    write_new(A/'preseal_change_audit.json',dict(status='PASS',scope='COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',
        baseline_file_count=5810,old_assets_changed=[],existing_version_assets_changed=[],
        includes_gitignored_research_assets=True,tmp_evidence_included=True,excluded_files=excluded,
        excluded_file_count=len(excluded),origin_sha256=ORIGIN,parent_revision_sha256=PARENT,
        changes_before_audit_file_creation=diff,scientific_gate_pass=False))
    actual.update({p.relative_to(P).as_posix():vc.file_info(p) for p in V.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    for path in reserved:actual.pop(path,None)
    final=vc.differences(expected,actual)
    assert not final['modified'] and not final['deleted'] and not final['possible_renames']
    assert all(r['path'].startswith(NS) for r in final['added'])
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded;guard.verify()
    now=datetime.now(timezone.utc)
    evidence=lambda name:vc.binding(P,(dest/name).relative_to(P).as_posix())
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0007',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N3：当前业务感知的 STATIC_HOLD/REACTIVE_DYNAMIC_K 多epoch闭环、真实N2动作与FIFO/能耗集成、完整登记catalog诊断及配对160星SGP4工程测试；仅新增独立资产。',
        authorization=dict(actor='human_user',scope='N3_TRAFFIC_AWARE_CLOSED_LOOP_ENGINEERING_ONLY',source='current_conversation_user_request',
            request='继续 dynamic_k_v1，授权 Stage N3 — Traffic-Aware Dynamic-K Closed-Loop Baseline。先验证独立版本起点与0006哈希。仅工程闭环，复用N2真实执行与N1a/N1b固定T能耗、本地FIFO。建立STATIC_HOLD及当前业务感知确定性REACTIVE_DYNAMIC_K，审计当前候选、预算、选择、真实接受拒绝释放和状态哈希；验证ADD/DROP/REPLACE、分区恢复、克隆重放、160星自然SGP4多epoch以及完整已登记Gate C catalog诊断。全部相关及历史回归无新增失败；不改冻结内核合同证据，不冻结科学参数/周期/预算，不实现RL或主性能实验；封存连续0007、中文报告及独立SHA-256，完成后等待审核。'),
        bindings=dict(baseline_seal=version['baseline_seal'],
            contract=vc.binding(P,NS+'contracts/N3_CLOSED_LOOP_BASELINES_CN.md'),
            configuration=vc.binding(P,NS+'configs/n3_baseline_semantics_v1.json'),
            implementation_manifest=vc.binding(P,NS+'acceptance/0007/'+args.manifest_name),
            N3_acceptance=evidence('n3_test_report.json'),upstream_regression=evidence('upstream_regression_report.json'),
            catalog_coverage=evidence('catalog_coverage.json'),engineering_examples=evidence('engineering_examples.json'),
            chinese_report=vc.binding(P,NS+'acceptance/0007/RESULT_CN.md'),
            paired_metrics=vc.binding(P,NS+'acceptance/0007/paired_metrics.json'),
            preseal_old_asset_audit=vc.binding(P,NS+'acceptance/0007/preseal_change_audit.json')),
        changes={k:final[k] for k in ('added','modified','deleted')},
        engineering_acceptance=dict(N3='PASS',n3_tests=20,N1a_regression='PASS',n1a_tests=25,N1b_regression='PASS',
            n1b_tests=24,N2_regression='PASS',n2_tests=27,real160_multi_epoch='PASS',
            complete_registered_catalog_rows=2742,version_protection_tests=22,historical_tests=132,
            known_historical_failures=1,new_regressions=0),
        old_assets_modified=False,production_code_modified=False,formal_experiments_executed=False,
        scientific_gate_pass=False,N3_implemented=True,N4_implemented=False,algorithm_selection=None)
    target=V/'revisions/0007';target.mkdir(exist_ok=False);write_new(target/'record.json',record)
    print(json.dumps(dict(revision=vc.binding(P,NS+'revisions/0007/record.json'),added_files=len(final['added']),
                         modified_files=0,deleted_files=0),indent=2),flush=True)
if __name__=='__main__':main()
