"""Actual Gate B/C structural point producer; no controller performance."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dynamic_lisl.f3_v2.k0_fixture import fixture
from dynamic_lisl.f3_v2.k0_snapshot import produce_snapshot, SnapshotBudget, BatchDiagnosticSpec, write_snapshot_bundle
from dynamic_lisl.f3_v2.k0_ledger import lifetime_summary, load_review_records
from dynamic_lisl.f3_v2.joint_action import canonical_sha256
from dynamic_lisl.f3_v2.k0_support import verify_snapshot_support
from dynamic_lisl.operational_policy import OperationalPolicy


class K0SnapshotTests(unittest.TestCase):
    def test_actual_bilateral_points_and_two_replays(self):
        args,_=fixture()
        for t in (0,30,570):
            with self.subTest(time_s=t):
                a=produce_snapshot(**args,K=4,time_s=t)
                b=produce_snapshot(**args,K=4,time_s=t)
                self.assertEqual(a['snapshot']['solver_status'],'EXACT')
                self.assertEqual(a['snapshot']['relative_structural_replay_sha256'],b['snapshot']['relative_structural_replay_sha256'])
                self.assertTrue(a['physical']['physical_and_resource_checks'])
                self.assertTrue(a['physical']['structure']['connected'])
                self.assertEqual(a['matching']['cardinality'],8)
                self.assertEqual(len(a['physical']['terminal_state']['links']),4)
                self.assertTrue(a['inventory']['uncapped'])
                self.assertGreater(a['inventory']['uncapped_physical_count'],0)
                self.assertEqual(a['lifetime']['selected_links']['median_s'],598-t)
                for e in a['lifetime']['selected_edges']:
                    self.assertEqual(e['ready_time_s'],t+2)
                    self.assertIsNone(e['physical_end_s'])
                    self.assertEqual(e['censor_status'],'RIGHT_CENSORED_AT_600')
                self.assertFalse(a['controller_or_traffic_invoked'])
                self.assertFalse(a['K_star_selected'])

    def test_matching_upper_bound_infeasibility_is_explicit(self):
        args,_=fixture();a=produce_snapshot(**args,K=16,time_s=0)
        self.assertEqual(a['solver']['status'],'EXACT_INFEASIBLE')
        self.assertEqual(a['solver']['capacity_upper_bound'],8)
        self.assertIsNone(a['snapshot']['metrics'])
        self.assertEqual(a['physical']['status'],'NOT_EXECUTED_NO_CERTIFIED_TOPOLOGY')

    def test_search_exhaustion_never_builds_incumbent(self):
        args,_=fixture();args['budget']=SnapshotBudget(1,5.,1,5.)
        a=produce_snapshot(**args,K=4,time_s=0)
        self.assertEqual(a['solver']['status'],'UNKNOWN')
        self.assertIsNone(a['snapshot']['metrics'])
        self.assertFalse(a['physical']['physical_and_resource_checks'])
        self.assertEqual(a['inventory']['status'],'NOT_EXECUTED_NO_CERTIFIED_TOPOLOGY')

    def test_selected_forward_certificate_revalidated(self):
        args,_=fixture();physical=args['physical_layer'];method=physical.evaluate;count=[0]
        def changed(*a,**k):
            count[0]+=1
            if count[0]>8:return {'accepted':False,'reason':'FOR_FAIL_LOCAL'}
            return method(*a,**k)
        physical.evaluate=changed
        with self.assertRaisesRegex(AssertionError,'SELECTED_GATE_C_CERTIFICATE_CHANGED'):
            produce_snapshot(**args,K=4,time_s=0)

    def test_generator_fixed_graph_and_lifetime_inputs(self):
        args,_=fixture();a=produce_snapshot(**args,K=4,time_s=0)
        args['fixed_edges']=(e for e in args['fixed_edges'])
        b=produce_snapshot(**args,K=4,time_s=0)
        self.assertEqual(a['snapshot']['relative_structural_replay_sha256'],b['snapshot']['relative_structural_replay_sha256'])
        from dynamic_lisl.f3_v2.structural import StructuralEdge
        edges=[StructuralEdge((('a','D1'),('b','D1')),(0,1),572,600,True,600)]
        self.assertEqual(lifetime_summary(iter(edges),setup_s=2),lifetime_summary(edges,setup_s=2))

    def test_setup_legality_natural_end_and_censor_not_conflated(self):
        args,_=fixture();catalog=args['physical_layer'].catalog
        for key,windows in catalog.windows.items():
            catalog.windows[key]=[replace(windows[0],end_s=573.,right_censored=False)]
        a=produce_snapshot(**args,K=4,time_s=570)
        self.assertEqual(a['lifetime']['selected_links']['median_s'],1)
        self.assertTrue(all(e['physical_end_s']==573 for e in a['lifetime']['selected_edges']))
        args['setup']['acquisition_s']=2.
        a=produce_snapshot(**args,K=4,time_s=570)
        self.assertEqual(a['matching']['cardinality'],0)
        self.assertEqual(a['solver']['status'],'EXACT_INFEASIBLE')
        self.assertTrue(all(r['reason']=='INSUFFICIENT_LIFETIME' for r in a['lifetime']['idle_rejections']))

    def test_unregistered_or_implicit_hypotheses_rejected(self):
        args,_=fixture()
        for key,value in (('initialization_convention',''),('budget',None)):
            bad=dict(args);bad[key]=value
            with self.assertRaises((ValueError,TypeError)):produce_snapshot(**bad,K=4,time_s=0)
        with self.assertRaisesRegex(ValueError,'UNREGISTERED'):produce_snapshot(**args,K=4,time_s=600)
        for values in ((True,1,1,1),(1,0,1,1),(1,1,1,float('inf'))):
            with self.assertRaises(ValueError):SnapshotBudget(*values)

    def test_exclusive_evidence_publication(self):
        args,_=fixture();a=produce_snapshot(**args,K=4,time_s=0)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'point'
            ref=write_snapshot_bundle(out,a,root=root,replay_index=0)
            self.assertEqual(set(ref['supporting_evidence']),{'solver','physical','inventory','lifetime'})
            records=load_review_records(root,{'schema':'f3_v2_k0_review_inputs_v1','records':[ref]})
            self.assertEqual(records[0]['support_verification']['status'],'CONTENT_CONSISTENCY_PASS')
            self.assertFalse(records[0]['support_verification']['global_optimality_independently_proved_by_this_loader'])
            before={p.name:p.read_bytes() for p in out.iterdir()}
            with self.assertRaises(FileExistsError):write_snapshot_bundle(out,a,root=root,replay_index=1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir()})
            with self.assertRaises(ValueError):write_snapshot_bundle(root/'bad',a,root=root,replay_index=2)

    def test_actual_safe_four_member_witness_and_bounded_unknown(self):
        args,_=fixture()
        args['batch_diagnostic']=BatchDiagnosticSpec(2516,OperationalPolicy('STRICT_CONNECTED'))
        a=produce_snapshot(**args,K=4,time_s=0);d=a['snapshot']['batch_diagnostics']
        self.assertEqual(d['max_joint_safe_witness_size'],4)
        self.assertEqual(d['allowed_joint_maximum_status'],'EXACT_WITHIN_0_TO_4')
        self.assertTrue(d['root_unchanged']);self.assertEqual(d['role'],'DIAGNOSTIC_ONLY')
        self.assertGreater(d['joint_safe_count_by_size']['4'],0)
        self.assertFalse(a['snapshot']['batch_diagnostics_used_for_admissibility'])
        args['batch_diagnostic']=BatchDiagnosticSpec(1,OperationalPolicy('STRICT_CONNECTED'))
        b=produce_snapshot(**args,K=4,time_s=0);d=b['snapshot']['batch_diagnostics']
        self.assertEqual(d['allowed_joint_maximum_status'],'UNKNOWN')
        self.assertFalse(d['all_subsets_through_size_scanned'])
        # Diagnostic uncertainty does not erase a proved topology.
        self.assertEqual(b['solver']['status'],'EXACT')

    def test_support_perturbation_is_not_laundered_by_matching_file_hashes(self):
        args,_=fixture();a=produce_snapshot(**args,K=4,time_s=0)
        support={k:a[k] for k in ('solver','physical','inventory','lifetime')}
        self.assertEqual(verify_snapshot_support(a['snapshot'],support)['status'],'CONTENT_CONSISTENCY_PASS')
        for key in ('solver','physical','inventory','lifetime'):
            bad=deepcopy(support);bad[key]={}
            with self.assertRaises(ValueError):verify_snapshot_support(a['snapshot'],bad)
        bad=deepcopy(a)
        bad['physical']['terminal_state']['sequence']+=1
        bad['snapshot']['canonical_structural_state']['physical']=bad['physical']
        with self.assertRaisesRegex(ValueError,'PREESTABLISHED_STATE'):
            verify_snapshot_support(bad['snapshot'],{k:bad[k] for k in support})
        bad=deepcopy(a)
        bad['lifetime']['selected_links']['median_s']+=1
        bad['snapshot']['canonical_structural_state']['lifetime']=bad['lifetime']
        with self.assertRaisesRegex(ValueError,'LIFETIME_SUMMARY'):
            verify_snapshot_support(bad['snapshot'],{k:bad[k] for k in support})
        bad=deepcopy(a);bad['snapshot']['metrics']['connected']=False
        with self.assertRaisesRegex(ValueError,'REBUILT_RECORD'):
            verify_snapshot_support(bad['snapshot'],support)

    def test_unknown_and_infeasible_support_remain_explicit(self):
        args,_=fixture()
        for K,budget in ((16,args['budget']),(4,SnapshotBudget(1,5.,1,5.))):
            args['budget']=budget;a=produce_snapshot(**args,K=K,time_s=0)
            r=verify_snapshot_support(a['snapshot'],{k:a[k] for k in ('solver','physical','inventory','lifetime')})
            self.assertEqual(r['status'],'CONTENT_CONSISTENCY_PASS')
            self.assertFalse(r['Gate_B_state_reconstructed'])


if __name__=='__main__':unittest.main()
