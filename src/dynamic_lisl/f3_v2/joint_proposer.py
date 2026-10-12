"""Result-blind bounded joint pool. Budgets are explicit engineering inputs."""
from __future__ import annotations

from dataclasses import dataclass, replace
import itertools

from .joint_action import JointAction, canonical_sha256, terminal_state_hash


@dataclass(frozen=True)
class JointSearchBudget:
    singleton_cap: int
    per_stratum_slots: int
    beam_width: int
    max_non_hold: int
    max_members: int
    expansion_cap: int
    validation_cap: int
    rollout_cap: int

    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in self.__dict__.values()):
            raise ValueError("POSITIVE_EXPLICIT_SEARCH_BUDGETS_REQUIRED")
        if self.max_members>4:raise ValueError('MAX_JOINT_MEMBERS_EXCEEDS_AUTHORIZED_FOUR')
        if self.singleton_cap != 2*self.per_stratum_slots:
            raise ValueError("EXPLICIT_TWO_STRATUM_SINGLETON_ALLOCATION_REQUIRED")
        if self.max_non_hold < self.singleton_cap+self.max_members-1:
            raise ValueError("POOL_MUST_RESERVE_SINGLETONS_AND_AVAILABLE_SIZES")
        if self.rollout_cap < 1+self.max_non_hold:
            raise ValueError("ROLLOUT_CAP_MUST_COVER_HOLD_AND_COMPLETE_COMMON_POOL")
        if min(self.expansion_cap,self.validation_cap)<self.singleton_cap:
            raise ValueError("SINGLETON_VALIDATION_BUDGET_INSUFFICIENT")


@dataclass(frozen=True)
class JointProposalPool:
    root_sha256: str
    pool_sha256: str
    actions: tuple
    plans: tuple
    audit: dict
    physical_singletons: tuple

    def public_document(self):
        return {"schema":"f3_v2_joint_proposal_pool_v1","root_sha256":self.root_sha256,
                "pool_sha256":self.pool_sha256,"actions":[a.to_dict() for a in self.actions],
                "audit":self.audit}


