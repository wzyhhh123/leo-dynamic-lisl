"""Atomic real-terminal dispatch over the unchanged, pinned N1b evaluator."""
from copy import deepcopy
from dataclasses import asdict
from .n1a import require,digest
from .n1b_evaluator import DeliveredFluidEvaluator,validate_n1b
from .n2_binding import N2EvidenceBinding
from .n2_actions import Hold,ActionValidator
from .n2_candidates import CandidateSource


class AtomicTopologyController:
    def __init__(self,evaluator,physical,*,binding):
        require(type(evaluator) is DeliveredFluidEvaluator and isinstance(binding,N2EvidenceBinding),'PINNED_N1B_AND_N2_REQUIRED')
        binding.verify();evaluator.binding.verify()
        require(not evaluator.base.engine.actions,'LEGACY_POLICY_SCRIPT_ACTIONS_NOT_ALLOWED_IN_N2')
        self.evaluator=evaluator;self.validator=ActionValidator(physical);self.source=CandidateSource(self.validator)
        self.binding=binding;self.receipts=[];self.last_result=None
        self.physical_sha256=self._physical_digest()

    @property
    def engine(self):return self.evaluator.base.engine

    def _physical_digest(self):
        p=self.validator.physical
        rows=[w.to_dict() for _,ws in sorted(p.catalog.windows.items()) for w in ws]
        g=p.guard
        guard=dict(scope=g.scope)
        if hasattr(g,'model'):
            guard.update(TLE_records=g.model.records,duration=g.model.duration_s,
                geometry_config=asdict(g.config),earth_radius_km=g.earth_radius_km)
        else:guard['rejections']=sorted((repr(k),v) for k,v in g.rejections.items())
        return digest(dict(windows=rows,planes=sorted(p.catalog.plane_by_satellite.items()),guard=guard))

    def _verify(self):
        self.binding.verify();self.evaluator.binding.verify()
        require(self._physical_digest()==self.physical_sha256,'N2_PHYSICAL_INPUT_CHANGED')
        require(self.engine.now==self.engine.executor.now,'N2_CLOCK_MISMATCH')

    def candidates(self,setup,*,retention_budgets=None):
        self._verify()
        return self.source.generate(self.engine.executor,setup,retention_budgets=retention_budgets)

    def submit_batch(self,actions):
        self._verify()
        return dict(accepted=False,reason='JOINT_ACTION_EXECUTION_DEFERRED',requested_count=len(tuple(actions)),
                    maximum_concurrent_actions=None)

    def submit(self,action):
        self._verify()
        ex=self.engine.executor
        plan=self.validator.validate(ex,action)
        receipt=dict(action_id=len(self.receipts)+1,time_s=self.engine.now,
            action=asdict(action) if hasattr(action,'__dataclass_fields__') else repr(action),
            accepted=plan['accepted'],reason=plan['reason'],before_terminal_sha256=digest(ex.snapshot()))
        if not plan['accepted']:
            self.receipts.append(receipt);return deepcopy(receipt)
        cursor=len(ex.log)
        if not isinstance(action,Hold):
            ex.submit(plan['commands'])
            require(ex.snapshot()==plan['trial'].snapshot(),'N2_TRIAL_LIVE_EXECUTION_MISMATCH')
        new=ex.log[cursor:]
        actual=sorted({r['details']['link_id'] for r in new if r['event']=='DRAINING'})
        require(actual==plan.get('actual_immediate_release_ids',[]),'N2_ACTUAL_RELEASE_SET_MISMATCH')
        rid=next((r['details']['reservation_id'] for r in new if r['event']=='RESERVE_BOTH'),None)
        receipt.update(mode=plan['mode'],requested_release_refs=[asdict(r) for r in plan['release_refs']],
            actual_immediate_release_ids=actual,reservation_id=rid,terminal_log_start=cursor,
            geometry=plan.get('physical'),after_terminal_sha256=digest(ex.snapshot()))
        if receipt['geometry'] is not None:
            receipt['geometry']=deepcopy({k:v for k,v in receipt['geometry'].items() if k!='command'})
        self.receipts.append(receipt)
        self.advance_to(self.engine.now)
        return deepcopy(receipt)

    def release_audit(self):
        logs=self.engine.executor.log
        audit=[]
        for receipt in self.receipts:
            if not receipt['accepted']:continue
            records=logs[receipt['terminal_log_start']:]
            for ref in receipt['requested_release_refs']:
                lid=ref['link_id']
                draining=[r['time'] for r in records if r['event']=='DRAINING' and r['details']['link_id']==lid]
                down=[dict(time_s=r['time'],reason=r['details']['reason']) for r in records
                      if r['event']=='LINK_DOWN' and r['details']['link_id']==lid]
                aborted=any(r['event']=='ABORT' and r['details']['reservation_id']==receipt['reservation_id'] for r in records)
                status=('COMPLETE' if down and draining else 'NATURAL_END_BEFORE_REQUESTED_RELEASE' if down else
                        'DRAINING' if draining else 'SETUP_ABORTED_NO_RELEASE' if aborted else 'PENDING_SETUP')
                audit.append(dict(action_id=receipt['action_id'],reference=ref,status=status,
                                  draining_times_s=draining,link_down=down))
        return audit

    def advance_to(self,t):
        self._verify()
        original=self.evaluator.advance_to(t)
        ex=self.engine.executor
        k=sum(not l.draining and all(ex.terminals[e].phase=='ACTIVE' for e in l.endpoints) for l in ex.links.values())
        draining=sum(l.draining for l in ex.links.values())
        states=ex.snapshot()['terminals']
        setup=sum(r['phase'] in ('RETARGETING','ACQUIRING') for r in states)
        result=dict(schema='dynamic_k_n2_engineering_result_v1',scope='ENGINEERING_TEST_ONLY',
            bindings=self.binding.verify(),physical_input_sha256=self.physical_sha256,
            n1b_result=original,K_admit=k,K_draining=draining,setup_terminal_count=setup,
            reserved_terminal_count=sum(r['reservation_id'] is not None for r in states),
            dynamic_terminal_states=states,
            dynamic_K_time_series=[dict(row,K_admit=row['K_active_admissible']) for row in original['n1a_result']['K_time_series']],
            action_receipts=deepcopy(self.receipts),release_audit=self.release_audit(),
            scientific_gate_pass=False,formal_experiments_executed=False,N3_implemented=False)
        validate_n2(result);self.last_result=deepcopy(result)
        return result

    def run(self):return self.advance_to(self.evaluator.base.T)
    def clone(self):return deepcopy(self)
    def checkpoint(self):return self.clone()
    @classmethod
    def restore(cls,checkpoint):
        require(type(checkpoint) is cls,'INVALID_N2_CHECKPOINT');return checkpoint.clone()


