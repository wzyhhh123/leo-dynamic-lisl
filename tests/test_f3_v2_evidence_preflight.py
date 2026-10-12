"""Engineering-only evidence and fail-closed launch boundary tests."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from test_f3_v2_batch_executor import fixture,network
from dynamic_lisl.f3_v2.evidence import engine_invariants,persist_run_evidence,paired_contrast,file_sha256
from dynamic_lisl.f3_v2.preflight import validate_preflight
from dynamic_lisl.f3_v2.joint_action import canonical_sha256
from check_f3_v2_engineering import authorized_planning_revision,PLANNING_REVISION,ROOT


def invariants(engine,end=6):
    return engine_invariants(engine,expected_trace_sha256=engine.trace.sha256(),
        complete_threshold_bits=.01,drain_limit_s=end,
        capacity_tolerance_bit_s=max(1e-9,engine.capacity_bit_s*1e-12))


def engine_at(end,rate=1,horizon=1):
    ex,_,_,fixed=fixture(('BBM',))
    engine=network(ex,fixed,horizon=horizon,rates=rate)
    engine.advance_to(end)
    return engine


def frozen(data):
    doc={**data,'status':'FROZEN','frozen':True}
    return {**doc,'canonical_sha256':canonical_sha256(doc)}


def preflight_fixture(root):
    # Fictional tiny authorization fixture only: not a registered manifest and
    # never persisted to project configs or used to run a simulation.
    science=frozen({'action_kinds':['HOLD','BATCH_REPLACE']})
    k0={'status':'PASS','full_audit_complete':True,'human_authorization_verified':True,'K_star':8}
    k1={'status':'PASS','approved_K_star':8,'batch_compatibility_checked':True}
    eng={key:'PASS' for key in ('V2_A','V2_B','V2_C','V2_D','V2_E','V2_F','full_regression',
        'serial_8worker_natural_geometry','no_performance_leakage','historical_integrity')}
    budget={'status':'MEASURED_AND_APPROVED','matrix_wall_budget_s':20}
    refs={};hashes={}
    for key,doc in [('K0',k0),('K1',k1),('ENGINEERING',eng),('RUNTIME',budget)]:
        path=root/(key+'.json');path.write_text(json.dumps(doc),encoding='utf-8')
        digest=file_sha256(path);refs[key]={'path':path.name,'sha256':digest};hashes[path.name]=digest
    (root/'scientific.py').write_text('# tiny source fixture',encoding='utf-8')
    hashes['scientific.py']=file_sha256(root/'scientific.py')
    manifest=frozen({'runs':[{'run_id':'TINY-NOT-REGISTERED','K':8,'runtime_budget':{'estimated_wall_clock_s':10}}],
        'scientific_contract_canonical_sha256':science['canonical_sha256'],'file_hashes':hashes,'acceptance_evidence':refs})
    auth={'status':'APPROVED','actor':'HUMAN','scope':'REGISTERED_F3_V2',
          'manifest_canonical_sha256':manifest['canonical_sha256'],'authorized_run_ids':['TINY-NOT-REGISTERED']}
    return dict(manifest=manifest,science_contract=science,k0_report=k0,k1_report=k1,
                engineering_report=eng,runtime_budget=budget,authorization=auth)


class EvidenceTests(unittest.TestCase):
    def persist(self,path,engine,report):
        return persist_run_evidence(path,engine,run_id='ENGINEERING-ONLY',invariant_report=report,
            decision_records=[],candidate_audits=[],code_hashes={},input_hashes={},engineering_only=True)

    def test_complete_evidence_seal_and_immutable_attempt(self):
        engine=engine_at(5);report=invariants(engine)
        self.assertEqual(report['scientific_outcome'],'COMPLETE');self.assertEqual(report['status'],'PASS')
        before=deepcopy(engine.canonical_state())
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'attempt';metrics=self.persist(out,engine,report)
            self.assertTrue(metrics['J_is_complete']);self.assertEqual(metrics['completion_time_s'],5)
            seals=json.loads((out/'artifact_hashes.json').read_text())
            self.assertEqual(len(seals),9)
            for name,digest in seals.items():self.assertEqual(file_sha256(out/name),digest)
            with self.assertRaises(FileExistsError):self.persist(out,engine,report)
        self.assertEqual(engine.canonical_state(),before)

    def test_censor_keeps_residual_and_never_ranks_truncated_J(self):
        e=engine_at(6,1000,6);report=invariants(e)
        self.assertEqual(report['status'],'PASS');self.assertEqual(report['scientific_outcome'],'CENSORED_AT_DRAIN_LIMIT')
        with tempfile.TemporaryDirectory() as temp:
            metrics=self.persist(Path(temp)/'censored',e,report)
        self.assertGreater(metrics['residual_backlog_bits'],0)
        self.assertFalse(metrics['J_is_complete']);self.assertIsNone(metrics['mean_bit_delay_s'])
        other={**metrics,'outcome':'COMPLETE','J_bit_s':10,'completion_time_s':3}
        contrast=paired_contrast(metrics,other)
        self.assertEqual(contrast['status'],'NOT_RANKED_CENSORED')
        self.assertNotIn('delta_J_left_minus_right',contrast)
        self.assertEqual(contrast['right_completion_time_s'],3)

    def test_partial_not_scientific_censor(self):
        e=engine_at(2,1000,6);report=invariants(e)
        self.assertEqual(report['status'],'FAIL');self.assertEqual(report['scientific_outcome'],'PARTIAL')

    def test_terminal_assertion_captured_before_failure_persistence(self):
        e=engine_at(5)
        with patch.object(e.executor,'assert_invariants',side_effect=AssertionError('BILATERAL_BROKEN')):
            report=invariants(e)
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(report['items']['terminal_invariants']['error'],'BILATERAL_BROKEN')
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'failed';metrics=self.persist(out,e,report)
            self.assertEqual(metrics['outcome'],'EXECUTION_BLOCKED')
            self.assertTrue((out/'final_state_evidence.json').is_file())
            self.assertTrue((out/'artifact_hashes.json').is_file())

    def test_each_numeric_invariant_detected_without_clamp(self):
        for attribute,value,item in [('max_capacity_violation',100,'capacity')]:
            e=engine_at(5);setattr(e,attribute,value)
            report=invariants(e);self.assertFalse(report['items'][item]['pass'])
        e=engine_at(5);key=(e.nodes[0],'f0');e.queues.bits[key]=-3
        report=invariants(e);self.assertFalse(report['items']['queue_nonnegative']['pass'])
        self.assertEqual(e.queues.bits[key],-3)
        e=engine_at(5);e.delivered['f0']+=10
        self.assertFalse(invariants(e)['items']['work_conservation']['pass'])

    def test_nonfinite_evidence_is_preserved_as_invalid_numeric_tag(self):
        e=engine_at(5);e.objective_by_commodity['f0']=float('nan')
        report=invariants(e);self.assertFalse(report['items']['finite_state']['pass'])
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'nan';self.persist(out,e,report)
            saved=json.loads((out/'metrics.json').read_text())
            self.assertEqual(saved['J_bit_s'],{'invalid_nonfinite_float':'nan'})
            self.assertEqual(saved['outcome'],'EXECUTION_BLOCKED')
        self.assertNotEqual(e.objective_by_commodity['f0'],e.objective_by_commodity['f0'])

    def test_complete_pair_and_failed_pair(self):
        a={'outcome':'COMPLETE','J_bit_s':8};b={'outcome':'COMPLETE','J_bit_s':10}
        self.assertEqual(paired_contrast(a,b)['delta_J_left_minus_right'],-2)
        self.assertEqual(paired_contrast(a,{**b,'outcome':'EXECUTION_BLOCKED'})['status'],'NOT_EVALUABLE_EXECUTION_FAILURE')


class PreflightTests(unittest.TestCase):
    def test_missing_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            report=validate_preflight(Path(temp),*({} for _ in range(7)))
            self.assertEqual(report['status'],'NOT_READY')
            self.assertFalse(report['registered_P1_v2_started'])

    def test_complete_tiny_artifact_chain_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=preflight_fixture(root)
            self.assertEqual(validate_preflight(root,**args)['status'],'READY')

    def test_authorization_rejects_wrong_actor_hash_scope_or_order(self):
        for field,value in [('actor','AUTOMATION'),('manifest_canonical_sha256','unknown'),
                            ('scope','ENGINEERING_ONLY'),('authorized_run_ids',[])]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);args=preflight_fixture(root);args['authorization'][field]=value
                self.assertFalse(validate_preflight(root,**args)['checks']['formal_run_authorization'])

    def test_file_tamper_or_missing_evidence_rejected(self):
        for kind in ('source','report','missing'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);args=preflight_fixture(root)
                if kind=='source':(root/'scientific.py').write_text('modified')
                elif kind=='report':(root/'K0.json').write_text('{}')
                else:(root/'K0.json').unlink()
                self.assertEqual(validate_preflight(root,**args)['status'],'NOT_READY')

    def test_frozen_manifest_and_contract_must_be_bound_not_only_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=preflight_fixture(root)
            args['science_contract']['action_kinds'].append('ADD')
            self.assertFalse(validate_preflight(root,**args)['checks']['scientific_contract_frozen'])

    def test_false_PASS_report_claim_cannot_replace_supporting_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=preflight_fixture(root);args['engineering_report']['invented']=True
            self.assertFalse(validate_preflight(root,**args)['checks']['supporting_evidence_matches_input'])

    def test_budget_and_K_mismatch_reject(self):
        for value in (True,float('inf'),float('nan'),-1,0):
            with self.subTest(value=value),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);args=preflight_fixture(root);args['runtime_budget']['matrix_wall_budget_s']=value
                self.assertFalse(validate_preflight(root,**args)['checks']['runtime_measured'])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=preflight_fixture(root);args['runtime_budget']['matrix_wall_budget_s']=1
            self.assertFalse(validate_preflight(root,**args)['checks']['matrix_budget_sufficient'])
            args['manifest']['runs'][0]['K']=16
            self.assertFalse(validate_preflight(root,**args)['checks']['K_star_manifest_bound'])

    def test_absent_scientific_gate_cannot_be_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=preflight_fixture(root)
            args['engineering_report']['serial_8worker_natural_geometry']='PENDING'
            self.assertFalse(validate_preflight(root,**args)['checks']['engineering_acceptance_complete'])

    def test_explicit_authorized_planning_revision_only(self):
        seal=json.loads((ROOT/PLANNING_REVISION/'artifact_hashes.json').read_text(encoding='utf-8'))
        for rel,digest in seal['before'].items():
            self.assertTrue(authorized_planning_revision(ROOT,rel,digest,seal['after'][rel]))
            self.assertFalse(authorized_planning_revision(ROOT,rel,digest,'unregistered'))
        self.assertFalse(authorized_planning_revision(ROOT,'src/dynamic_lisl/terminal_executor.py','old','new'))


if __name__=='__main__':unittest.main(verbosity=2)
