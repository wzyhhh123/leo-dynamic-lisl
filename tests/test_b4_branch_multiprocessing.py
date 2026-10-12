"""Spawn-safe transport and one exact real branch before scaling gate."""
from pathlib import Path
import hashlib
import json
import pickle
import psutil
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'tools'))
from check_b4_branch_multiprocessing import setup
from dynamic_lisl.b4_branch_multiprocessing import (
    BranchTask,ParallelB4BranchPool,encode_root,
    _worker_engineering_error)
from dynamic_lisl.rollout_evaluator import ExactRootActionRolloutEvaluator


class B4SpawnTests(unittest.TestCase):
    def test_concurrent_worker_liveness_and_shutdown(self):
        folder=PROJECT/'data/raw/sgp4_x720'
        for count in (1,2,4,8):
            with self.subTest(workers=count):
                with ParallelB4BranchPool(count,folder) as pool:
                    ready=pool.warm()
                    pids={row['pid'] for row in ready}
                    self.assertEqual(len(pids),count)
                self.assertFalse(any(psutil.pid_exists(pid) for pid in pids))

    def test_worker_exception_reaches_parent_and_pool_shuts_down(self):
        with ParallelB4BranchPool(1,PROJECT/'data/raw/sgp4_x720') as pool:
            pids={row['pid'] for row in pool.warm()}
            with self.assertRaisesRegex(RuntimeError,
                'B4_ENGINEERING_EXCEPTION_PROPAGATION_PROBE'):
                pool.pool.submit(_worker_engineering_error).result()
        self.assertFalse(any(psutil.pid_exists(pid) for pid in pids))

    def test_real_engine_pickle_and_spawn_hold_exact(self):
        # Transport correctness precedes final P1 hash registration in the Gate.
        _,assets,runner,state,_=setup(check_preflight=False)
        engine=runner.engine
        before=engine.canonical_state_sha256()
        forecast=runner.controller._forecast(state)
        reference=ExactRootActionRolloutEvaluator(
            engine,assets.physical,assets.fixed,'Z_MODERATE').evaluate_hold(
                forecast,root_hash=before,forecast_hash=forecast.sha256())
        with ParallelB4BranchPool(1,PROJECT/'data/raw/sgp4_x720') as pool:
            workers=pool.warm()
            self.assertEqual(len({x['pid'] for x in workers}),1)
            task=BranchTask(0,encode_root(engine,pool.token),
                pickle.dumps(assets.physical,protocol=pickle.HIGHEST_PROTOCOL),
                tuple(assets.fixed),'Z_MODERATE',forecast,None,None,
                before,forecast.sha256())
            encoded,_,_=pool.submit(task).result()
            observed=pickle.loads(encoded)
        self.assertEqual(observed['result'],reference)
        canonical=json.dumps(observed['evidence']['canonical_state'],
            sort_keys=True,separators=(',',':'),allow_nan=False)
        self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(),
                         observed['result'].end_state_sha256)
        self.assertEqual(engine.canonical_state_sha256(),before)


if __name__=='__main__':
    unittest.main()