class BoundedJointProposer:
    def __init__(self, validator, budget):
        if budget.max_members>validator.physical_validator.max_batch_replace:
            raise ValueError("SEARCH_EXCEEDS_PHYSICAL_ACTION_CONTRACT")
        self.validator,self.budget=validator,budget

    def propose(self, executor, members, *, decision_root_sha256=None):
        before=terminal_state_hash(executor)
        root=before if decision_root_sha256 is None else decision_root_sha256
        members=tuple(members)
        if len({m.member_id for m in members})!=len(members):
            raise ValueError("DUPLICATE_RAW_MEMBER_ID")
        frame=self.validator.physical_validator.absolute_time_frame_id
        def action(ms):return JointAction(executor.now,frame,root,canonical_sha256([]),tuple(ms))
        screened=[];pruned=[]
        for m in sorted(members,key=lambda m:m.member_id):
            p=self.validator.physical_validator.evaluate(executor,action((m,)),decision_root_sha256=root)
            if not p.accepted:
                pruned.append({"member_ids":[m.member_id],"reason":p.reason,"stage":"PHYSICAL"});continue
            row=p.member_results[0]
            screened.append((m,row))
        def single_key(item):
            m,r=item
            return (-r['usable_lifetime_s'],int(r['window'].get('plane_gap') or 0),m.old_binding,m.new_terminal_pair,m.member_id)
        groups={mode:sorted((x for x in screened if x[1]['transition_mode']==mode),key=single_key)
                for mode in ('MBB','BBM')}
        chosen=groups['MBB'][:self.budget.per_stratum_slots]+groups['BBM'][:self.budget.per_stratum_slots]
        missing=self.budget.singleton_cap-len(chosen)
        leftovers=[x for mode in ('MBB','BBM') for x in groups[mode][self.budget.per_stratum_slots:]]
        chosen+=sorted(leftovers,key=lambda x:(0 if x[1]['transition_mode']=='MBB' else 1,single_key(x)))[:missing]
        chosen.sort(key=lambda x:(0 if x[1]['transition_mode']=='MBB' else 1,single_key(x)))
        chosen=[(replace(m,canonical_index=i),r) for i,(m,r) in enumerate(chosen)]
        selected=tuple(m for m,_ in chosen)
        lifetime={m.canonical_index:r['usable_lifetime_s'] for m,r in chosen}
        def key(ms):
            usable=[lifetime[m.canonical_index] for m in ms]
            return (-min(usable),-sum(usable),tuple(m.canonical_index for m in ms))
        evaluated={};validation_count=0;expansions=0;exhausted=False
        def evaluate(ms):
            nonlocal validation_count,expansions,exhausted
            ids=tuple(m.canonical_index for m in ms)
            if ids in evaluated:return evaluated[ids]
            if validation_count>=self.budget.validation_cap or expansions>=self.budget.expansion_cap:
                exhausted=True;return None
            validation_count+=1;expansions+=1
            p=self.validator.evaluate(executor,action(ms),decision_root_sha256=root)
            evaluated[ids]=p
            if not p.accepted:pruned.append({'member_ids':[m.member_id for m in ms],'reason':p.reason,'stage':'JOINT'})
            return p
        singleton_plans=[]
        for m in selected:
            p=evaluate((m,))
            if p and p.accepted:singleton_plans.append(p)
        # Unsafe network prefixes may expand; only proven physical/resource
        # conflicts are excluded. Economic/controller scores never enter beam.
        prefixes=sorted(((m,) for m in selected),key=key)[:self.budget.beam_width]
        joint_by_size={}
        for size in range(2,self.budget.max_members+1):
            next_prefixes=[];safe=[]
            for prefix in prefixes:
                for m in selected:
                    if m.canonical_index<=prefix[-1].canonical_index:continue
                    ms=prefix+(m,)
                    if any(m.footprint & previous.footprint for previous in prefix):
                        pruned.append({'member_ids':[x.member_id for x in ms],'reason':'TERMINAL_FOOTPRINT_CONFLICT','stage':'RESOURCE_PROOF'});continue
                    p=evaluate(ms)
                    if p is None:break
                    if p.commands:next_prefixes.append(ms)
                    if p.accepted:safe.append(p)
                if exhausted:break
            joint_by_size[size]=sorted(safe,key=lambda p:key(p.action.members))[:self.budget.beam_width]
            prefixes=sorted(next_prefixes,key=key)[:self.budget.beam_width]
            if not prefixes or exhausted:break
        output=list(singleton_plans)
        # Mandatory one witness per available size first; round-robin remainder.
        queues={size:list(vals) for size,vals in sorted(joint_by_size.items())}
        while any(queues.values()) and len(output)<self.budget.max_non_hold:
            for size,q in queues.items():
                if q and len(output)<self.budget.max_non_hold:output.append(q.pop(0))
        output.sort(key=lambda p:(len(p.action.members),tuple(m.canonical_index for m in p.action.members)))
        hold=action(())
        identities=[hold.identity_document()]+[p.action.identity_document() for p in output]
        audit={'raw_member_ids':sorted(m.member_id for m in members),
               'physical_screened_count':len(screened),'singleton_member_ids':[m.member_id for m in selected],
               'singleton_safety_rejections_are_expandable':True,'pruned':pruned,
               'joint_validation_calls':validation_count,'structural_expansions':expansions,
               'budget_exhausted':exhausted,'beam_width':self.budget.beam_width,
               'raw_physical_space_not_complete_joint_space':True,
               'coverage_by_size':{str(s):sum(len(p.action.members)==s for p in output) for s in range(1,self.budget.max_members+1)},
               'maximum_optimality_claim':False,'performance_inputs_read':False}
        digest=canonical_sha256({'root_sha256':root,'identities':identities,'audit':audit})
        actions=(replace(hold,joint_proposal_set_sha256=digest),)+tuple(replace(p.action,joint_proposal_set_sha256=digest) for p in output)
        plans=tuple(replace(p,action=a) for p,a in zip(output,actions[1:]))
        if terminal_state_hash(executor)!=before:raise AssertionError('PROPOSER_MUTATED_ROOT')
        return JointProposalPool(root,digest,actions,plans,audit,selected)
