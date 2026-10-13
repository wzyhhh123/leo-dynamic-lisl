"""Root-scoped immutable tuple history, independent per-preview views.

Only native immutable tuples/scalars are shared. No mutable dict/list or view
object is shared across Gate C previews. Source history is freshly checked
before/after preview. Frozen physics/transactions and logs stay unchanged.
"""
import hashlib
from collections.abc import Mapping,Sequence
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.terminal_executor import Connect
from runtime.n4_p0h_gate_c import SourceBinding,history_bytes,deny

def freeze_node(x):
    if type(x) is dict:return ('dict',tuple((k,freeze_node(v)) for k,v in x.items()))
    if type(x) in (list,tuple):return (type(x).__name__,tuple(freeze_node(v) for v in x))
    if x is None or type(x) in (bool,int,float,str):return ('value',x)
    raise ValueError('P0H_UNAUDITED_HISTORY_TYPE:'+type(x).__name__)

class ReadOnlyRecord(Mapping):
    __slots__=('_data',)
    __setattr__=__setitem__=__delitem__=clear=pop=popitem=setdefault=update=deny
    def __init__(self,data):object.__setattr__(self,'_data',data)
    def __iter__(self):return (k for k,v in self._data)
    def __len__(self):return len(self._data)
    def __getitem__(self,key):
        for k,v in self._data:
            if k==key:return view(v)
        raise KeyError(key)
    def __deepcopy__(self,memo):
        out=type(self)(self._data);memo[id(self)]=out;return out

class ReadOnlyRows(Sequence):
    __slots__=('_data',)
    __setattr__=__setitem__=__delitem__=append=extend=insert=pop=remove=clear=reverse=sort=__iadd__=__imul__=deny
    def __init__(self,data):object.__setattr__(self,'_data',data)
    def __len__(self):return len(self._data)
    def __getitem__(self,key):
        if isinstance(key,slice):return [view(v) for v in self._data[key]]
        return view(self._data[key])
    def __eq__(self,other):return list(self)==other
    def __deepcopy__(self,memo):
        out=type(self)(self._data);memo[id(self)]=out;return out

def view(node):
    kind,data=node
    if kind=='value':return data
    if kind=='dict':return ReadOnlyRecord(data)
    if kind=='list':return ReadOnlyRows(data)
    return tuple(view(v) for v in data)

def materialize(x):
    if isinstance(x,Mapping):return {k:materialize(v) for k,v in x.items()}
    if isinstance(x,ReadOnlyRows) or type(x) is list:return [materialize(v) for v in x]
    if type(x) is tuple:return tuple(materialize(v) for v in x)
    return x

class SealedHistory:
    __slots__=('_payload','expected_bytes','sha256','record_count')
    __setattr__=deny
    def __init__(self,executor):
        data=history_bytes(executor.log);payload=tuple(freeze_node(r) for r in executor.log)
        if history_bytes([materialize(view(r)) for r in payload])!=data:raise ValueError('P0H_HISTORY_ENCODING_DIFF')
        for k,v in dict(_payload=payload,expected_bytes=data,sha256=hashlib.sha256(data).hexdigest(),record_count=len(payload)).items():object.__setattr__(self,k,v)
    @property
    def records(self):return tuple(view(r) for r in self._payload)
    def verify(self,executor):
        if history_bytes(executor.log)!=self.expected_bytes:raise ValueError('P0H_SOURCE_HISTORY_CHANGED_REBIND_REQUIRED')
    def clone(self,executor):
        self.verify(executor);trial=executor.clone_for_transaction()
        trial.log=list(self.records);return trial
    def __deepcopy__(self,memo):
        out=type(self).__new__(type(self));memo[id(self)]=out
        for k in self.__slots__:object.__setattr__(out,k,getattr(self,k))
        return out

class StructuralCatalog(TerminalPairCatalog):
    def __init__(self,windows,plane_by_satellite,*,history,binding,parent_catalog=None,model=None,config=None):
        super().__init__(windows,plane_by_satellite,parent_catalog,model,config)
        binding.verify();self.history,self.binding=history,binding
    def connect_command(self,executor,a,b,retarget_a,retarget_b,acquisition,
                        orientation_a=(0.0,1.0,0.0),orientation_b=(0.0,1.0,0.0),
                        release_after=(),numerical_epsilon_s=1e-9):
        self.binding.verify();a,b=tuple(a),tuple(b)
        window=self.current_window(a,b,executor.now)
        if window is None:raise ValueError(self.diagnose(a,b,executor.now) or 'NOT_VISIBLE')
        command=Connect(a,b,window.end_s,retarget_a,retarget_b,acquisition,
                        orientation_a,orientation_b,tuple(release_after))
        trial=self.history.clone(executor)
        try:
            try:trial.submit([command])
            except ValueError as error:
                if 'strictly precede' in str(error):raise ValueError('INSUFFICIENT_LIFETIME') from error
                raise
            ready=next(item['details']['predicted_ready'] for item in reversed(trial.log) if item['event']=='RESERVE_BOTH')
            usable=window.end_s-ready
            if usable<=numerical_epsilon_s:raise ValueError('INSUFFICIENT_LIFETIME')
            return command,dict(window=window.to_dict(),ready_time=ready,remaining_lifetime_s=window.end_s-executor.now,
                usable_lifetime_s=usable,end_semantics='prediction_horizon' if window.right_censored else 'terminal_pair_for_expiry')
        finally:self.history.verify(executor)

def install(controller,binding):
    from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
    from runtime.n2_physical import N2PhysicalLayer
    from runtime.n2_actions import ActionValidator
    from runtime.n2_candidates import CandidateSource
    old=controller.validator.physical;cat=old.catalog
    replacement=StructuralCatalog([w for values in cat.windows.values() for w in values],cat.plane_by_satellite,
        history=SealedHistory(controller.engine.executor),binding=binding,parent_catalog=cat.parent_catalog,model=cat.model,config=cat.config)
    controller.validator=ActionValidator(N2PhysicalLayer(TerminalPairPhysicalFeasibility(replacement,old.gate_c.hardware),old.guard))
    controller.source=CandidateSource(controller.validator);controller._verify();return controller
