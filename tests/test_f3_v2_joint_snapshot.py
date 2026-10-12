"""Shared pool and full-graph snapshot correctness; no controller performance."""
from dataclasses import replace
from copy import deepcopy
import math
import unittest
from unittest.mock import patch

from test_f3_v2_batch_executor import fixture, network
from dynamic_lisl.scientific_snapshot import SnapshotEvaluation, ScientificSnapshotEvaluator
from dynamic_lisl.f3_v2.joint_proposer import JointSearchBudget, BoundedJointProposer
from dynamic_lisl.f3_v2.snapshot_controllers import (
    SnapshotBatchController, StaticBatchController, batch_target_edges, improvement)
from dynamic_lisl.f3_v2.snapshot_controllers import current_snapshot_view
from dynamic_lisl.f3_v2.natural_engine import NaturalGeometryBatchEngine
from dynamic_lisl.load_aware_router import DeterministicLoadAwareRouter


def pool_fixture():
    ex,a,v,fixed=fixture(('BBM','MBB','BBM','MBB'))
    e=network(ex,fixed)
    e.advance_to(1)
    budget=JointSearchBudget(4,2,4,7,4,100,100,8)
    proposer=BoundedJointProposer(v,budget)
    p=proposer.propose(e.executor,a.members,decision_root_sha256=e.decision_root_sha256())
    return e,proposer,p,a


