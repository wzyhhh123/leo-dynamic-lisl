"""Engineering pipeline/tiny oracle/raw inventory/K1 candidate tests."""
from dataclasses import replace
import unittest

from test_f3_v2_batch_executor import fixture,network,FRAME
from dynamic_lisl.f3_v2.candidate_source import replacement_inventory,RawCandidateBudget
from dynamic_lisl.f3_v2.joint_proposer import BoundedJointProposer,JointSearchBudget
from dynamic_lisl.f3_v2.joint_action import JointAction,canonical_sha256
from dynamic_lisl.f3_v2.tiny_oracle import enumerate_tiny_joint_actions,audit_tiny_approximation
from dynamic_lisl.f3_v2.structural import legal_edge_inventory,deterministic_lexicographic_topology
from dynamic_lisl.f3_v2.k1 import build_k1_candidate
from dynamic_lisl.f3_v2.service_adapter import DecisionSchedule,BatchCadenceAdapter
from dynamic_lisl.f3_v2.natural_engine import NaturalGeometryBatchEngine
from dynamic_lisl.gate_e2_experiments import E2TransitionEngine
from dynamic_lisl.terminal_executor import TerminalExecutor


class PipelineTests(unittest.TestCase):
    def test_uncapped_raw_inventory_and_caps_replay(self):
        ex,a,v,_=fixture(('BBM','MBB'))
        planes={n:i for i,n in enumerate(ex.satellite_ids)}
        kwargs=dict(plane_by_satellite=planes,retarget_a_s=1,retarget_b_s=1,acquisition_s=1,observation_end_s=30)
        all_rows=replacement_inventory(ex,v.physical_validator.physical_layer,**kwargs)
        capped=replacement_inventory(ex,v.physical_validator.physical_layer,**kwargs,raw_budget=RawCandidateBudget(1,1,2))
        self.assertTrue(all_rows['audit']['uncapped'])
        self.assertLessEqual(len(capped['members']),2)
        self.assertFalse(capped['audit']['performance_input_read'])
        self.assertEqual(capped,replacement_inventory(ex,v.physical_validator.physical_layer,**kwargs,raw_budget=RawCandidateBudget(1,1,2)))
        self.assertEqual(all_rows['audit']['uncapped_physical_count'],capped['audit']['uncapped_physical_count'])

    def test_tiny_complete_legal_set_and_bounded_omissions(self):
        ex,a,v,f=fixture(('BBM','MBB'))
        e=network(ex,f);e.advance_to(1)
        proposer=BoundedJointProposer(v,JointSearchBudget(2,1,1,3,2,20,20,4))
        p=proposer.propose(e.executor,a.members,decision_root_sha256=e.decision_root_sha256())
        exact=enumerate_tiny_joint_actions(e,v,p.physical_singletons,max_members=2)
        self.assertEqual(len(exact.actions),4)
        self.assertEqual(exact.audit['evaluation_count'],4)
        report=audit_tiny_approximation(e,v,p,max_members=2,horizon_s=5)
        self.assertFalse(report['main_scale_optimality_claim'])
        self.assertFalse(report['B3_B4_equal_action_required'])
        self.assertFalse(report['budgets_tuned_by_this_result'])
        self.assertGreaterEqual(report['bounded_B4_J_H'],report['exact_B4_J_H'])

    def test_tiny_rejects_main_scale(self):
        ex,a,v,f=fixture(('BBM',)*5)
        e=network(ex,f)
        with self.assertRaises(ValueError):enumerate_tiny_joint_actions(e,v,a.members,max_members=4)

    def test_k1_candidate_certified_exact_budget_root_and_hash(self):
        ex,a,v,f=fixture(('BBM','MBB'))
        physical=v.physical_validator.physical_layer
        idle=TerminalExecutor(ex.satellite_ids)
        planes={n:i for i,n in enumerate(ex.satellite_ids)}
        inventory=legal_edge_inventory(idle,physical,planes,retarget_a_s=1,retarget_b_s=1,acquisition_s=1,observation_end_s=30)
        solved=deterministic_lexicographic_topology(inventory['edges'],2,tuple(planes.values()),max_search_nodes=1000,wall_timeout_s=2)
        kwargs=dict(plane_by_satellite=planes,target_K=2,retarget_a_s=1,retarget_b_s=1,acquisition_s=1,
                    initialization_convention='PREESTABLISHED_AT_ZERO_WITH_FORWARD_GATE_C_CERTIFICATE')
        initial,doc=build_k1_candidate(ex.satellite_ids,f,solved,physical,**kwargs)
        _,other=build_k1_candidate(ex.satellite_ids,f,solved,physical,**kwargs)
        self.assertEqual(len(initial.links),2)
        self.assertEqual(doc,other)
        self.assertEqual(doc['status'],'DRAFT_NOT_FROZEN')
        self.assertFalse(doc['K_star_selected_by_this_helper'])
        with self.assertRaises(ValueError):build_k1_candidate(ex.satellite_ids,f,{**solved,'status':'UNKNOWN'},physical,**kwargs)

    def test_natural_engine_inherits_existing_loadaware_behavior(self):
        self.assertIs(NaturalGeometryBatchEngine._recompute_routes,E2TransitionEngine._recompute_routes)

    def test_early_complete_stops_real_drain_before_next_cadence(self):
        ex,a,v,f=fixture(('BBM',))
        e=network(ex,f,horizon=1,rates=1)
        schedule=DecisionSchedule(5,1,10,5,.01,True)
        adapter=BatchCadenceAdapter(e,schedule,v)
        def hold(live,root,h):return JointAction(live.now,FRAME,root,canonical_sha256([]),())
        result=adapter.run(hold)
        self.assertEqual(result['status'],'COMPLETE')
        self.assertLess(e.now,5)
        self.assertEqual(len(result['checkpoints']),1)
        self.assertLessEqual(result['residual_backlog_bits'],.01)


if __name__=='__main__':unittest.main(verbosity=2)
