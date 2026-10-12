"""New joint rollout engineering only; exact serial/spawn and state chain."""
from dataclasses import replace
import multiprocessing
import unittest

from test_f3_v2_batch_executor import fixture,network
from dynamic_lisl.f3_v2.batch_rollout import (
    BatchPersistenceForecast, JointRootRolloutEvaluator, PersistentBatchBranchPool, JointRolloutController)
from dynamic_lisl.f3_v2.joint_proposer import JointSearchBudget,BoundedJointProposer
from dynamic_lisl.f3_v2.service_adapter import ScriptedBatchProposal


class JointRolloutTests(unittest.TestCase):
    def test_forecast_current_only_cutoff_and_physical_time_guard(self):
        ex,a,v,f=fixture(('MBB',))
        e=network(ex,f,horizon=6);e.advance_to(5)
        fc=BatchPersistenceForecast.from_current_state(e,5)
        self.assertEqual(dict(fc.current_rates_bit_s),{'f0':20})
        b=e.clone();fc.attach(b)
        self.assertEqual(b.trace.rate_at(8),{'f0':20})
        self.assertEqual(e.trace.rate_at(8),{'f0':0})
        self.assertEqual(b.decision_root_sha256(),e.decision_root_sha256())
        a=replace(a,members=(),decision_time_s=e.now,decision_root_sha256=e.decision_root_sha256())
        r=JointRootRolloutEvaluator(e,v).evaluate(a,fc)
        self.assertEqual(r['horizon_end_s'],10)
        with self.assertRaises(ValueError):JointRootRolloutEvaluator(e,v).evaluate(a,replace(fc,horizon_s=30))

    def test_joint_branch_atomic_real_setup_clone_isolation(self):
        ex,a,v,f=fixture(('BBM','MBB','BBM','MBB'))
        e=network(ex,f);e.advance_to(1)
        a=replace(a,decision_time_s=e.now,decision_root_sha256=e.decision_root_sha256())
        before=e.canonical_state_sha256()
        r=JointRootRolloutEvaluator(e,v).evaluate(a,BatchPersistenceForecast.from_current_state(e,10))
        self.assertEqual(e.canonical_state_sha256(),before)
        self.assertTrue(all(r['invariants'].values()))
        self.assertEqual(len(r['action_result']['commit']['member_results']),4)
        events=r['terminal_events']
        commits=[x for x in events if x['event']=='BATCH_COMMIT']
        self.assertEqual(len(commits),1)
        self.assertEqual(commits[0]['details']['command_count'],4)
        self.assertTrue(any(x['event']=='LINK_UP' and x['time']==3 for x in events))

    def test_serial_evaluates_whole_pool_and_hold_exact_tie(self):
        ex,a,v,f=fixture(('BBM','MBB'))
        e=network(ex,f,rates=0)
        p=BoundedJointProposer(v,JointSearchBudget(2,1,2,3,2,20,20,4)).propose(
            e.executor,a.members,decision_root_sha256=e.decision_root_sha256())
        d=JointRolloutController(v,rollout_cap=4).observe(e,p,horizon_s=10)
        self.assertEqual(d.action.kind,'HOLD')
        self.assertEqual(len(d.metadata['branches']),len(p.actions))
        self.assertTrue(all(r['J_H_bit_s']==0 for r in d.metadata['branches']))
        with self.assertRaises(ValueError):JointRolloutController(v,rollout_cap=1).observe(e,p,horizon_s=10)

    def test_serial_eight_worker_multi_epoch_exact_chain_and_shutdown(self):
        ex,a,v,f=fixture(('BBM','MBB','BBM','MBB'))
        serial=network(ex,f);parallel=serial.clone()
        budget=JointSearchBudget(4,2,16,15,4,100,100,16)
        proposer=BoundedJointProposer(v,budget)
        serial_c=JointRolloutController(v,rollout_cap=16)
        original_children={p.pid for p in multiprocessing.active_children()}
        observations=[]
        with PersistentBatchBranchPool(worker_count=8) as workers:
            parallel_c=JointRolloutController(v,rollout_cap=16,branch_pool=workers)
            first_pool=None
            for t in (0,2,4,6,8,10):
                self.assertEqual(serial.canonical_state_sha256(),parallel.canonical_state_sha256())
                serial.advance_to(t);parallel.advance_to(t)
                self.assertEqual(serial.canonical_state_sha256(),parallel.canonical_state_sha256())
                root_s=serial.canonical_state_sha256();root_p=parallel.canonical_state_sha256()
                ps=proposer.propose(serial.executor,a.members,decision_root_sha256=serial.decision_root_sha256())
                pp=proposer.propose(parallel.executor,a.members,decision_root_sha256=parallel.decision_root_sha256())
                self.assertEqual(ps.public_document(),pp.public_document())
                ds=serial_c.observe(serial,ps,horizon_s=10)
                dp=parallel_c.observe(parallel,pp,horizon_s=10)
                self.assertEqual(ds.metadata['branches'],dp.metadata['branches'])
                self.assertEqual(ds.action.to_dict(),dp.action.to_dict())
                self.assertEqual(ds.metadata['selected_pool_index'],dp.metadata['selected_pool_index'])
                self.assertEqual(serial.canonical_state_sha256(),root_s)
                self.assertEqual(parallel.canonical_state_sha256(),root_p)
                if first_pool is None:first_pool=workers._pool
                self.assertIs(first_pool,workers._pool)
                for engine,decision in ((serial,ds),(parallel,dp)):
                    engine.schedule_action(ScriptedBatchProposal(t,decision.action.batch_id,decision.action,v,True))
                    engine.settle_current_time()
                self.assertEqual(serial.canonical_state_sha256(),parallel.canonical_state_sha256())
                observations.append((t,sum(serial.arrived.values()),sum(serial.delivered.values())))
            serial.advance_to(12);parallel.advance_to(12)
            self.assertEqual(serial.canonical_state_sha256(),parallel.canonical_state_sha256())
        self.assertTrue(workers.closed)
        self.assertEqual({p.pid for p in multiprocessing.active_children()},original_children)
        self.assertGreater(len({(a,d) for t,a,d in observations}),1)
        self.assertGreater(observations[-1][2],0)


if __name__=='__main__':unittest.main(verbosity=2)
