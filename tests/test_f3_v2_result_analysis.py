"""Tiny literal ledger fixtures, not actual controller performance results."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from test_f3_v2_evidence_preflight import frozen
from dynamic_lisl.f3_v2.result_analysis import analyze_registered_results,load_sealed_registered_results
from dynamic_lisl.f3_v2.evidence import file_sha256,write_new_json,persist_run_evidence
from dynamic_lisl.f3_v2.joint_action import canonical_sha256


def fixture():
    common={'scale':160,'rho':.8,'topology_regime':'K_STAR','router':'PRIMARY','traffic':'MIGRATION',
            'decision_cadence_s':5,'max_batch_replace':4}
    manifest=frozen({'runs':[{'run_id':'L','controller':'B4-v2',**common},{'run_id':'R','controller':'B3-v2',**common}],
        'contrasts':[{'contrast_id':'C','kind':'PRIMARY_CONTROLLER','left_run_id':'L','right_run_id':'R'}]})
    metrics={r:{'run_id':r,'outcome':'COMPLETE','J_is_complete':True,'J_bit_s':v,
        'engineering_only':False,'residual_backlog_bits':0,'delivery_ratio':1,'completion_time_s':3} for r,v in [('L',8),('R',10)]}
    return manifest,metrics


class ResultAnalysisTests(unittest.TestCase):
    def test_frozen_registry_all_complete_pair_no_global_ranking(self):
        m,r=fixture();result=analyze_registered_results(m,r)
        self.assertEqual(result['COMPLETE_count'],2)
        self.assertEqual(result['paired_contrasts'][0]['delta_J_left_minus_right'],-2)
        self.assertFalse(result['global_controller_ranking_created'])

    def test_censored_pair_retained_with_no_delta(self):
        m,r=fixture();r['L'].update(outcome='CENSORED_AT_DRAIN_LIMIT',J_is_complete=False,residual_backlog_bits=12,delivery_ratio=.5,completion_time_s=None)
        result=analyze_registered_results(m,r)
        self.assertEqual(result['CENSORED_count'],1)
        self.assertTrue(result['paired_analysis_performed'])
        pair=result['paired_contrasts'][0]
        self.assertEqual(pair['status'],'NOT_RANKED_CENSORED')
        self.assertNotIn('delta_J_left_minus_right',pair)

    def test_missing_or_failed_run_prevents_partial_paired_analysis(self):
        for failed in (False,True):
            m,r=fixture()
            if failed:r['L'].update(outcome='EXECUTION_BLOCKED',J_is_complete=False)
            else:del r['L']
            result=analyze_registered_results(m,r)
            self.assertEqual(result['status'],'INCOMPLETE_EVIDENCE_PACKAGE')
            self.assertFalse(result['paired_analysis_performed'])
            self.assertEqual(len(result['run_ledger']),2)

    def test_draft_engineering_extra_or_false_completion_rejected(self):
        for fault in ('draft','engineering','extra','false_J','mismatched_ID'):
            m,r=fixture()
            if fault=='draft':m['frozen']=False
            elif fault=='engineering':r['L']['engineering_only']=True
            elif fault=='extra':r['UNKNOWN']=deepcopy(r['L'])
            elif fault=='false_J':r['L']['J_is_complete']=False
            else:r['L']['run_id']='OTHER'
            with self.subTest(fault=fault),self.assertRaises(ValueError):analyze_registered_results(m,r)

    def test_unequal_action_permission_not_attributed_to_forecast(self):
        m,r=fixture();unsigned={k:v for k,v in m.items() if k!='canonical_sha256'}
        unsigned['runs'][1]['max_batch_replace']=1
        m=frozen({k:v for k,v in unsigned.items() if k not in ('frozen','status')})
        with self.assertRaisesRegex(ValueError,'UNFAIR_PRIMARY_PAIR'):analyze_registered_results(m,r)


class SealedResultTests(unittest.TestCase):
    """Literal temporary bytes only; never formal evidence or simulation runs."""
    def sealed(self,root):
        m,metrics=fixture();unsigned={k:v for k,v in m.items() if k!='canonical_sha256'}
        hashes={'fixture_input.json':'1'*64,'fixture_code.py':'2'*64}
        provenance={'inputs':{'fixture_input.json':'1'*64},'code':{'fixture_code.py':'2'*64}}
        unsigned.update(file_hashes=hashes,result_provenance={rid:deepcopy(provenance) for rid in metrics})
        m=frozen({k:v for k,v in unsigned.items() if k not in ('status','frozen')})
        mapping={}
        for rid,data in metrics.items():
            directory=root/rid;directory.mkdir();mapping[rid]=rid
            contents={name:{} for name in ('final_state_evidence.json','action_timeline.json',
                'transition_timeline.json','candidate_source_audit.json','timeseries.json')}
            contents.update({'metrics.json':data,'invariant_report.json':{'status':'PASS',
                'scientific_outcome':'COMPLETE','items':{'fixture':{'pass':True}}},
                'failure_summary.json':{'status':'COMPLETE','failure':None},
                'input_code_hashes.json':{**provenance,'execution_binding':{
                    'execution_manifest_canonical_sha256':m['canonical_sha256'],
                    'registered_run_configuration_sha256':canonical_sha256(next(row for row in m['runs'] if row['run_id']==rid))}}})
            for name,value in contents.items():write_new_json(directory/name,value)
            self.reseal(directory)
        return m,metrics,mapping

    def reseal(self,directory):
        seals={p.name:file_sha256(p) for p in directory.iterdir() if p.name!='artifact_hashes.json'}
        (directory/'artifact_hashes.json').write_text(json.dumps(seals),encoding='utf-8')

    def test_registered_seals_and_exact_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);m,expected,mapping=self.sealed(root)
            metrics,sources=load_sealed_registered_results(root,m,mapping)
            self.assertEqual(metrics,expected);self.assertEqual(list(sources),['L','R'])
            self.assertEqual(analyze_registered_results(m,metrics)['status'],'COMPLETE_REGISTERED_EVIDENCE')

    def test_self_resealed_changed_input_code_manifest_or_run_config_rejected(self):
        for fault in ('input','code','manifest','configuration'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);m,_,mapping=self.sealed(root);p=root/'L/input_code_hashes.json'
                doc=json.loads(p.read_text())
                if fault=='input':doc['inputs']['fixture_input.json']='3'*64
                elif fault=='code':doc['code']['fixture_code.py']='3'*64
                elif fault=='manifest':doc['execution_binding']['execution_manifest_canonical_sha256']='3'*64
                else:doc['execution_binding']['registered_run_configuration_sha256']='3'*64
                p.write_text(json.dumps(doc));self.reseal(root/'L')
                with self.assertRaisesRegex(ValueError,'REGISTERED_INPUT_CODE_OR_CONFIGURATION_MISMATCH'):
                    load_sealed_registered_results(root,m,mapping)

    def test_missing_seal_hash_tamper_path_escape_or_unregistered_run_rejected(self):
        for fault in ('missing','tamper','escape','extra'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);m,_,mapping=self.sealed(root)
                if fault=='missing':(root/'L/timeseries.json').unlink()
                elif fault=='tamper':(root/'L/metrics.json').write_text('{}')
                elif fault=='escape':mapping['L']='../outside'
                else:mapping['UNKNOWN']='L'
                with self.assertRaises((ValueError,FileNotFoundError)):load_sealed_registered_results(root,m,mapping)

    def test_resealed_false_scientific_success_rejected(self):
        for fault in ('outcome','empty_checks','failure'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);m,_,mapping=self.sealed(root)
                p=root/'L/invariant_report.json';doc=json.loads(p.read_text())
                if fault=='outcome':doc['scientific_outcome']='PARTIAL'
                elif fault=='empty_checks':doc['items']={}
                else:(root/'L/failure_summary.json').write_text(json.dumps({'status':'COMPLETE','failure':'hidden'}))
                p.write_text(json.dumps(doc));self.reseal(root/'L')
                with self.assertRaisesRegex(ValueError,'SCIENTIFIC_RESULT_WITH_FAILED_INVARIANTS'):
                    load_sealed_registered_results(root,m,mapping)

    def test_draft_rejected_before_reading_any_result(self):
        m,_=fixture();m['frozen']=False
        with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(ValueError,'ANALYSIS_REQUIRES_EXACT_FROZEN_MANIFEST'):
            load_sealed_registered_results(Path(temp),m,{'L':'missing'})

    def test_formal_writer_requires_binding_before_creating_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'never_created'
            with self.assertRaisesRegex(ValueError,'FORMAL_EVIDENCE_REQUIRES_EXPLICIT_EXECUTION_BINDING'):
                persist_run_evidence(target,None,run_id='L',invariant_report={},decision_records=[],
                    candidate_audits=[],code_hashes={},input_hashes={},engineering_only=False)
            self.assertFalse(target.exists())


if __name__=='__main__':unittest.main(verbosity=2)
