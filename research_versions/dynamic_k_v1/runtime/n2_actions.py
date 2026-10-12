"""Typed atomic actions and dry-run validation over the real Gate B executor."""
from dataclasses import dataclass,asdict
from copy import deepcopy
import math
from dynamic_lisl.terminal_executor import pair,Disconnect


@dataclass(frozen=True)
class Setup:
    retarget_a_s:float
    retarget_b_s:float
    acquisition_s:float
    def valid(self):
        return all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in asdict(self).values())

@dataclass(frozen=True)
class LinkRef:
    link_id:str
    endpoints:tuple
    @classmethod
    def from_link(cls,link):return cls(link.link_id,tuple(link.endpoints))

@dataclass(frozen=True)
class Hold:
    kind:str='HOLD'

@dataclass(frozen=True)
class Add:
    a:tuple
    b:tuple
    setup:Setup
    kind:str='ADD'

@dataclass(frozen=True)
class Drop:
    old:LinkRef
    kind:str='DROP'

@dataclass(frozen=True)
class Replace:
    old:tuple
    a:tuple
    b:tuple
    setup:Setup
    mode:str
    kind:str='REPLACE'


def action_key(action):
    return (action.kind,getattr(action,'mode',''),repr(getattr(action,'a',())),repr(getattr(action,'b',())),
            repr(getattr(action,'old',())))

def implicit_releases(executor,a,b):
    ends=pair(a,b);satpair={e[0] for e in ends}
    return tuple(sorted((LinkRef.from_link(l) for l in executor.links.values()
        if any(e in ends for e in l.endpoints) or {e[0] for e in l.endpoints}==satpair),key=lambda r:r.link_id))


class ActionValidator:
    def __init__(self,physical):self.physical=physical
    def validate(self,executor,action):
        def reject(reason,**details):return dict(accepted=False,reason=reason,**details)
        if type(action) not in (Hold,Add,Drop,Replace):return reject('UNKNOWN_ACTION')
        if isinstance(action,Hold):
            if action.kind!='HOLD':return reject('ACTION_KIND_MISMATCH')
            return dict(accepted=True,reason=None,commands=(),release_refs=(),mode='HOLD')
        if executor.events and executor.events[0][0]<=executor.now:return reject('UNSETTLED_EVENTS_ADVANCE_FIRST')
        expected_kind={Add:'ADD',Drop:'DROP',Replace:'REPLACE'}[type(action)]
        if action.kind!=expected_kind:return reject('ACTION_KIND_MISMATCH')
        if isinstance(action,Replace) and type(action.old) is not tuple:return reject('INVALID_RELEASE_SET')
        refs=(action.old,) if isinstance(action,Drop) else (action.old if isinstance(action,Replace) else ())
        if isinstance(action,Replace) and not refs:return reject('REPLACE_REQUIRES_OLD_REFERENCES')
        if any(type(r) is not LinkRef for r in refs):return reject('INVALID_LINK_REFERENCE')
        if len(set(r.link_id for r in refs))!=len(refs):return reject('DUPLICATE_RELEASE_REFERENCE')
        for ref in refs:
            old=executor.links.get(ref.link_id)
            if old is None or old.endpoints!=ref.endpoints:return reject('STALE_OR_WRONG_LINK_REFERENCE')
            if old.draining:return reject('ALREADY_DRAINING')
            if old.release_owner:return reject('RELEASE_OWNERSHIP_CONFLICT')
        geometry=None
        if isinstance(action,Drop):
            commands=(Disconnect(*action.old.endpoints),);mode='DROP'
        else:
            if type(action.setup) is not Setup or not action.setup.valid():return reject('INVALID_SETUP')
            try:ends=pair(action.a,action.b)
            except (TypeError,ValueError):return reject('INVALID_TERMINAL_PAIR')
            if any(e not in executor.terminals for e in ends):return reject('UNKNOWN_DYNAMIC_TERMINAL')
            if any(executor.terminals[e].reservation_id for e in ends):return reject('RESERVATION_CONFLICT')
            implicit=implicit_releases(executor,*ends)
            ids={r.link_id for r in refs};hidden={r.link_id for r in implicit}-ids
            if isinstance(action,Add):
                if implicit:return reject('ADD_WOULD_IMPLICITLY_RELEASE',implicit_release_refs=implicit)
                if any(executor.terminals[e].phase!='IDLE' for e in ends):return reject('ADD_TERMINAL_NOT_IDLE')
                mode='ADD';release_after=()
            elif action.mode=='MBB':
                if implicit or any(executor.terminals[e].phase!='IDLE' for e in ends):return reject('MBB_REQUIRES_FREE_TERMINALS')
                mode='MBB';release_after=tuple(r.endpoints for r in refs)
            elif action.mode=='BBM':
                if hidden:return reject('UNDECLARED_THIRD_PARTY_RELEASE',implicit_release_refs=implicit)
                mode='BBM';release_after=()
            else:return reject('UNKNOWN_REPLACE_MODE')
            geometry=self.physical.evaluate(executor,action.a,action.b,action.setup,release_after)
            if not geometry['accepted']:return reject(geometry['reason'],physical=geometry)
            extra=tuple(r for r in refs if r.link_id not in {x.link_id for x in implicit}) if mode=='BBM' else ()
            commands=tuple(Disconnect(*r.endpoints) for r in extra)+(geometry['command'],)
        trial=executor.clone_for_transaction();cursor=len(trial.log)
        try:trial.submit(commands)
        except ValueError as error:return reject('EXECUTOR_REJECTED',detail=str(error))
        actual={x['details']['link_id'] for x in trial.log[cursor:] if x['event']=='DRAINING'}
        expected=set() if mode in ('ADD','MBB') else {r.link_id for r in refs}
        if mode=='MBB' and action.setup.retarget_a_s==action.setup.retarget_b_s==action.setup.acquisition_s==0:
            expected={r.link_id for r in refs}  # True zero-duration setup completed inside submit.
        if actual!=expected:return reject('TRIAL_RELEASE_SET_MISMATCH',actual=sorted(actual),expected=sorted(expected))
        return dict(accepted=True,reason=None,commands=commands,release_refs=refs,mode=mode,
                    trial=trial,actual_immediate_release_ids=sorted(actual),physical=geometry)