class JointSnapshotTests(unittest.TestCase):
    def test_loadaware_epoch_context_is_current_private_and_uses_frozen_E2_rule(self):
        ex,a,v,fixed=fixture(('BBM','MBB'))
        base=network(ex,fixed)
        e=NaturalGeometryBatchEngine(base.nodes,fixed,base.capacity_bit_s,base.commodities,
            base.trace,base.delay,ex,router=DeterministicLoadAwareRouter(),
            absolute_time_frame_id=base.absolute_time_frame_id)
        e.advance_to(2)
        self.assertEqual(e.router.snapshot.time_s,0)
        before=deepcopy(e.canonical_state())
        with self.assertRaisesRegex(ValueError,'STALE_OR_FUTURE_LOAD_SNAPSHOT'):
            ScientificSnapshotEvaluator(e).evaluate_hold()
        view=current_snapshot_view(e)
        self.assertEqual(view.router.snapshot.time_s,2)
        expected=e.clone()
        expected._recompute_routes('engineering-frozen-E2-context-reference')
        self.assertEqual(view.router.snapshot,expected.router.snapshot)
        self.assertEqual(ScientificSnapshotEvaluator(view).evaluate_hold(),ScientificSnapshotEvaluator(expected).evaluate_hold())
        proposer=BoundedJointProposer(v,JointSearchBudget(2,1,1,3,2,20,20,4))
        pool=proposer.propose(e.executor,a.members,decision_root_sha256=e.decision_root_sha256())
        for controller in (SnapshotBatchController('B1-v2'),SnapshotBatchController('B3-v2',eta_aggregation='min')):
            decision=controller.observe(e,pool)
            self.assertIn(decision.action,pool.actions)
        self.assertEqual(e.canonical_state(),before)
        self.assertEqual(e.router.snapshot.time_s,0)

    def test_full_state_hash_covers_router_context_and_future_diagnostics(self):
        e,_,_,_=pool_fixture()
        before=e.canonical_state_sha256()
        other=e.clone();other._pending_clearance.append({'baseline_queue_bits':3})
        self.assertNotEqual(other.canonical_state_sha256(),before)
        other=e.clone();other.propagation_closure_events.append({'closed_bits':1})
        self.assertNotEqual(other.canonical_state_sha256(),before)
        self.assertEqual(e.canonical_state_sha256(),before)

    def test_pool_replay_identity_order_and_all_sizes(self):
        e,proposer,p,a=pool_fixture()
        q=proposer.propose(e.executor,a.members[::-1],decision_root_sha256=e.decision_root_sha256())
        # Input enumeration order is recorded separately in audit; normalize it
        # before production hashing so it cannot affect the common pool identity.
        self.assertEqual([x.batch_id for x in p.actions],[x.batch_id for x in q.actions])
        self.assertEqual(p.pool_sha256,q.pool_sha256)
        self.assertEqual(len(p.actions),8)
        self.assertEqual({len(x.members) for x in p.actions},{0,1,2,3,4})
        self.assertEqual([len(x.members) for x in p.actions],sorted(len(x.members) for x in p.actions))

    def test_every_final_batch_joint_safe_from_same_immutable_root(self):
        e,proposer,p,a=pool_fixture()
        before=e.canonical_state_sha256()
        for action,plan in zip(p.actions[1:],p.plans):
            check=proposer.validator.evaluate(e.executor,action,decision_root_sha256=e.decision_root_sha256())
            self.assertTrue(check.accepted,check.reason)
            self.assertEqual(plan.seal_sha256,check.seal_sha256)
        self.assertEqual(before,e.canonical_state_sha256())

    def test_explicit_incompatible_budgets_fail(self):
        with self.assertRaises(ValueError):JointSearchBudget(4,2,1,4,4,100,100,8)
        with self.assertRaises(ValueError):JointSearchBudget(4,2,1,7,4,100,100,7)
        with self.assertRaises(ValueError):JointSearchBudget(4,2,1,7,4,3,100,8)

    def test_search_cap_records_omissions_no_economic_repair(self):
        e,proposer,p,a=pool_fixture()
        tiny=replace(proposer.budget,expansion_cap=4,validation_cap=4)
        p=BoundedJointProposer(proposer.validator,tiny).propose(e.executor,a.members,decision_root_sha256=e.decision_root_sha256())
        self.assertTrue(p.audit['budget_exhausted'])
        self.assertEqual(p.audit['joint_validation_calls'],4)
        self.assertEqual(len(p.actions),5)
        self.assertFalse(p.audit['performance_inputs_read'])

    def test_snapshot_controllers_use_same_pool_no_time_advance(self):
        e,_,p,_=pool_fixture()
        before=e.canonical_state_sha256()
        for c in [StaticBatchController(),SnapshotBatchController('B1-v2'),SnapshotBatchController('B3-v2',eta_aggregation='min')]:
            d=c.observe(e,p)
            self.assertIn(d.action,p.actions)
            self.assertEqual(e.canonical_state_sha256(),before)
        self.assertNotIn('future_trace_sha256',e.decision_root_state())
        self.assertNotIn('traffic_cursor',e.decision_root_state())

    def test_b1_exact_tie_hold_and_canonical_replace_tie(self):
        e,_,p,_=pool_fixture()
        def tied(_self,edges):return SnapshotEvaluation(tuple(edges),10.,20.,())
        with patch.object(ScientificSnapshotEvaluator,'evaluate_edges',tied):
            d=SnapshotBatchController('B1-v2').observe(e,p)
        self.assertEqual(d.action.kind,'HOLD')
        hold_edges=tuple(tuple(x) for x in e.graph['admit_edges'])
        def improve(_self,edges):return SnapshotEvaluation(tuple(edges),10. if tuple(edges)==hold_edges else 5.,20.,())
        with patch.object(ScientificSnapshotEvaluator,'evaluate_edges',improve):
            d=SnapshotBatchController('B1-v2').observe(e,p)
        expected=next(a for a in p.actions[1:] if batch_target_edges(e,a)!=hold_edges)
        self.assertEqual(d.action.batch_id,expected.batch_id)

    def test_b3_min_eta_requires_explicit_draft_choice_and_documents_bias(self):
        e,_,p,_=pool_fixture()
        with self.assertRaises(ValueError):SnapshotBatchController('B3-v2')
        hold_edges=tuple(tuple(x) for x in e.graph['admit_edges'])
        def value(_self,edges):return SnapshotEvaluation(tuple(edges),10. if tuple(edges)==hold_edges else 5.,20.,())
        with patch.object(ScientificSnapshotEvaluator,'evaluate_edges',value):
            d=SnapshotBatchController('B3-v2',eta_aggregation='min').observe(e,p)
        records=d.metadata['candidates']
        by_id={a.batch_id:plan for a,plan in zip(p.actions[1:],p.plans)}
        for row in records:
            plan=by_id[row['batch_id']]
            self.assertEqual(row['eta'],min(r['usable_lifetime_s']/r['remaining_lifetime_s'] for r in plan.member_results))
            self.assertEqual(row['score'],row['deltaV']*row['eta'])
        # Under equal whole-graph DeltaV, one short-lived member suppresses the
        # whole batch; this is a conservative heuristic, not an exact service law.
        self.assertEqual(improvement(math.inf,math.inf),0)

    def test_b2_real_elapsed_per_binding_initial_age(self):
        e,_,p,_=pool_fixture()
        c=SnapshotBatchController('B2-v2',minimum_hold_s=4,initial_age_s=0,
                                  initial_bindings=[m.old_binding for m in p.actions[-1].members])
        hold_edges=tuple(tuple(x) for x in e.graph['admit_edges'])
        def value(_self,edges):return SnapshotEvaluation(tuple(edges),10. if tuple(edges)==hold_edges else 5.,20.,())
        with patch.object(ScientificSnapshotEvaluator,'evaluate_edges',value):d=c.observe(e,p)
        self.assertEqual(d.action.kind,'HOLD')
        self.assertTrue(all(not r['eligible'] for r in d.metadata['candidates']))
        with self.assertRaises(ValueError):SnapshotBatchController('B2-v2',minimum_hold_s=4,initial_age_s=0)

    def test_snapshot_full_batch_edges_not_sum_individual_proxies(self):
        e,_,p,_=pool_fixture()
        four=next(a for a in p.actions if len(a.members)==4)
        expected=set(tuple(x) for x in e.graph['admit_edges'])
        expected-=set(tuple(e[0] for e in m.old_binding) for m in four.members)
        expected|=set(tuple(e[0] for e in m.new_terminal_pair) for m in four.members)
        self.assertEqual(batch_target_edges(e,four),tuple(sorted(expected)))
        v=ScientificSnapshotEvaluator(e).evaluate_edges(batch_target_edges(e,four))
        self.assertEqual(v.topology_edges,tuple(sorted(expected)))


if __name__=='__main__':unittest.main(verbosity=2)
