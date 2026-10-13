"""Seal requested root README update with exact-path documentation addendum."""
import importlib.util,json,re,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
NS='research_versions/dynamic_k_v1/'
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='0ab864c1bc8eaf8b3e746cf68df2e32f2924b91a07c316c25f3bc0d220b9bbbc'
spec=importlib.util.spec_from_file_location('doc_addendum_vc',V/'tools/version_control_readme_v1.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
sys.path[:0]=[str(V),str(P/'src')]
from runtime.n3_baselines import N3EvidenceBinding

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')

def main():
    loaded=vc.load_expected(P,ORIGIN,PARENT)
    version,baseline,expected,latest,parent,reserved=loaded
    assert latest['revision_id']=='0008'
    before={'README.md':vc.file_info(A/'PROJECT_README.before.md'),NS+'README_CN.md':vc.file_info(A/'VERSION_README.before.md')}
    assert all(expected[path]==info for path,info in before.items())
    source=vc.read_json(A/'verifier_source_audit.json')
    assert source['status']=='PASS_EXACT_ADDITIVE_TRANSFORMATION'
    assert vc.file_info(V/'tools/version_control.py')['sha256']==source['original_sha256']==vc.ORIGINAL_VERIFIER_SHA
    assert vc.file_info(V/'tools/version_control_readme_v1.py')['sha256']==source['new_sha256']
    assert vc.read_json(P/vc.DOC_POLICY_PATH)==vc.documentation_policy()
    tests=vc.read_json(A/'protection_test_report.json')
    assert tests['status']=='PASS' and tests['tests_run']==32 and tests['failures']==tests['errors']==tests['skipped']==[]
    guard=N3EvidenceBinding(P,NS+'acceptance/0007/implementation_manifest_attempt02.json',
        'dbc7e0d54d6d9bb864ec216a0b7c6cd1b86ec6353ed3ab41a3c3c64b471b9129')
    bindings=guard.verify()
    checked=[]
    for document in (P/'README.md',V/'README_CN.md'):
        links=re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',document.read_text(encoding='utf-8'))
        for link in links:
            target=(document.parent/link.split('#',1)[0]).resolve()
            assert target.is_relative_to(P) and target.is_file(),'README_LINK_MISSING:'+link
            vc.safe_path(P,target.relative_to(P).as_posix())
            checked.append(dict(document=document.relative_to(P).as_posix(),target=target.relative_to(P).as_posix()))
    assert vc.file_info(P/'README.md')==vc.file_info(A/'PROJECT_README.after.md')
    write_new(A/'documentation_update.json',dict(status='PASS_DOCUMENTATION_AND_PROTECTION_CHECKS_ONLY',
        pre_edit_full_verification=dict(status='PASS',revision_id='0008',version_record_sha256=ORIGIN,
            revision_record_sha256=PARENT,verified_file_count=5952,excluded_file_count=202,
            source='actual original read-only verifier output before any 0009 files or README changes'),
        client_date_asia_shanghai='2026-10-12',changes=[dict(path=p,before=b,after=vc.file_info(P/p)) for p,b in before.items()],
        local_links_count=len(checked),checked_local_links=checked,unchanged_N3_implementation_bindings=bindings,
        protection_tests=32,engineering_tests_rerun=False,simulation_executed=False,training_executed=False,
        original_verifier_modified=False,baseline_modified=False,formal_experiments_executed=False,scientific_gate_pass=False))
    actual,excluded=vc.inventory(P,progress=lambda value:print(json.dumps(dict(progress=value)),flush=True))
    for p in reserved:actual.pop(p,None)
    diff=vc.differences(expected,actual)
    assert not diff['deleted'] and not diff['possible_renames']
    assert {r['path'] for r in diff['modified']}==set(before)
    assert all(row['before']==before[row['path']] and row['after']==vc.file_info(P/row['path']) for row in diff['modified'])
    allowed={vc.DOC_POLICY_PATH,vc.DOC_VERIFIER_PATH,NS+'contracts/ROOT_README_DOCUMENTATION_CHANGE_CN.md',NS+'tests/test_root_readme_policy.py'}
    assert all(r['path'] in allowed or r['path'].startswith(NS+'acceptance/0009/') for r in diff['added'])
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded and guard.verify()==bindings
    write_new(A/'preseal_change_audit.json',dict(status='PASS_ONLY_AUTHORIZED_README_CHANGES',
        scope='FULL_RESEARCH_FILE_RAW_BYTE_AUDIT_INCLUDING_IGNORED_OUTPUTS_AND_TMP',
        before_revision_sha256=PARENT,version_origin_sha256=ORIGIN,baseline_file_count=5810,
        old_source_tests_contracts_manifests_data_outputs_changed=[],
        authorized_existing_document_changes=diff['modified'],added_files_before_this_audit=diff['added'],
        excluded_files=excluded,excluded_file_count=len(excluded),scientific_gate_pass=False))
    actual.update({p.relative_to(P).as_posix():vc.file_info(p) for p in A.iterdir() if p.is_file()})
    final=vc.differences(expected,actual)
    assert final['modified']==diff['modified'] and not final['deleted'] and not final['possible_renames']
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded and guard.verify()==bindings
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0009',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='Explicitly requested project README update and exact-path documentation protection addendum; engineering/science unchanged.',
        authorization=dict(actor='human_user',scope=vc.DOC_SCOPE,named_requested_file='README.md',
            source='current_conversation_user_request',
            request='\u8fd9\u4e2areadme\u4e5f\u5f97\u66f4\u65b0\u5427',
            user_named_absolute_file='D:/Document/leo_routing_attitude/dynamic_lisl_v2/README.md'),
        bindings=dict(baseline_seal=version['baseline_seal'],contract=latest['bindings']['contract'],
            configuration=latest['bindings']['configuration'],implementation_manifest=latest['bindings']['implementation_manifest'],
            root_readme_policy=vc.binding(P,vc.DOC_POLICY_PATH),version_verifier=vc.binding(P,vc.DOC_VERIFIER_PATH),
            original_version_verifier=vc.binding(P,NS+'tools/version_control.py'),
            project_README=vc.binding(P,'README.md'),version_README=vc.binding(P,NS+'README_CN.md'),
            policy_contract=vc.binding(P,NS+'contracts/ROOT_README_DOCUMENTATION_CHANGE_CN.md'),
            documentation_validation=vc.binding(P,NS+'acceptance/0009/documentation_update.json'),
            protection_tests=vc.binding(P,NS+'acceptance/0009/protection_test_report.json'),
            old_asset_audit=vc.binding(P,NS+'acceptance/0009/preseal_change_audit.json')),
        changes={key:final[key] for key in ('added','modified','deleted')},
        documentation_only=True,N3_implemented=True,N4_implemented=False,production_code_modified=False,
        engineering_source_and_evidence_modified=False,formal_experiments_executed=False,scientific_gate_pass=False,
        documentation_validation='PASS',protection_tests=32,engineering_acceptance_not_rerun=True,algorithm_selection=None)
    # Check the exact policy before creating any immutable new revision directory.
    root_change=next(r for r in final['modified'] if r['path']=='README.md')
    assert vc.authorized_project_readme(P,record,9,'modified',root_change)
    folder=V/'revisions/0009';folder.mkdir(exist_ok=False);write_new(folder/'record.json',record)
    print(json.dumps(dict(revision=vc.binding(P,NS+'revisions/0009/record.json'),
        new_verifier=vc.binding(P,vc.DOC_VERIFIER_PATH),added_files=len(final['added']),modified_files=2,
        deleted_files=0,local_links=len(checked)),indent=2),flush=True)
if __name__=='__main__':main()