def validate_n2(r):
    require(r['schema']=='dynamic_k_n2_engineering_result_v1' and r['scope']=='ENGINEERING_TEST_ONLY'
            and r['scientific_gate_pass'] is r['formal_experiments_executed'] is r['N3_implemented'] is False,'N2_RESULT_SCOPE')
    validate_n1b(r['n1b_result'])
    states=r['dynamic_terminal_states']
    require(len(states)==320 and len({tuple(s['terminal_id']) for s in states})==320,'N2_TERMINAL_INVENTORY')
    require(all(s['phase'] in ('IDLE','ACTIVE','DRAINING','RETARGETING','ACQUIRING') for s in states),'N2_UNKNOWN_STATE')
    require(all(type(r[k]) is int and 0<=r[k]<=320 for k in
        ('K_admit','K_draining','setup_terminal_count','reserved_terminal_count')),'N2_INVALID_COUNT')
    require(sum(s['phase']=='ACTIVE' for s in states)==2*r['K_admit'],'N2_K_STATE_MISMATCH')
    require(sum(s['phase']=='DRAINING' for s in states)==2*r['K_draining'],'N2_DRAINING_STATE_MISMATCH')
    require(sum(s['phase'] in ('RETARGETING','ACQUIRING') for s in states)==r['setup_terminal_count'],'N2_SETUP_STATE_MISMATCH')
    require(sum(s['reservation_id'] is not None for s in states)==r['reserved_terminal_count'],'N2_RESERVED_STATE_MISMATCH')
    last=r['dynamic_K_time_series'][-1]
    require(last['K_admit']==r['K_admit'] and last['K_draining']==r['K_draining']
            and last['setup_terminal_count']==r['setup_terminal_count'],'N2_K_TIMELINE_MISMATCH')
