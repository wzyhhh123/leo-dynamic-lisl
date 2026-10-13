"""P0H root-scoped read-only history and Gate C structural-copy seam.

No frozen class/global is patched. Current terminal state is cloned by the
audited Gate B API; immutable historical values are shared only in discarded
Gate C previews. Final N2 trial/live submit stays unchanged.
"""
import hashlib,json,importlib.util
from pathlib import Path
from dataclasses import dataclass
from copy import deepcopy
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.terminal_executor import Connect

def history_bytes(log):
    return json.dumps(log,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def deny(*args,**kwargs):raise TypeError('P0H_READ_ONLY_HISTORY')

class FrozenDict(dict):
    __slots__=()
    __setitem__=__delitem__=clear=pop=popitem=setdefault=update=__ior__=__init__=deny
    def __copy__(self):return self
    def __deepcopy__(self,memo):memo[id(self)]=self;return self

class FrozenList(list):
    __slots__=()
    __setitem__=__delitem__=append=extend=insert=pop=remove=clear=reverse=sort=__iadd__=__imul__=__init__=deny
    def __copy__(self):return self
    def __deepcopy__(self,memo):memo[id(self)]=self;return self

def freeze(value):
    if type(value) is dict:
        out=dict.__new__(FrozenDict)
        for key,item in value.items():dict.__setitem__(out,key,freeze(item))
        return out
    if type(value) is list:
        out=list.__new__(FrozenList);list.extend(out,(freeze(x) for x in value));return out
    if type(value) is tuple:return tuple(freeze(x) for x in value)
    if value is None or type(value) in (bool,int,float,str):return value
    raise ValueError('P0H_UNAUDITED_HISTORY_TYPE:'+type(value).__name__)

@dataclass(frozen=True)
class SourceBinding:
    project_root: Path
    manifest_path: str
    expected_manifest_sha256: str
    def verify(self):
        tool=Path(__file__).resolve().parents[1]/'tools/version_control_readme_v1.py'
        spec=importlib.util.spec_from_file_location('p0h_bound_vc',tool)
        vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
        p=vc.safe_path(self.project_root,self.manifest_path)
        if vc.file_info(p)['sha256']!=self.expected_manifest_sha256:raise ValueError('P0H_MANIFEST_DRIFT')
        doc=vc.read_json(p)
        if doc['schema']!='dynamic_k_p0h_structural_seam_sources_v1':raise ValueError('P0H_MANIFEST_SCOPE')
        for row in doc['files']:
            if vc.binding(self.project_root,row['path'])!=row:raise ValueError('P0H_SOURCE_DRIFT:'+row['path'])
        return {'status':'PASS','scope':'P0H_STRUCTURAL_COPY_ONLY'}

class SealedHistory:
    """No source-executor reference retained. Explicitly rebind after history changes.

    Python base-class mutation can bypass subclasses; freshly comparing both
    original and sealed values before/after previews detects such tampering.
    This is audited integrity, not a malicious-process memory security sandbox.
    """
    __slots__=('records','expected_bytes','sha256','record_count')
    def __init__(self,executor):
        expected=history_bytes(executor.log)
        self.records=tuple(freeze(row) for row in executor.log)
        self.expected_bytes=expected;self.sha256=hashlib.sha256(expected).hexdigest();self.record_count=len(self.records)
        self.verify(executor)
    def verify(self,executor):
        if history_bytes(self.records)!=self.expected_bytes:raise ValueError('P0H_SEALED_HISTORY_TAMPER')
        if history_bytes(executor.log)!=self.expected_bytes:raise ValueError('P0H_SOURCE_HISTORY_CHANGED_REBIND_REQUIRED')
    def clone(self,executor):
        self.verify(executor)
        trial=executor.clone_for_transaction()
        # Independent list, read-only records. Original source log is unchanged.
        trial.log=list(self.records)
        return trial
    def __deepcopy__(self,memo):
        out=type(self).__new__(type(self));memo[id(self)]=out
        out.records=self.records;out.expected_bytes=self.expected_bytes
        out.sha256=self.sha256;out.record_count=self.record_count
        return out

class StructuralCatalog(TerminalPairCatalog):
    def __init__(self,windows,plane_by_satellite,*,history,binding,parent_catalog=None,model=None,config=None):
        super().__init__(windows,plane_by_satellite,parent_catalog,model,config)
        binding.verify();self.history,self.binding=history,binding

    def connect_command(self,executor,a,b,retarget_a,retarget_b,acquisition,
                        orientation_a=(0.0,1.0,0.0),orientation_b=(0.0,1.0,0.0),
                        release_after=(),numerical_epsilon_s=1e-9):
        self.binding.verify()
        a,b=tuple(a),tuple(b)
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
            return command,dict(window=window.to_dict(),ready_time=ready,
                remaining_lifetime_s=window.end_s-executor.now,usable_lifetime_s=usable,
                end_semantics='prediction_horizon' if window.right_censored else 'terminal_pair_for_expiry')
        finally:self.history.verify(executor)

def install(controller,binding):
    """Explicit root factory seam; no command-result or geometry cache."""
    from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
    from runtime.n2_physical import N2PhysicalLayer
    from runtime.n2_actions import ActionValidator
    from runtime.n2_candidates import CandidateSource
    old=controller.validator.physical;cat=old.catalog
    replacement=StructuralCatalog([w for values in cat.windows.values() for w in values],cat.plane_by_satellite,
        history=SealedHistory(controller.engine.executor),binding=binding,
        parent_catalog=cat.parent_catalog,model=cat.model,config=cat.config)
    physical=N2PhysicalLayer(TerminalPairPhysicalFeasibility(replacement,old.gate_c.hardware),old.guard)
    controller.validator=ActionValidator(physical);controller.source=CandidateSource(controller.validator)
    controller._verify()
    return controller
