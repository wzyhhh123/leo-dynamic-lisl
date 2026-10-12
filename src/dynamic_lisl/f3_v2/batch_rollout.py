"""Joint root-only rollout, serial reference and persistent spawn scheduling.

Generic engineering implementation: a frozen K1 scene/contract and acceptance
are still required before any registered performance execution.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import math
import multiprocessing as mp
import os
import pickle
import time

from ..traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from .joint_action import canonical_sha256
from .service_adapter import ScriptedBatchProposal
from .snapshot_controllers import BatchControllerDecision


@dataclass(frozen=True)
class BatchPersistenceForecast:
    start_time_s: float
    horizon_s: float
    current_rates_bit_s: tuple

    def __post_init__(self):
        if not math.isfinite(self.start_time_s) or self.start_time_s<0 or not math.isfinite(self.horizon_s) or self.horizon_s<=0:
            raise ValueError('INVALID_EXPLICIT_FORECAST_INTERVAL')
        keys=[k for k,v in self.current_rates_bit_s]
        if keys!=sorted(set(keys)) or any(not math.isfinite(v) or v<0 for k,v in self.current_rates_bit_s):
            raise ValueError('INVALID_FORECAST_CURRENT_RATES')

    @classmethod
    def from_current_state(cls,engine,horizon_s):
        return cls(engine.now,horizon_s,tuple(sorted(engine.trace.rate_at(engine.now).items())))

    def attach(self,branch):
        if branch.now!=self.start_time_s:raise ValueError('FORECAST_ABSOLUTE_TIME_MISMATCH')
        branch.trace=PiecewiseConstantTrafficTrace(tuple(k for k,v in self.current_rates_bit_s),
            (TrafficSegment(0,self.start_time_s+self.horizon_s,dict(self.current_rates_bit_s),'v2-current-rate-persistence'),))
        branch.boundaries=list(branch.trace.boundaries_after(branch.now));branch.boundary_index=0

    @property
    def sha256(self):return canonical_sha256(self.__dict__)


class JointRootRolloutEvaluator:
    def __init__(self,engine,validator):self.engine,self.validator=engine,validator

    def evaluate(self,action,forecast):
        if forecast.start_time_s+forecast.horizon_s>self.validator.physical_validator.observation_end_s:
            raise ValueError('ROLLOUT_OUTSIDE_PHYSICAL_OBSERVATION_HORIZON')
        live_before=self.engine.canonical_state_sha256()
        branch=self.engine.clone()
        if branch.canonical_state_sha256()!=live_before:raise AssertionError('V2_CLONE_EXACTNESS_FAILURE')
        if branch.action_index<len(branch.actions):raise ValueError('FUTURE_VOLUNTARY_ACTION_IN_ROOT')
        decision_root=branch.decision_root_sha256()
        if decision_root!=action.decision_root_sha256:raise ValueError('ROLLOUT_ACTION_ROOT_MISMATCH')
        forecast.attach(branch)
        if branch.decision_root_sha256()!=decision_root:raise AssertionError('FORECAST_CHANGED_CURRENT_PHYSICAL_SERVICE_ROOT')
        start=math.fsum(branch.objective_by_commodity.values())
        terminal_cursor=len(branch.terminal_event_sequence)
        action_result=None
        if action.members:
            branch.schedule_action(ScriptedBatchProposal(branch.now,action.batch_id,action,self.validator,True))
            branch.settle_current_time();action_result=branch.batch_results[-1]
        branch.advance_to(forecast.start_time_s+forecast.horizon_s)
        final=math.fsum(branch.objective_by_commodity.values())
        invariants={
            'work_conservation':all(abs(branch.arrived[f]-branch.delivered[f]-branch.queues.total(f)-branch.in_flight.total(f))
                                     <=branch.abs_tol+branch.rel_tol*max(1.,abs(branch.arrived[f])) for f in branch.by_id),
            'queue_nonnegative':all(x>=0 for x in branch.queues.bits.values()),
            'capacity':branch.max_capacity_violation<=max(1e-9,branch.capacity_bit_s*1e-12),
            'live_state_unchanged':self.engine.canonical_state_sha256()==live_before,
            'horizon_exact':branch.now==forecast.start_time_s+forecast.horizon_s}
        branch.executor.assert_invariants()
        if not all(invariants.values()):raise AssertionError('V2_ROLLOUT_INVARIANT_FAILURE:'+str(invariants))
        return {'branch_id':'HOLD' if not action.members else action.batch_id,'action':action.to_dict(),
                'valid':True,'invalid_reason':None,'J_H_bit_s':final-start,
                'objective_start_bit_s':start,'objective_end_bit_s':final,
                'horizon_end_s':branch.now,'forecast_sha256':forecast.sha256,
                'live_before_hash':live_before,'live_after_hash':self.engine.canonical_state_sha256(),
                'action_result':action_result,'terminal_events':branch.terminal_event_sequence[terminal_cursor:],
                'terminal':branch.executor.snapshot(),'G_active':branch.graph['active_edges'],'G_admit':branch.graph['admit_edges'],
                'Q':branch.queues.snapshot(),'I':branch.in_flight.snapshot(),'D':dict(branch.delivered),
                'final_state':branch.canonical_state(),'invariants':invariants}


@dataclass(frozen=True)
class BatchBranchTask:
    index: int
    root_blob: bytes
    transport: str
    action: object
    forecast: BatchPersistenceForecast
    expected_root_hash: str


def _initialize_sgp4_worker(folder,token):
    # Reuse only the already-audited immutable asset transport. No old evaluator
    # or scientific controller is invoked. No mutable branch survives a task.
    from ..b4_branch_multiprocessing import init_worker
    init_worker(folder,token,None,None)


def execute_batch_task(task):
    start=time.perf_counter()
    if task.transport=='SYNTHETIC_PICKLE':engine,validator=pickle.loads(task.root_blob)
    elif task.transport=='FROZEN_SGP4':
        from ..b4_branch_multiprocessing import decode_root
        engine,validator=decode_root(task.root_blob)
    else:raise ValueError('UNKNOWN_V2_BRANCH_TRANSPORT')
    if engine.canonical_state_sha256()!=task.expected_root_hash:raise AssertionError('WORKER_ROOT_STATE_MISMATCH')
    result=JointRootRolloutEvaluator(engine,validator).evaluate(task.action,task.forecast)
    return {'index':task.index,'result':result,'pid':os.getpid(),'worker_wall_s':time.perf_counter()-start}


class PersistentBatchBranchPool:
    def __init__(self,*,worker_count,sgp4_asset_folder=None):
        if type(worker_count) is not int or worker_count<1:raise ValueError('EXPLICIT_WORKER_COUNT_REQUIRED')
        self.worker_count=worker_count;self._pool=None;self.closed=False
        self.last_failure_evidence=None
        self.folder=sgp4_asset_folder;self.token=None
        self.initializer=None;self.initargs=()
        if sgp4_asset_folder is not None:
            from ..b4_branch_multiprocessing import _asset_token
            self.token=_asset_token(sgp4_asset_folder)
            self.initializer=_initialize_sgp4_worker;self.initargs=(sgp4_asset_folder,self.token)

    def evaluate(self,engine,validator,actions,forecast):
        if self.closed:raise RuntimeError('POOL_ALREADY_SHUT_DOWN')
        if self._pool is None:
            self._pool=ProcessPoolExecutor(max_workers=self.worker_count,mp_context=mp.get_context('spawn'),
                initializer=self.initializer,initargs=self.initargs)
        before=engine.canonical_state_sha256()
        self.last_failure_evidence=None
        if self.folder is None:
            blob=pickle.dumps((engine,validator),protocol=pickle.HIGHEST_PROTOCOL);transport='SYNTHETIC_PICKLE'
        else:
            from ..b4_branch_multiprocessing import encode_root
            blob=encode_root((engine,validator),self.token);transport='FROZEN_SGP4'
        tasks=[BatchBranchTask(i,blob,transport,a,forecast,before) for i,a in enumerate(actions)]
        futures=[];values=[];i=-1;phase='SUBMISSION'
        try:
            for i,task in enumerate(tasks):futures.append(self._pool.submit(execute_batch_task,task))
            phase='RESULT_MERGE'
            # Parent merges by HOLD/P1... order; completion order is irrelevant.
            for i,future in enumerate(futures):
                value=future.result()
                if value['index']!=i:raise AssertionError('WORKER_CANONICAL_ORDER_MISMATCH')
                values.append(value)
        except BaseException as error:
            # Retain completed-prefix evidence before pool shutdown. It must
            # never be reused as a successful controller decision or retry.
            self.last_failure_evidence={'status':'EXECUTION_FAILURE','failed_merge_index':i,
                'failed_phase':phase,
                'exception_type':type(error).__name__,'exception_message':str(error),
                'root_hash':before,'forecast_sha256':forecast.sha256,
                'action_ids':[a.batch_id for a in actions],'completed_prefix':values,
                'scientific_result_usable':False}
            self.last_failure_evidence['cancel_results']=[future.cancel() for future in futures]
            self.shutdown()
            self.last_failure_evidence['pool_closed']=self.closed
            self.last_failure_evidence['live_hash_after_failure']=engine.canonical_state_sha256()
            raise
        if engine.canonical_state_sha256()!=before:raise AssertionError('PARALLEL_CONTROLLER_MUTATED_ROOT')
        return values

    def shutdown(self):
        if self._pool is not None:
            self._pool.shutdown(wait=True,cancel_futures=True);self._pool=None
        self.closed=True

    def __enter__(self):return self
    def __exit__(self,*exc):self.shutdown()


class JointRolloutController:
    controller_id='B4-v2'
    def __init__(self,validator,*,rollout_cap,branch_pool=None):
        if type(rollout_cap) is not int or rollout_cap<1:raise ValueError('EXPLICIT_ROLLOUT_BUDGET_REQUIRED')
        self.validator,self.rollout_cap,self.branch_pool=validator,rollout_cap,branch_pool

    def observe(self,engine,pool,*,horizon_s):
        if engine.decision_root_sha256()!=pool.root_sha256:raise ValueError('B4_COMMON_POOL_ROOT_MISMATCH')
        if len(pool.actions)>self.rollout_cap:raise ValueError('CANNOT_PARTIALLY_EVALUATE_REQUIRED_POOL')
        before=engine.canonical_state_sha256()
        forecast=BatchPersistenceForecast.from_current_state(engine,horizon_s)
        if self.branch_pool is None:
            evaluator=JointRootRolloutEvaluator(engine,self.validator)
            results=[evaluator.evaluate(a,forecast) for a in pool.actions];timing=[]
        else:
            values=self.branch_pool.evaluate(engine,self.validator,pool.actions,forecast)
            results=[v['result'] for v in values]
            timing=[{k:v[k] for k in ('index','pid','worker_wall_s')} for v in values]
        best_index=0
        for i,r in enumerate(results):
            if not r['valid']:raise AssertionError('COMMON_POOL_ROLLOUT_INVALID')
            if r['J_H_bit_s']<results[best_index]['J_H_bit_s']:best_index=i
        after=engine.canonical_state_sha256()
        if after!=before:raise AssertionError('B4_OBSERVE_MUTATED_LIVE_ENGINE')
        return BatchControllerDecision(pool.actions[best_index],{
            'branches':results,'live_before_hash':before,'live_after_hash':after,
            'selected_pool_index':best_index,'pool_sha256':pool.pool_sha256,
            'exact_tie_policy':'HOLD_FIRST_THEN_CANONICAL_POOL_ORDER',
            'forecast_sha256':forecast.sha256,'engineering_worker_timing':timing,
            'scientific_status':'DRAFT_NOT_FROZEN'})
