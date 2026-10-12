"""K0 review correctness only: no natural K x20 audit or primary selection."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from dynamic_lisl.f3_v2.evidence import file_sha256
from dynamic_lisl.f3_v2.joint_action import canonical_sha256
from dynamic_lisl.f3_v2.k0_ledger import (
    KS,TIMES,snapshot_record,review_ledger,validate_contract,load_review_records,lifetime_summary)
from dynamic_lisl.f3_v2.structural import StructuralEdge

ROOT=Path(__file__).resolve().parents[1]


def contract():
    return json.loads((ROOT/'configs/gate_k0_contract_v1_1_DRAFT.json').read_text(encoding='utf-8'))


def row(K,t,*,mbb=8,bbm=8,connected=True,bridges=0,status='EXACT',wall=1):
    bindings=[((str(i*2),'D1'),(str(i*2+1),'D1')) for i in range(K)]
    solver={'status':status,'target_K':K,'optimality_certified':status!='UNKNOWN','bindings':bindings if status=='EXACT' else None,'wall_s':wall}
    inventory={'uncapped':True,'performance_input_read':False,'stratum_counts':{'BBM':bbm,'MBB':mbb},
        'uncapped_physical_count':bbm+mbb,'selected_member_ids':['m'+str(i) for i in range(bbm+mbb)]}
    return snapshot_record(K=K,time_s=t,matching_capacity=160,represented_planes=[0,1,2,3],
        connected=connected,dynamic_bridge_count=bridges,replace_inventory=inventory,solver=solver,
        physical_and_resource_checks=True,input_hashes={'fixture':'a'*64},
        canonical_structural_state={'bindings':bindings,'time_s':t},
        batch_diagnostics={'size4_status':'UNKNOWN_MAXIMUM'})


def records_for(K,mutate=None):
    records=[]
    for t in TIMES:
        kwargs=mutate(t) if mutate else {}
        for replay in (0,1):records.append({'replay_index':replay,'snapshot':row(K,t,wall=1+replay,**kwargs)})
    return records


def summary(report,K):return next(r for r in report['rows'] if r['K']==K)


class K0LedgerTests(unittest.TestCase):
    def test_contract_exact_twenty_and_no_threshold_drift(self):
        self.assertEqual(len(TIMES),20);self.assertEqual(TIMES[-1],570)
        validate_contract(contract())
        for key,value in (('snapshot_times_s',list(TIMES)+( [600])),('primary_band',[.1,.6])):
            d=contract();d[key]=value
            with self.assertRaisesRegex(ValueError,'CONTRACT_MISMATCH'):validate_contract(d)
        d=contract();d['admissibility']['connected_and_bridges_lt_edges_snapshots']=17
        with self.assertRaises(ValueError):validate_contract(d)

    def test_two_replays_exclude_wall_and_report_no_selection(self):
        a=row(24,0,wall=1);b=row(24,0,wall=4)
        self.assertNotEqual(a['solver_sha256'],b['solver_sha256'])
        self.assertEqual(a['relative_structural_replay_sha256'],b['relative_structural_replay_sha256'])
        report=review_ledger(contract(),records_for(24));r=summary(report,24)
        self.assertTrue(r['admissible_review']);self.assertEqual(r['summary']['sample_count'],20)
        self.assertIsNone(report['K_star']);self.assertFalse(report['Gate_K0_PASS'])
        self.assertEqual(report['status'],'STRUCTURAL_REVIEW_INCOMPLETE')

    def test_eighteen_twenty_boundary_and_all_plane_twenty(self):
        r=review_ledger(contract(),records_for(24,lambda t:{'connected':t>=60}))
        self.assertTrue(summary(r,24)['admissible_review'])
        r=review_ledger(contract(),records_for(24,lambda t:{'connected':t>=90}))
        self.assertFalse(summary(r,24)['admissible_review'])

    def test_median_middle_two_not_average_all_and_zero_inventory_not_loss(self):
        r=review_ledger(contract(),records_for(24,lambda t:{'mbb':2 if t<300 else 18,'bbm':18 if t<300 else 2}))
        self.assertEqual(summary(r,24)['summary']['median_MBB_fraction'],.5)
        self.assertFalse(summary(r,24)['admissible_review']) # per-point8/8 requirement still fails
        r=review_ledger(contract(),records_for(24,lambda t:{'mbb':0,'bbm':0}))
        self.assertIsNone(summary(r,24)['summary']['median_MBB_fraction'])
        self.assertFalse(summary(r,24)['admissible_review'])

    def test_unknown_missing_infeasible_and_replay_mismatch_are_distinct(self):
        for status,expected in (('UNKNOWN',None),('EXACT_INFEASIBLE',False)):
            r=review_ledger(contract(),records_for(24,lambda t:{'status':status} if t==0 else {}))
            self.assertIs(summary(r,24)['admissible_review'],expected)
        rows=records_for(24);rows.pop();r=review_ledger(contract(),rows)
        self.assertIsNone(summary(r,24)['admissible_review'])
        rows=records_for(24);rows[1]['snapshot']=row(24,0,connected=False)
        r=review_ledger(contract(),rows)
        self.assertEqual(summary(r,24)['point_status'][0]['status'],'REPLAY_MISMATCH')

    def test_all_registered_records_review_is_not_formal_K0_pass(self):
        report=review_ledger(contract(),[r for K in KS for r in records_for(K)])
        self.assertEqual(report['supplied_records'],480)
        self.assertEqual(report['status'],'STRUCTURAL_REVIEW_COMPLETE')
        self.assertFalse(summary(report,4)['admissible_review'])
        self.assertFalse(summary(report,160)['admissible_review'])
        self.assertFalse(report['full_audit_complete']);self.assertIsNone(report['K_star'])
        self.assertFalse(report['human_authorization_verified'])

    def test_duplicate_and_changed_input_or_forged_metrics_fail(self):
        rows=records_for(24)
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):review_ledger(contract(),rows+[rows[0]])
        rows[1]['snapshot']['input_hashes']['fixture']='b'*64
        r=rows[1]['snapshot'];r['relative_structural_replay_sha256']=canonical_sha256({k:v for k,v in r.items() if k not in ('relative_structural_replay_sha256','solver_sha256')})
        with self.assertRaisesRegex(ValueError,'INPUTS_CHANGED'):review_ledger(contract(),rows)
        r=row(24,0);r['metrics']['MBB_fraction']=.9
        r['relative_structural_replay_sha256']=canonical_sha256({k:v for k,v in r.items() if k not in ('relative_structural_replay_sha256','solver_sha256')})
        with self.assertRaisesRegex(ValueError,'METRICS_INCONSISTENT'):review_ledger(contract(),[{'snapshot':r,'replay_index':0}])

    def test_capped_inventory_rejected_at_serializer(self):
        # Producer never launders a runtime top-K table into uncapped K0 stats.
        from unittest.mock import patch
        import dynamic_lisl.f3_v2.k0_ledger as module
        original=module.snapshot_record
        def reject(**kwargs):
            kwargs['replace_inventory']['uncapped']=False
            return original(**kwargs)
        with patch(__name__+'.snapshot_record',reject):
            with self.assertRaisesRegex(ValueError,'UNCAPPED'):row(24,0)

    def test_lifetime_censor_horizon_and_empty_are_preserved(self):
        edges=[StructuralEdge((('a','D1'),('b','D1')),(0,1),572,600,True,600),
               StructuralEdge((('c','D1'),('d','D1')),(2,3),572,580,False,600)]
        r=lifetime_summary(edges,setup_s=2)
        self.assertEqual(r['median_s'],18);self.assertEqual(r['fraction_le_10s'],.5)
        self.assertEqual(r['right_censored_count'],1);self.assertTrue(r['truncated_metric_not_full_physical_lifetime'])
        self.assertIsNone(edges[0].to_dict()['physical_end_s'])
        self.assertIsNone(lifetime_summary([],setup_s=2)['median_s'])

    def test_loader_exact_support_chain_and_hash_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'row.json';p.write_text(json.dumps(row(24,0)))
            support=root/'support.json';support.write_text('{}')
            ref={'path':p.name,'sha256':file_sha256(p),'replay_index':0,
                'supporting_evidence':{k:{'path':support.name,'sha256':file_sha256(support)} for k in ('solver','physical','inventory','lifetime')}}
            manifest={'schema':'f3_v2_k0_review_inputs_v1','records':[ref]}
            # Hash-valid empty files are not gate evidence. Literal ledger
            # fixtures remain useful for threshold tests, never disk provenance.
            with self.assertRaisesRegex(ValueError,'SUPPORT_STATE_CONTENT'):
                load_review_records(root,manifest)
            support.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'SUPPORT'):load_review_records(root,manifest)
            p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'SNAPSHOT'):load_review_records(root,manifest)


if __name__=='__main__':unittest.main()
