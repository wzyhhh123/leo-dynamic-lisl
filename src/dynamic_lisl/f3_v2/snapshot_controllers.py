"""New B0/B1/B2/B3 adapters; frozen scheduler-consistent V_v2 is reused."""
from __future__ import annotations
from dataclasses import dataclass
from copy import copy,deepcopy
from collections import defaultdict
import math

from ..scientific_snapshot import ScientificSnapshotEvaluator
from ..load_aware_router import DeterministicLoadAwareRouter


def current_snapshot_view(engine):
    """Install the frozen E2 current-state context on a private router only.

    E2 refreshes live routes on physical events. A later analytic snapshot is a
    separate route evaluation and needs a context at its exact observation time;
    it must not refresh the live fast-layer routes or advance the network.
    """
    if not isinstance(engine.router,DeterministicLoadAwareRouter):return engine
    view=copy(engine)
    view.router=deepcopy(engine.router)
    edge_rates=defaultdict(float)
    for (edge,_commodity),value in engine.service_rates.items():edge_rates[tuple(edge)]+=value
    utilization={edge:value/engine.capacity_bit_s for edge,value in edge_rates.items()}
    node_queue=defaultdict(float)
    for (node,_commodity),value in engine.queues.bits.items():node_queue[node]+=value
    view.router.update_current_state(engine.now,utilization,node_queue,engine.trace.rate_at(engine.now))
    return view


def improvement(hold,candidate):
    if math.isinf(hold) and math.isinf(candidate):return 0.0
    return hold-candidate


def number(value):
    return value if math.isfinite(value) else ('+infinity' if value>0 else '-infinity')


def batch_target_edges(engine,action):
    edges=set(tuple(sorted(e)) for e in engine.graph['admit_edges'])
    # Simultaneous set update: no sequential controller/router decisions.
    old={tuple(e[0] for e in m.old_binding) for m in action.members}
    new={tuple(e[0] for e in m.new_terminal_pair) for m in action.members}
    return tuple(sorted((edges-old)|new|set(tuple(sorted(e)) for e in engine.fixed_edges)))


@dataclass(frozen=True)
class BatchControllerDecision:
    action: object
    metadata: dict


class StaticBatchController:
    controller_id='B0-v2'
    def observe(self,engine,pool):
        return BatchControllerDecision(pool.actions[0],{'reason':'STATIC_HOLD','future_traffic_read':False})


class SnapshotBatchController:
    def __init__(self,controller_id,*,eta_aggregation=None,minimum_hold_s=None,initial_age_s=None,initial_bindings=None):
        if controller_id not in ('B1-v2','B2-v2','B3-v2'):raise ValueError('UNKNOWN_SNAPSHOT_CONTROLLER')
        if controller_id=='B3-v2' and eta_aggregation!='min':raise ValueError('EXPLICIT_DRAFT_ETA_AGGREGATION_REQUIRED')
        if controller_id=='B2-v2' and (minimum_hold_s is None or initial_age_s is None or min(minimum_hold_s,initial_age_s)<0):
            raise ValueError('EXPLICIT_HOLD_AND_INITIAL_AGE_REQUIRED')
        if controller_id=='B2-v2' and initial_bindings is None:
            raise ValueError('EXPLICIT_INITIAL_BINDING_SET_REQUIRED')
        self.controller_id=controller_id;self.eta_aggregation=eta_aggregation
        self.minimum_hold_s=minimum_hold_s;self.initial_age_s=initial_age_s
        self.initial_bindings=frozenset(initial_bindings or ())

    def observe(self,engine,pool):
        before=engine.canonical_state_sha256()
        if engine.decision_root_sha256()!=pool.root_sha256:raise ValueError('SCORING_ROOT_MISMATCH')
        evaluator=ScientificSnapshotEvaluator(current_snapshot_view(engine))
        hold=evaluator.evaluate_hold();best=pool.actions[0];best_value=hold.value_bit_s;best_score=0.;records=[]
        if hold.total_unfinished_bits>0:
            for action,plan in zip(pool.actions[1:],pool.plans):
                evaluation=evaluator.evaluate_edges(batch_target_edges(engine,action))
                delta=improvement(hold.value_bit_s,evaluation.value_bit_s)
                eligible=True;eta=None;score=None
                if self.controller_id=='B2-v2':
                    for m in action.members:
                        old=engine.executor._link(m.old_binding)
                        if old is None:raise ValueError('SCORING_OLD_BINDING_MISSING')
                        age=engine.now-old.start+(self.initial_age_s if old.start==0 and m.old_binding in self.initial_bindings else 0)
                        eligible &= age>=self.minimum_hold_s
                if self.controller_id=='B3-v2':
                    eligible=all(r['remaining_lifetime_s']>0 and r['usable_lifetime_s']>0 for r in plan.member_results)
                    if eligible:
                        eta=min(r['usable_lifetime_s']/r['remaining_lifetime_s'] for r in plan.member_results)
                        score=delta*eta if delta>0 else 0.
                        if score>best_score:best,best_score=action,score
                elif eligible and evaluation.value_bit_s<best_value:
                    best,best_value=action,evaluation.value_bit_s
                records.append({'batch_id':action.batch_id,'eligible':eligible,'snapshot':evaluation.to_dict(),
                                'deltaV':number(delta),'eta':eta,'score':None if score is None else number(score)})
        after=engine.canonical_state_sha256()
        if before!=after:raise AssertionError('SNAPSHOT_CONTROLLER_MUTATED_LIVE_STATE')
        return BatchControllerDecision(best,{'controller_id':self.controller_id,'hold':hold.to_dict(),
            'candidates':records,'live_before_hash':before,'live_after_hash':after,
            'common_pool_sha256':pool.pool_sha256,'current_state_only':True,'rollout':False,
            'snapshot_router_context':'E2_CURRENT_STATE_RULE_AT_EXACT_EPOCH_ON_PRIVATE_ROUTER',
            'scientific_status':'DRAFT_NOT_FROZEN','eta_aggregation':self.eta_aggregation})
