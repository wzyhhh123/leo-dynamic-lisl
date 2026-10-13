"""Append a README-only revision, keeping all engineering bindings unchanged."""
import importlib.util,json,re,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
NS='research_versions/dynamic_k_v1/'
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='f58cc5eb037eaf6ee804c9aa1c5ec54f38894d00ca0d715f8b7baae8a47e06db'
README=NS+'README_CN.md'
spec=importlib.util.spec_from_file_location('readme_integrity',V/'tools/version_control.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
sys.path[:0]=[str(V),str(P/'src')]
from runtime.n3_baselines import N3EvidenceBinding

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')

def main():
    loaded=vc.load_expected(P,ORIGIN,PARENT)
    version,baseline,expected,latest,parent,reserved=loaded
    assert latest['revision_id']=='0007'
    before=vc.file_info(A/'README_CN.before.md')
    assert before==expected[README],'README_BEFORE_SNAPSHOT_MISMATCH'
    original=vc.read_json(V/'acceptance/0007/implementation_manifest_attempt02.json')
    assert not any(row['path']==README for row in original['files']),'README_IS_FROZEN_IMPLEMENTATION_INPUT'
    guard=N3EvidenceBinding(P,NS+'acceptance/0007/implementation_manifest_attempt02.json',
                           'dbc7e0d54d6d9bb864ec216a0b7c6cd1b86ec6353ed3ab41a3c3c64b471b9129')
    pre=guard.verify()
    path=vc.safe_path(P,README);text=path.read_text(encoding='utf-8')
    links=re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',text)
    checked=[]
    for link in links:
        assert not link.startswith(('http:','https:','file:'))
        relative=NS+link.split('#',1)[0]
        target=vc.safe_path(P,relative);assert target.is_file(),'README_LINK_MISSING:'+link
        checked.append(relative)
    summary=vc.read_json(V/'acceptance/0007/attempt02/acceptance_summary.json')
    assert summary['status']=='PASS' and summary['N3_tests']==20
    config=vc.read_json(V/'configs/n3_baseline_semantics_v1.json')
    assert all(value is None for value in config['scientific_parameters'].values())
    assert all(config[key] is None for key in ('decision_period_s','search_budget','maximum_concurrent_actions'))
    assert vc.file_info(path)!=before,'NO_README_UPDATE'
    write_new(A/'documentation_update.json',dict(status='PASS_DOCUMENTATION_CHECKS_ONLY',
        client_update_date_asia_shanghai='2026-10-12',version_id='dynamic_k_v1',revision_id='0008',
        pre_edit_full_verification=dict(status='PASS',revision_id='0007',version_record_sha256=ORIGIN,
            revision_record_sha256=PARENT,verified_file_count=5948,excluded_file_count=202,
            evidence_source='actual read-only verify execution output before modifying README in this conversation'),
        README_before=before,README_after=vc.file_info(path),link_count=len(checked),checked_local_links=checked,
        implementation_binding_before=pre,implementation_binding_after=guard.verify(),
        retained_N3_acceptance=vc.binding(P,NS+'acceptance/0007/attempt02/acceptance_summary.json'),
        tests_rerun=False,simulation_executed=False,training_executed=False,
        formal_experiments_executed=False,scientific_gate_pass=False))
    actual,excluded=vc.inventory(P,progress=lambda value:print(json.dumps(dict(progress=value)),flush=True))
    for item in reserved:actual.pop(item,None)
    diff=vc.differences(expected,actual)
    assert not diff['deleted'] and not diff['possible_renames']
    assert diff['modified']==[dict(path=README,before=before,after=vc.file_info(path))],'UNEXPECTED_EXISTING_ASSET_CHANGE'
    assert all(row['path'].startswith(NS+'acceptance/0008/') for row in diff['added']),'UNEXPECTED_NEW_ASSET'
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded
    assert guard.verify()==pre
    write_new(A/'preseal_change_audit.json',dict(status='PASS_README_ONLY_CHANGE',
        scope='COMPLETE_RAW_BYTE_OLD_AND_VERSION_ASSET_AUDIT',origin_sha256=ORIGIN,parent_sha256=PARENT,
        legacy_asset_changes=[],engineering_source_contract_configuration_and_evidence_changes=[],
        changes_before_audit_file_creation=diff,excluded_files=excluded,excluded_file_count=len(excluded),
        scientific_gate_pass=False))
    actual.update({p.relative_to(P).as_posix():vc.file_info(p) for p in A.iterdir() if p.is_file()})
    final=vc.differences(expected,actual)
    assert final['modified']==diff['modified'] and not final['deleted'] and not final['possible_renames']
    assert all(row['path'].startswith(NS+'acceptance/0008/') for row in final['added'])
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded and guard.verify()==pre
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0008',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='README navigation and current N0-N3 status update only; no scientific or implementation change.',
        authorization=dict(actor='human_user',source='current_conversation_user_request',
            scope='CURRENT_README_DOCUMENTATION_UPDATE_ONLY',request='\u66f4\u65b0\u4e00\u4e0b\u5f53\u524dreadme'),
        bindings=dict(baseline_seal=version['baseline_seal'],contract=latest['bindings']['contract'],
            configuration=latest['bindings']['configuration'],implementation_manifest=latest['bindings']['implementation_manifest'],
            updated_README=vc.binding(P,README),
            prior_README_snapshot=vc.binding(P,NS+'acceptance/0008/README_CN.before.md'),
            documentation_validation=vc.binding(P,NS+'acceptance/0008/documentation_update.json'),
            old_asset_audit=vc.binding(P,NS+'acceptance/0008/preseal_change_audit.json')),
        changes={key:final[key] for key in ('added','modified','deleted')},
        documentation_only=True,documentation_validation='PASS',N3_implemented=True,N4_implemented=False,
        engineering_acceptance_not_rerun=True,legacy_assets_modified=False,production_code_modified=False,
        formal_experiments_executed=False,scientific_gate_pass=False,algorithm_selection=None)
    directory=V/'revisions/0008';directory.mkdir(exist_ok=False);write_new(directory/'record.json',record)
    print(json.dumps(dict(revision=vc.binding(P,NS+'revisions/0008/record.json'),
        added_files=len(final['added']),modified_files=len(final['modified']),deleted_files=0,link_count=len(checked)),indent=2),flush=True)
if __name__=='__main__':main()
