"""Generate an additive, one-path documentation reader; preserve original bytes."""
import hashlib,json
from pathlib import Path
V=Path(__file__).absolute().parents[2];P=V.parents[1];A=Path(__file__).parent
BASE_SHA='c740401a75c2b43063957db3ef9dc4575098f3f7bb4bfadfd3f16d40739e04b5'
EXTRA='''
# Single authorized root README change; no legacy exclusion or root broadening.
README_PARENT_SHA = '0ab864c1bc8eaf8b3e746cf68df2e32f2924b91a07c316c25f3bc0d220b9bbbc'
README_BEFORE_SHA = '905a689bdfc027fd904c5cbe8f1bbd3a907232b3a9f0e47349bb3119f8a7b72d'
ORIGINAL_VERIFIER_SHA = 'c740401a75c2b43063957db3ef9dc4575098f3f7bb4bfadfd3f16d40739e04b5'
DOC_POLICY_PATH = NAMESPACE + '/contracts/root_readme_documentation_exception_v1.json'
DOC_VERIFIER_PATH = NAMESPACE + '/tools/version_control_readme_v1.py'
DOC_SCOPE = 'PROJECT_ROOT_README_DOCUMENTATION_UPDATE_ONLY'

def documentation_policy():
    return dict(schema='dynamic_k_root_readme_documentation_exception_v1',version_id=VERSION_ID,
        revision_id='0009',parent_revision_sha256=README_PARENT_SHA,legacy_path='README.md',
        allowed_operation='modified',legacy_before_sha256=README_BEFORE_SHA,
        original_verifier_sha256=ORIGINAL_VERIFIER_SHA,
        scope='ONE_EXPLICITLY_AUTHORIZED_PROJECT_README_UPDATE',
        baseline_or_history_rewrite_allowed=False,production_or_science_change_allowed=False)

def authorized_project_readme(root,record,index,operation,change):
    if change['path'] != 'README.md' or index != 9:
        return False
    require(operation == 'modified','README_ONLY_MODIFICATION_ALLOWED')
    auth=record.get('authorization',{})
    require(auth.get('actor')=='human_user' and auth.get('scope')==DOC_SCOPE
        and auth.get('named_requested_file')=='README.md','README_EXPLICIT_FILE_AUTHORIZATION_REQUIRED')
    require(record['parent_record']['sha256']==README_PARENT_SHA,'README_PARENT_ANCHOR_MISMATCH')
    require(change['before']['sha256']==README_BEFORE_SHA,'README_BASELINE_HASH_MISMATCH')
    require(record.get('documentation_only') is True and record.get('production_code_modified') is False
        and record.get('scientific_gate_pass') is False and record.get('formal_experiments_executed') is False,
        'README_DOCUMENTATION_ONLY_REQUIRED')
    ref=record['bindings']['root_readme_policy']
    require(ref['path']==DOC_POLICY_PATH,'README_POLICY_PATH_MISMATCH')
    policy=read_bound_json(root,ref,'dynamic_k_root_readme_documentation_exception_v1')
    require(policy==documentation_policy(),'README_POLICY_SCOPE_CHANGED')
    original=record['bindings']['original_version_verifier']
    require(original['path']==NAMESPACE+'/tools/version_control.py'
        and original['sha256']==ORIGINAL_VERIFIER_SHA and binding(root,original['path'])==original,
        'README_ORIGINAL_VERIFIER_CHANGED')
    verifier=record['bindings']['version_verifier']
    require(verifier['path']==DOC_VERIFIER_PATH and binding(root,verifier['path'])==verifier,
        'README_NEW_VERIFIER_BINDING_MISMATCH')
    old=read_json(safe_path(root,record['parent_record']['path']))
    require(all(record['bindings'][k]==old['bindings'][k] for k in ('contract','configuration')),
        'README_SCIENTIFIC_BINDINGS_CHANGED')
    changes=record['changes']
    require(not changes['deleted'] and {r['path'] for r in changes['modified']} <=
        {'README.md',NAMESPACE+'/README_CN.md'},'README_OTHER_ASSET_CHANGE_REJECTED')
    allowed={DOC_POLICY_PATH,DOC_VERIFIER_PATH,NAMESPACE+'/contracts/ROOT_README_DOCUMENTATION_CHANGE_CN.md',
             NAMESPACE+'/tests/test_root_readme_policy.py'}
    require(all(r['path'] in allowed or r['path'].startswith(NAMESPACE+'/acceptance/0009/')
        for r in changes['added']),'README_UNAUTHORIZED_ADDED_ASSET')
    return True

'''
OLD='require(in_version or path_changed.startswith(LEGACY_CHANGE_ROOTS),'
NEW='require(in_version or path_changed.startswith(LEGACY_CHANGE_ROOTS) or\n                        authorized_project_readme(root, record, index, operation, change),'

def main():
    base=V/'tools/version_control.py';raw=base.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==BASE_SHA
    source=raw.decode('utf-8');assert source.count(OLD)==1 and source.count('def load_expected(')==1
    updated=source.replace('def load_expected(',EXTRA+'def load_expected(',1).replace(OLD,NEW,1)
    target=V/'tools/version_control_readme_v1.py'
    with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write(updated)
    restored=updated.replace(EXTRA,'',1).replace(NEW,OLD,1)
    assert restored==source,'UNEXPECTED_ORIGINAL_VERIFIER_SEMANTIC_CHANGE'
    audit=dict(status='PASS_EXACT_ADDITIVE_TRANSFORMATION',original_sha256=BASE_SHA,
        new_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),original_source_unchanged=True,
        original_exclusion_policy_and_change_roots_unchanged=True,
        changes=['add authorized_project_readme and fixed policy constants','extend one path authorization require'],
        reverting_only_these_additions_reproduces_original_source=True)
    with (A/'verifier_source_audit.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(audit,stream,indent=2);stream.write('\n')
    print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
