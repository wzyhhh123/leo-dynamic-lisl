from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from runtime_successor_chain import validate_runtime_chain, EXECUTOR
from dynamic_lisl.b4_runtime_seal import canonical, sha
import json

class RuntimeSuccessorChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.file='source.py'
        (self.root/self.file).write_text('new source')
        self.current=sha(self.root/self.file);self.old='a'*64

    def write(self,path,doc):
        p=self.root/path;p.write_text(json.dumps(doc));return p

    def entry(self,index,parent,successor,status='CANDIDATE_SUCCESSOR_VALIDATED'):
        multi=self.write(f'multi{index}.json',{'status':'MULTI_EPOCH_EXACT_EQUIVALENCE_PASS','all_epoch_branch_and_state_exact':True})
        doc={'status':status,'file':self.file,'H_old':parent,'H_new':successor,
             'scientific_semantics_unchanged':True,'multi_epoch_report':multi.name,
             'supporting_evidence':[{'report':multi.name,'report_sha256':sha(multi)}]}
        evidence=self.write(f'evidence{index}.json',doc)
        registry={'status':'AUTHORIZED_RUNTIME_SUCCESSOR','file':self.file,
                  'parent_hash':parent,'successor_hash':successor,'authorization_gate':'fixture',
                  'evidence':{'report':evidence.name,'report_sha256':sha(evidence)}}
        registry['canonical_sha256']=canonical(registry)
        path=self.write(f'registry{index}.json',registry)
        return {'path':path.name,'sha256':sha(path)}

    def check(self,entries,current=None):
        return validate_runtime_chain(self.root,self.file,self.old,current or self.current,entries)

    def test_A_historical_tail(self):
        self.assertTrue(self.check([],self.old)['pass'])

    def test_B_authorized_successor(self):
        result=self.check([self.entry(1,self.old,self.current)])
        self.assertTrue(result['pass']);self.assertEqual(result['validated_chain'],[self.old,self.current])

    def test_C_unregistered_hash(self):
        self.assertEqual(self.check([])['reason'],'UNREGISTERED_SUCCESSOR')
        self.assertEqual(self.check([self.entry(1,self.old,'b'*64)])['reason'],'CURRENT_HASH_MISMATCH')

    def test_D_wrong_parent(self):
        self.assertEqual(self.check([self.entry(1,'b'*64,self.current)])['reason'],'PARENT_HASH_MISMATCH')

    def test_E_missing_evidence(self):
        entry=self.entry(1,self.old,self.current);(self.root/'evidence1.json').unlink()
        self.assertEqual(self.check([entry])['reason'],'MISSING_GATE_EVIDENCE')

    def test_F_gate_failed(self):
        self.assertEqual(self.check([self.entry(1,self.old,self.current,'FAIL')])['reason'],'GATE_NOT_PASS')

    def test_G_registry_tamper(self):
        entry=self.entry(1,self.old,self.current)
        p=self.root/entry['path'];p.write_text(p.read_text()+' ')
        self.assertEqual(self.check([entry])['reason'],'REGISTRY_HASH_MISMATCH')

    def test_H_multilevel_chain_no_skip(self):
        first=self.entry(1,self.old,'b'*64);second=self.entry(2,'b'*64,self.current)
        self.assertTrue(self.check([first,second])['pass'])
        self.assertEqual(self.check([second])['reason'],'PARENT_HASH_MISMATCH')
        self.assertEqual(self.check([second,first])['reason'],'PARENT_HASH_MISMATCH')

    def test_exact_file_path(self):
        entry=self.entry(1,self.old,self.current)
        result=validate_runtime_chain(self.root,'other.py',self.old,self.current,[entry])
        self.assertEqual(result['reason'],'UNREGISTERED_SUCCESSOR')

    def test_evidence_tamper(self):
        entry=self.entry(1,self.old,self.current)
        p=self.root/'evidence1.json';p.write_text(p.read_text()+' ')
        self.assertEqual(self.check([entry])['reason'],'REGISTRY_HASH_MISMATCH')

    def test_current_production_authorization(self):
        root=Path(__file__).resolve().parents[1]
        result=validate_runtime_chain(root,EXECUTOR,
            'f879ea45dd006769108c32205ed111c53f5f2a3c83e7098bdbf0220415b73a44',sha(root/EXECUTOR))
        self.assertTrue(result['pass'],result)
