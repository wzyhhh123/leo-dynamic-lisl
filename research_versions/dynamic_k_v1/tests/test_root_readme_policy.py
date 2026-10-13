"""Original 22 controls plus exact-path README exception integration tests."""
import importlib.util,json,sys
from pathlib import Path
from unittest.mock import patch
V=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

vc=load('readme_v1_reader',V/'tools/version_control_readme_v1.py')
original=load('original_v1_reader',V/'tools/version_control.py')
base_tests=load('unchanged_n0_controls',V/'tests/test_version_control.py')
base_tests.vc=vc
write_json=base_tests.write_json

class RootReadmeControls(base_tests.N0IntegrityControls):
    def readme_fixture(self):
        # All rewrites here are inside isolated disposable fixture directories.
        root=self.root;ns=self.ns
        (root/'README.md').write_bytes((V/'acceptance/0009/PROJECT_README.before.md').read_bytes())
        self.legacy['README.md']=vc.file_info(root/'README.md')
        baseline=root/self.baseline_relative
        manifest=vc.read_json(baseline/'files.json');manifest.update(files=self.legacy,
            file_count=len(self.legacy),total_bytes=sum(x['byte_count'] for x in self.legacy.values()))
        write_json(baseline/'files.json',manifest)
        seal=vc.read_json(baseline/'seal.json');seal['files']['files.json']=vc.file_info(baseline/'files.json')
        write_json(baseline/'seal.json',seal);self.seal=vc.binding(root,self.baseline_relative+'/seal.json')
        (ns/'tools').mkdir()
        for name in ('version_control.py','version_control_readme_v1.py'):(ns/'tools'/name).write_bytes((V/'tools'/name).read_bytes())
        actual,_=vc.inventory(root)
        actual.pop(vc.NAMESPACE+'/version_record.json');actual.pop(vc.NAMESPACE+'/revisions/0001/record.json')
        initial=self.record('0001',None,vc.differences(self.legacy,actual))
        write_json(ns/'revisions/0001/record.json',initial)
        self.revision=vc.binding(root,vc.NAMESPACE+'/revisions/0001/record.json')
        version=vc.read_json(ns/'version_record.json');version.update(baseline_seal=self.seal,initial_revision=self.revision,
            genesis_contract=initial['bindings']['contract'],genesis_configuration=initial['bindings']['configuration'])
        write_json(ns/'version_record.json',version);self.version_sha=vc.file_info(ns/'version_record.json')['sha256']
        for index in range(2,9):
            record=self.record('%04d'%index,self.revision,dict(added=[],modified=[],deleted=[]))
            path=vc.NAMESPACE+'/revisions/%04d/record.json'%index;write_json(root/path,record)
            self.revision=vc.binding(root,path)
        self.expected8=vc.load_expected(root,self.version_sha,self.revision['sha256'])[2]
        patched=patch.object(vc,'README_PARENT_SHA',self.revision['sha256']);patched.start();self.addCleanup(patched.stop)
        policy=root/vc.DOC_POLICY_PATH;write_json(policy,vc.documentation_policy())
        (root/'README.md').write_bytes(b'Updated navigation\n')
        actual,_=vc.inventory(root)
        for path in list(actual):
            if path==vc.NAMESPACE+'/version_record.json' or '/revisions/' in path and path.endswith('/record.json'):actual.pop(path)
        record=self.record('0009',self.revision,vc.differences(self.expected8,actual))
        record['authorization'].update(scope=vc.DOC_SCOPE,named_requested_file='README.md')
        record.update(documentation_only=True,production_code_modified=False,scientific_gate_pass=False,formal_experiments_executed=False)
        record['bindings'].update(root_readme_policy=vc.binding(root,vc.DOC_POLICY_PATH),
            original_version_verifier=vc.binding(root,vc.NAMESPACE+'/tools/version_control.py'),
            version_verifier=vc.binding(root,vc.DOC_VERIFIER_PATH))
        self.set_nine(record);return record

    def set_nine(self,record):
        path=vc.NAMESPACE+'/revisions/0009/record.json';write_json(self.root/path,record)
        self.revision=vc.binding(self.root,path)

    def test_readme_01_explicit_nine_passes_and_original_reader_rejects(self):
        self.readme_fixture();self.assertEqual(self.check()['status'],'PASS')
        with self.assertRaisesRegex(original.IntegrityError,'PROTECTED_LEGACY_PATH_CHANGE'):
            original.verify_project(self.root,self.version_sha,self.revision['sha256'])

    def test_readme_02_unregistered_followup_or_newline_change_rejected(self):
        self.readme_fixture();(self.root/'README.md').write_bytes(b'Updated navigation\r\n')
        with self.assertRaisesRegex(vc.IntegrityError,'UNREGISTERED_FILE_DRIFT'):self.check()

    def test_readme_03_wrong_authorization_rejected(self):
        record=self.readme_fixture();record['authorization']['named_requested_file']='docs/GATE.md';self.set_nine(record)
        with self.assertRaisesRegex(vc.IntegrityError,'README_EXPLICIT_FILE_AUTHORIZATION_REQUIRED'):self.check()

    def test_readme_04_resigned_policy_cannot_broaden_path(self):
        record=self.readme_fixture();policy=vc.read_json(self.root/vc.DOC_POLICY_PATH);policy['legacy_path']='docs/GATE.md'
        write_json(self.root/vc.DOC_POLICY_PATH,policy);binding=vc.binding(self.root,vc.DOC_POLICY_PATH)
        record['bindings']['root_readme_policy']=binding
        record['changes']['added']=[binding if x['path']==vc.DOC_POLICY_PATH else x for x in record['changes']['added']]
        self.set_nine(record)
        with self.assertRaisesRegex(vc.IntegrityError,'README_POLICY_SCOPE_CHANGED'):self.check()

    def test_readme_05_other_historical_or_source_change_rejected(self):
        record=self.readme_fixture();old=vc.file_info(self.root/'src/engine.py');(self.root/'src/engine.py').write_bytes(b'new production\n')
        record['changes']['modified'].append(dict(path='src/engine.py',before=old,after=vc.file_info(self.root/'src/engine.py')))
        self.set_nine(record)
        with self.assertRaisesRegex(vc.IntegrityError,'README_OTHER_ASSET_CHANGE_REJECTED'):self.check()

    def test_readme_06_delete_or_rename_not_permitted(self):
        record=self.readme_fixture();row=record['changes']['modified'].pop();(self.root/'README.md').unlink()
        record['changes']['deleted']=[dict(path='README.md',before=row['before'])];self.set_nine(record)
        with self.assertRaisesRegex(vc.IntegrityError,'README_ONLY_MODIFICATION_ALLOWED'):self.check()

    def test_readme_07_exception_does_not_apply_to_future_revision(self):
        self.readme_fixture();self.assertEqual(self.check()['status'],'PASS');before=self.prior_expected()
        (self.root/'README.md').write_bytes(b'Unauthorized future update\n');self.append_fixture_revision(before)
        with self.assertRaisesRegex(vc.IntegrityError,'PROTECTED_LEGACY_PATH_CHANGE'):self.check()

    def test_readme_08_before_hash_forgery_rejected(self):
        record=self.readme_fixture();record['changes']['modified'][0]['before']['sha256']='0'*64;self.set_nine(record)
        with self.assertRaisesRegex(vc.IntegrityError,'README_BASELINE_HASH_MISMATCH'):self.check()

    def test_readme_09_original_verifier_or_new_verifier_tamper_rejected(self):
        self.readme_fixture();(self.root/vc.DOC_VERIFIER_PATH).write_bytes(b'forged verifier\n')
        with self.assertRaisesRegex(vc.IntegrityError,'README_NEW_VERIFIER_BINDING_MISMATCH'):self.check()

    def test_readme_10_unrelated_namespace_asset_cannot_piggyback(self):
        record=self.readme_fixture();path=vc.NAMESPACE+'/runtime/unapproved.py';(self.root/path).parent.mkdir();(self.root/path).write_bytes(b'change\n')
        record['changes']['added'].append(vc.binding(self.root,path));self.set_nine(record)
        with self.assertRaisesRegex(vc.IntegrityError,'README_UNAUTHORIZED_ADDED_ASSET'):self.check()
