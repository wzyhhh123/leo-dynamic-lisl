"""Persistent eight-worker failure isolation and evidence; no registered run."""
from dataclasses import replace
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from test_f3_v2_joint_snapshot import pool_fixture
from dynamic_lisl.f3_v2.batch_rollout import PersistentBatchBranchPool,BatchPersistenceForecast
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256


class WorkerFailureTests(unittest.TestCase):
    def test_submission_failure_closes_pool_and_retains_failure(self):
        engine,proposer,pool,_=pool_fixture()
        class FailedSubmissionPool:
            def submit(self,*args):raise RuntimeError('ENGINEERING_SUBMISSION_FAILURE')
            def shutdown(self,**kwargs):self.shutdown_called=True
        stub=FailedSubmissionPool()
        workers=PersistentBatchBranchPool(worker_count=8);workers._pool=stub
        with self.assertRaisesRegex(RuntimeError,'ENGINEERING_SUBMISSION_FAILURE'):
            workers.evaluate(engine,proposer.validator,pool.actions,BatchPersistenceForecast.from_current_state(engine,5))
        self.assertTrue(stub.shutdown_called)
        self.assertTrue(workers.closed)
        self.assertEqual(workers.last_failure_evidence['failed_phase'],'SUBMISSION')
        self.assertFalse(workers.last_failure_evidence['scientific_result_usable'])

    def test_failed_branch_preserves_completed_prefix_and_closes_8worker_pool(self):
        engine,proposer,pool,_=pool_fixture()
        before=engine.canonical_state_sha256()
        children={p.pid for p in multiprocessing.active_children()}
        actions=(pool.actions[0],replace(pool.actions[1],decision_root_sha256='f'*64),*pool.actions[2:])
        forecast=BatchPersistenceForecast.from_current_state(engine,5)
        workers=PersistentBatchBranchPool(worker_count=8)
        with self.assertRaisesRegex(ValueError,'ROLLOUT_ACTION_ROOT_MISMATCH'):
            workers.evaluate(engine,proposer.validator,actions,forecast)
        evidence=workers.last_failure_evidence
        self.assertEqual(evidence['status'],'EXECUTION_FAILURE')
        self.assertEqual(evidence['failed_merge_index'],1)
        self.assertEqual(len(evidence['completed_prefix']),1)
        self.assertFalse(evidence['scientific_result_usable'])
        self.assertTrue(evidence['pool_closed'])
        self.assertEqual(evidence['root_hash'],evidence['live_hash_after_failure'])
        self.assertEqual(engine.canonical_state_sha256(),before)
        self.assertEqual({p.pid for p in multiprocessing.active_children()},children)
        with self.assertRaisesRegex(RuntimeError,'POOL_ALREADY_SHUT_DOWN'):
            workers.evaluate(engine,proposer.validator,actions,forecast)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'branch_failure.json';write_new_json(path,evidence)
            self.assertEqual(len(file_sha256(path)),64)


if __name__=='__main__':unittest.main(verbosity=2)
