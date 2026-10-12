"""Short synthetic integration only; never registered performance episodes."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from test_f3_v2_batch_executor import fixture,network
from dynamic_lisl.f3_v2.engineering_episode import run_engineering_episode
from dynamic_lisl.f3_v2.service_adapter import DecisionSchedule
from dynamic_lisl.f3_v2.joint_proposer import BoundedJointProposer,JointSearchBudget
from dynamic_lisl.f3_v2.snapshot_controllers import StaticBatchController,SnapshotBatchController
from dynamic_lisl.f3_v2.batch_rollout import JointRolloutController
from dynamic_lisl.f3_v2.evidence import file_sha256


def scene(controller_id='B0-v2',rate=1):
    ex,action,validator,fixed=fixture(('BBM','MBB'))
    engine=network(ex,fixed,horizon=4,rates=rate)
    budget=JointSearchBudget(2,1,2,3,2,20,20,4)
    proposer=BoundedJointProposer(validator,budget)
    if controller_id=='B0-v2':controller=StaticBatchController()
    elif controller_id=='B4-v2':controller=JointRolloutController(validator,rollout_cap=4)
    elif controller_id=='B2-v2':controller=SnapshotBatchController(controller_id,minimum_hold_s=4,
        initial_age_s=0,initial_bindings=tuple(m.old_binding for m in action.members))
    else:controller=SnapshotBatchController(controller_id,eta_aggregation='min' if controller_id=='B3-v2' else None)
    source=lambda live,v:(action.members,{'fixture':'DETERMINISTIC_SYNTHETIC','no_performance_read':True})
    return dict(engine=engine,validator=validator,schedule=DecisionSchedule(2,4,8,2,.01,True),
        source=source,proposer=proposer,controller=controller,fixture_id='ENGINEERING-TINY-EPISODE',
        input_hashes={'fixture':'1'*64},code_hashes={'test_fixture':'2'*64},capacity_tolerance_bit_s=1e-9)


class EngineeringEpisodeTests(unittest.TestCase):
    def test_all_baselines_share_existing_kernel_and_evidence(self):
        for cid in ('B0-v2','B1-v2','B2-v2','B3-v2','B4-v2'):
            with self.subTest(controller=cid),tempfile.TemporaryDirectory() as temp:
                args=scene(cid);trace=args['engine'].trace.sha256()
                out=Path(temp)/'attempt';report=run_engineering_episode(output_dir=out,**args)
                self.assertEqual(report['status'],'ENGINEERING_EPISODE_PASS')
                self.assertEqual(args['engine'].trace.sha256(),trace)
                self.assertTrue(all(c['H_decision_root']==c['H_post_observe'] for c in report['checkpoints']))
                self.assertTrue(all(c['time_s']<8 for c in report['checkpoints']))
                metrics=json.loads((out/'run_evidence/metrics.json').read_text())
                self.assertTrue(metrics['engineering_only']);self.assertFalse(report['registered_P1_v2_executed'])
                seals=json.loads((out/'artifact_hashes.json').read_text())
                for name,digest in seals.items():self.assertEqual(file_sha256(out/name),digest)

    def test_repeat_state_chain_exact_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=scene('B4-v2')
            first=run_engineering_episode(output_dir=root/'first',**args)
            other=scene('B4-v2');second=run_engineering_episode(output_dir=root/'second',**other)
            self.assertEqual(first['checkpoints'],second['checkpoints'])
            self.assertEqual(args['engine'].canonical_state(),other['engine'].canonical_state())
            with self.assertRaises(FileExistsError):run_engineering_episode(output_dir=root/'first',**scene())

    def test_source_exception_persisted_before_stop_and_no_next_epoch(self):
        with tempfile.TemporaryDirectory() as temp:
            args=scene();calls=[]
            def bad_source(engine,validator):
                calls.append(engine.now);raise RuntimeError('SOURCE_FAILURE_FIXTURE')
            args['source']=bad_source;out=Path(temp)/'attempt'
            report=run_engineering_episode(output_dir=out,**args)
            self.assertEqual(report['status'],'FAIL_STOP');self.assertEqual(calls,[0])
            self.assertEqual(report['failure']['reason'],'SOURCE_FAILURE_FIXTURE')
            self.assertTrue((out/'run_evidence/final_state_evidence.json').is_file())
            saved=json.loads((out/'run_evidence/failure_summary.json').read_text())
            self.assertEqual(saved['status'],'EXECUTION_BLOCKED')

    def test_mutating_observer_rejected_and_original_numeric_error_not_clamped(self):
        with tempfile.TemporaryDirectory() as temp:
            args=scene()
            class BadController:
                controller_id='B0-v2'
                def observe(self,engine,pool):
                    engine.queues.bits[(engine.nodes[0],'f0')]=-3
                    return SimpleNamespace(action=pool.actions[0],metadata={})
            args['controller']=BadController();out=Path(temp)/'attempt'
            report=run_engineering_episode(output_dir=out,**args)
            self.assertEqual(report['status'],'FAIL_STOP')
            self.assertEqual(report['failure']['reason'],'CONTROLLER_CHANGED_LIVE_ENGINE')
            self.assertEqual(args['engine'].queues.bits[(args['engine'].nodes[0],'f0')],-3)
            saved=json.loads((out/'run_evidence/invariant_report.json').read_text())
            self.assertFalse(saved['items']['queue_nonnegative']['pass'])

    def test_censored_episode_is_legal_engineering_outcome(self):
        with tempfile.TemporaryDirectory() as temp:
            report=run_engineering_episode(output_dir=Path(temp)/'attempt',**scene(rate=1000))
            self.assertEqual(report['status'],'ENGINEERING_EPISODE_PASS')
            self.assertEqual(report['scientific_outcome'],'CENSORED_AT_DRAIN_LIMIT')

    def test_registered_id_rejected_before_output_or_advance(self):
        with tempfile.TemporaryDirectory() as temp:
            args=scene();args['fixture_id']='OCT26-CORE-01';out=Path(temp)/'not_created'
            with self.assertRaisesRegex(ValueError,'ENGINEERING_FIXTURE_ID_REQUIRED'):
                run_engineering_episode(output_dir=out,**args)
            self.assertFalse(out.exists());self.assertEqual(args['engine'].now,0)


if __name__=='__main__':unittest.main(verbosity=2)
