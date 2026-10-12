"""Current-only, deterministic engineering policies over the pinned N2 executor."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import importlib.util
import math
from pathlib import Path

from .bindings import EngineeringBinding
from .n1a import digest, require
from .n2_actions import Hold, Add, Drop, Replace, Setup, action_key
from .n2_controller import AtomicTopologyController, validate_n2


class N3EvidenceBinding(EngineeringBinding):
    def verify(self):
        spec = importlib.util.spec_from_file_location('n3_vc', Path(__file__).resolve().parents[1]/'tools/version_control.py')
        vc = importlib.util.module_from_spec(spec); spec.loader.exec_module(vc)
        info = vc.file_info(vc.safe_path(self.project_root, self.manifest_path))
        require(info['sha256'] == self.expected_manifest_sha256, 'N3_MANIFEST_ANCHOR_MISMATCH')
        m = vc.read_json(vc.safe_path(self.project_root, self.manifest_path))
        require(m['schema'] == 'dynamic_k_n3_candidate_v1' and m['candidate_revision_id'] == '0007'
                and m['formal_experiments_authorized'] is False, 'N3_UNAUTHORIZED_BINDING')
        seen = set()
        for row in m['files'] + list(m['anchors'].values()):
            require(row['path'] not in seen, 'DUPLICATE_N3_BINDING'); seen.add(row['path'])
            require(vc.file_info(vc.safe_path(self.project_root, row['path'])) ==
                    {k:row[k] for k in ('byte_count','sha256')}, 'N3_FILE_CHANGED:'+row['path'])
        c = vc.read_json(vc.safe_path(self.project_root, m['configuration_path']))
        require(all(v is None for v in c['scientific_parameters'].values()) and
                all(c[k] is None for k in ('decision_period_s','search_budget','maximum_concurrent_actions',
                    'fixed_K','Kmax','alpha','connectivity_rejection_policy','minimum_delivery_rate_hard_mask'))
                and c['formal_experiments_authorized'] is False, 'N3_SCIENCE_FREEZE_FORBIDDEN')
        return dict(scope='ENGINEERING_TEST_ONLY',candidate_revision_id='0007',
                    implementation_manifest=dict(path=self.manifest_path,**info),anchors=m['anchors'])


@dataclass(frozen=True)
class CurrentObservation:
    """No trace, future agenda, horizon, evaluator or final metrics are exposed."""
    time_s: float
    nodes: tuple
    fixed_edges: tuple
    admit_edges: tuple
    commodities: tuple
    queues: tuple
    in_flight: tuple
    injection_rates: tuple
    links: tuple
    terminal_states: tuple
    reservations: tuple
    K_admit: int


def observe_current(atomic):
    e = atomic.engine; ex = e.executor
    return CurrentObservation(e.now,e.nodes,e.fixed_edges,tuple(e.graph['admit_edges']),
        tuple((c.commodity_id,c.source,c.destination) for c in e.commodities),
        tuple((n,c,v) for (n,c),v in sorted(e.queues.bits.items())),
        tuple((a,b,c,v) for ((a,b),c),v in sorted(e.in_flight.bits.items())),
        tuple(sorted(e.trace.rate_at(e.now).items())),
        tuple((lid,tuple(l.endpoints),l.draining) for lid,l in sorted(ex.links.items())),
        tuple((tid,t.phase,t.reservation_id,t.current_peer) for tid,t in sorted(ex.terminals.items())),
        tuple(sorted(ex.reservations)),
        sum(not l.draining and all(ex.terminals[x].phase=='ACTIVE' for x in l.endpoints) for l in ex.links.values()))


def reachable(edges, start, end):
    graph = {}
    for a,b in edges:
        graph.setdefault(a,set()).add(b); graph.setdefault(b,set()).add(a)
    todo = [start]; seen = {start}
    while todo:
        node = todo.pop()
        if node == end:return True
        for other in sorted(graph.get(node,())):
            if other not in seen:seen.add(other);todo.append(other)
    return False


def demands(obs):
    dest = {c:d for c,_,d in obs.commodities}
    # Separate queue bits and current injection bit/s; no addition of different units.
    return tuple((n,dest[c],bits,0.) for n,c,bits in obs.queues if bits>0.) + tuple(
        (s,d,0.,r) for c,s,d in obs.commodities for key,r in obs.injection_rates if key==c and r>0.)


def projected_edges(obs, action):
    # Rebuild from ownership, preserving fixed edges / another link on the same edge.
    removed = {r.link_id for r in action.old} if isinstance(action,Replace) else set()
    edges = set(obs.fixed_edges)
    for lid,ends,draining in obs.links:
        if not draining and lid not in removed:edges.add(tuple(sorted((ends[0][0],ends[1][0]))))
    edges.add(tuple(sorted((action.a[0],action.b[0]))))
    return tuple(sorted(edges))


class StaticHold:
    name = 'STATIC_HOLD'
    def select(self, observation, candidates):
        require(type(observation) is CurrentObservation,'CURRENT_OBSERVATION_REQUIRED')
        require(any(type(a) is Hold for a in candidates),'HOLD_CANDIDATE_MISSING')
        return Hold(),dict(reason='NO_PROACTIVE_TOPOLOGY_ACTION',ordering='HOLD',scores=[])


class ReactiveDynamicK:
    name = 'REACTIVE_DYNAMIC_K'
    def select(self, observation, candidates):
        require(type(observation) is CurrentObservation,'CURRENT_OBSERVATION_REQUIRED')
        obs = observation; current = tuple(obs.admit_edges); needed = demands(obs); scored = []
        for action in candidates:
            if not isinstance(action,(Add,Replace)):continue
            after = projected_edges(obs,action)
            improves = [(n,d,q,r) for n,d,q,r in needed if not reachable(current,n,d) and reachable(after,n,d)]
            loses = any(reachable(current,n,d) and not reachable(after,n,d) for n,d,_,_ in needed)
            if not improves or loses:continue
            # Local preference only: reuse a redundant old connection if possible, then ADD.
            # This is a ranking, never a connectedness / delivery-rate rejection mask.
            replace = isinstance(action,Replace)
            key = (-sum(q for _,_,q,_ in improves),-sum(r for _,_,_,r in improves),
                   0 if replace else 1,0 if replace and action.mode=='MBB' else 1,action_key(action))
            scored.append((key,action))
        if scored:
            key,action = min(scored,key=lambda row:row[0])
            return action,dict(reason='CURRENT_UNREACHABLE_DEMAND_BECOMES_REACHABLE',
                ordering='queue_bits_desc,current_rate_desc,REPLACE_before_ADD,MBB_before_BBM,action_key_lex',
                scores=[dict(action=asdict(a),sort_key=k) for k,a in sorted(scored,key=lambda row:row[0])])
        # Exact no-demand predicate avoids an unapproved low-utilization threshold.
        idle = not needed and not any(v>0 for _,_,_,v in obs.in_flight)
        drops = sorted((a for a in candidates if isinstance(a,Drop)),key=action_key)
        if idle and drops:
            return drops[0],dict(reason='NO_CURRENT_QUEUE_IN_FLIGHT_OR_INJECTION',ordering='action_key_lex',scores=[])
        return Hold(),dict(reason='NO_RETAINED_ACTION_WITH_CURRENT_REACHABILITY_BENEFIT_OR_SAFE_IDLE_DROP',
                           ordering='HOLD',scores=[])


def serial_candidates(source):
    return dict(diagnostics=deepcopy(source['diagnostics']),replacement_coverage=source['replacement_coverage'],
        masks=[dict(action=asdict(x['action']),legal=x['legal'],reason=x['reason']) for x in source['masks']],
        retained=[asdict(a) for a in source['candidates']])


class ClosedLoopBaseline:
    """One atomic action/explicit TEST_ONLY epoch; all time advances through N2."""
    def __init__(self, atomic, policy, *, test_epochs_s, test_setup, binding, test_retention_budgets=None):
        require(type(atomic) is AtomicTopologyController and type(policy) in (StaticHold,ReactiveDynamicK), 'N3_PINNED_EXECUTOR_AND_POLICY_REQUIRED')
        require(isinstance(binding,N3EvidenceBinding),'N3_BINDING_REQUIRED');binding.verify()
        epochs = tuple(test_epochs_s)
        require(all(type(t) in (int,float) and math.isfinite(t) and atomic.engine.now<=t<=atomic.evaluator.base.T for t in epochs)
                and all(a<b for a,b in zip(epochs,epochs[1:])), 'INVALID_TEST_ONLY_EPOCHS')
        require(type(test_setup) is Setup and test_setup.valid(),'EXPLICIT_TEST_SETUP_REQUIRED')
        self.atomic=atomic;self.policy=policy;self.epochs=epochs;self.setup=test_setup;self.binding=binding
        self.budgets=deepcopy(test_retention_budgets);self.index=0;self.audit=[]
        self.log_cursor=len(atomic.engine.executor.log)
        e=atomic.engine
        self.fixture_identity=dict(initial_state_sha256=e.canonical_state_sha256(),
            traffic_trace_sha256=digest(e.trace.to_dict()),geometry_sha256=atomic.physical_sha256,
            nodes=e.nodes,fixed_edges=e.fixed_edges,capacity_bit_s=e.capacity_bit_s,
            service_kernel=type(e).__name__,T_s=atomic.evaluator.base.T,
            TEST_ONLY_epochs_s=epochs,TEST_ONLY_setup=asdict(test_setup),TEST_ONLY_retention_budgets=self.budgets)

    def step(self):
        require(self.index<len(self.epochs),'NO_REMAINING_TEST_EPOCH')
        self.binding.verify();t=self.epochs[self.index];self.atomic.advance_to(t)
        obs=observe_current(self.atomic);before=self.atomic.engine.canonical_state_sha256()
        source=self.atomic.candidates(self.setup,retention_budgets=self.budgets)
        catalog_scope=dict(registered_rows_in_supplied_physical_input=sum(len(ws) for ws in self.atomic.validator.physical.catalog.windows.values()),
            physical_input_sha256=self.atomic.physical_sha256,
            status_scope='CURRENT_CANDIDATES_WITHIN_SUPPLIED_PINNED_CATALOG_ONLY',
            fixture_omitted_or_unregistered_windows_are_not_budget_truncation=True)
        action,selection=self.policy.select(obs,tuple(source['candidates']))
        require(action in source['candidates'],'POLICY_SELECTED_NON_RETAINED_ACTION')
        require(before==self.atomic.engine.canonical_state_sha256(),'CANDIDATE_OR_POLICY_MUTATED_SERVICE')
        receipt=self.atomic.submit(action)
        require(receipt['accepted'],'REVALIDATED_N2_ACTION_REJECTED:'+str(receipt['reason']))
        ex=self.atomic.engine.executor
        self.audit.append(dict(epoch_index=self.index,time_s=t,current_observation=asdict(obs),
            candidate_audit=dict(serial_candidates(source),catalog_scope=catalog_scope),selected_action=asdict(action),selection=selection,
            actual_gate_receipt=receipt,before_state_sha256=before,after_state_sha256=self.atomic.engine.canonical_state_sha256(),
            after_observation=asdict(observe_current(self.atomic)),
            terminal_events_since_previous_epoch=deepcopy(ex.log[self.log_cursor:]),
            K_timeline_to_epoch=deepcopy(self.atomic.last_result['dynamic_K_time_series'])))
        self.log_cursor=len(ex.log);self.index+=1
        return deepcopy(self.audit[-1])

    def run(self):
        while self.index<len(self.epochs):self.step()
        original=self.atomic.run();self.binding.verify()
        result=dict(schema='dynamic_k_n3_engineering_result_v1',scope='ENGINEERING_TEST_ONLY',
            bindings=self.binding.verify(),controller=self.policy.name,fixture_identity=deepcopy(self.fixture_identity),
            decision_audit=deepcopy(self.audit),terminal_events_after_last_epoch=deepcopy(self.atomic.engine.executor.log[self.log_cursor:]),
            n2_result=original,metrics=extract_metrics(original),
            non_HOLD_accepted_count=sum(r['accepted'] and r['action']['kind']!='HOLD' for r in original['action_receipts']),
            scientific_gate_pass=False,formal_experiments_executed=False,N4_implemented=False)
        validate_n3(result);return result

    def clone(self):return deepcopy(self)
    def checkpoint(self):return self.clone()
    @classmethod
    def restore(cls, checkpoint):
        require(type(checkpoint) is cls,'INVALID_N3_CHECKPOINT');return checkpoint.clone()


def extract_metrics(result):
    age=result['n1b_result'];core=age['n1a_result']
    fields=('E_LCT_J','DeltaE_LCT_J','J_T_bit_s','N_T_bits','R_del_T','offered_bits','delivered_bits',
            'queued_bits','in_flight_bits','evaluation_completed_normally','all_offered_business_delivered')
    metrics={k:core[k] for k in fields}
    for k in ('delivered_bit_age_integral_bit_s','mean_delivered_fluid_delay_s','mean_delay_absolute_error_bound_s'):
        metrics[k]=age[k]
    metrics['K_time_series']=deepcopy(result['dynamic_K_time_series'])
    return metrics


def validate_n3(r):
    require(r['schema']=='dynamic_k_n3_engineering_result_v1' and r['scope']=='ENGINEERING_TEST_ONLY'
        and r['scientific_gate_pass'] is r['formal_experiments_executed'] is r['N4_implemented'] is False,'N3_RESULT_SCOPE')
    validate_n2(r['n2_result'])
    require(r['controller'] in ('STATIC_HOLD','REACTIVE_DYNAMIC_K'),'N3_UNKNOWN_POLICY')
    require(r['metrics']==extract_metrics(r['n2_result']),'N3_METRICS_CHANGED')
    receipts=r['n2_result']['action_receipts'];audit=r['decision_audit']
    require(len(audit)==len(receipts) and len(audit)==len(r['fixture_identity']['TEST_ONLY_epochs_s']),'N3_ONE_ACTION_PER_EPOCH')
    require(all(row['actual_gate_receipt']==receipt for row,receipt in zip(audit,receipts)),'N3_RECEIPT_AUDIT_MISMATCH')
    count=sum(x['accepted'] and x['action']['kind']!='HOLD' for x in receipts)
    require(type(r['non_HOLD_accepted_count']) is int and r['non_HOLD_accepted_count']==count,'N3_NON_HOLD_COUNT')
    if r['controller']=='STATIC_HOLD':require(count==0,'STATIC_HOLD_CHANGED_TOPOLOGY')
    require(r['metrics']['evaluation_completed_normally'] and
            r['n2_result']['n1b_result']['n1a_result']['T_s']==r['fixture_identity']['T_s'],'N3_FIXED_HORIZON_INCOMPLETE')


def paired_runs(atomic, *, test_epochs_s, test_setup, binding):
    outputs={}
    for policy in (StaticHold(),ReactiveDynamicK()):
        outputs[policy.name]=ClosedLoopBaseline(atomic.clone(),policy,test_epochs_s=test_epochs_s,
                                              test_setup=test_setup,binding=binding).run()
    require(outputs['STATIC_HOLD']['fixture_identity']==outputs['REACTIVE_DYNAMIC_K']['fixture_identity'],'N3_UNFAIR_INPUTS')
    return outputs
