"""Finite thread-only observation, no patched methods or instance fields."""
import sys,time,copy,dataclasses
from collections import Counter,defaultdict
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.sgp4_model import Sgp4Model
from runtime.n2_actions import ActionValidator
from runtime.n2_physical import N2PhysicalLayer,Sgp4PhysicalGuard
class Timer:
    def __init__(self,ex,extra=None):
        self.stack=[];self.parts=defaultdict(float);self.calls=Counter();self.objects=Counter();self.callbacks=0
        self.code={ActionValidator.validate.__code__:'N2_validation_other',
            N2PhysicalLayer.evaluate.__code__:'GateC_physical_window_bilateral_other',
            TerminalPairPhysicalFeasibility.evaluate.__code__:'GateC_layer_checks',
            TerminalPairCatalog.connect_command.__code__:'GateC_connect_other',
            TerminalPairCatalog.current_window.__code__:'window_lookup',
            Sgp4PhysicalGuard.evaluate.__code__:'LOS_FOR',Sgp4Model.state.__code__:'SGP4',
            TerminalExecutor.submit.__code__:'inner_transaction_preplay_other',
            TerminalExecutor.assert_invariants.__code__:'terminal_invariant_validation',
            TerminalExecutor._log.__code__:'320_terminal_log_snapshot',
            TerminalExecutor.snapshot.__code__:'320_terminal_snapshot',
            TerminalExecutor.clone_for_transaction.__code__:'CLONE',copy.deepcopy.__code__:'COPY'}
        self.code.update(extra or {})
        self.root_history_id=id(ex.log)
        self.mutable_ids={id(getattr(ex,k)):k for k in ('terminals','links','reservations','events')}
        self.asdict_code=dataclasses.asdict.__code__
        self.copy_shapes={copy._deepcopy_dict.__code__:'dict',copy._deepcopy_list.__code__:'list',copy._reconstruct.__code__:'reconstruct'}
    def hook(self,frame,event,arg):
        if event not in ('call','return'):return
        self.callbacks+=1;code=frame.f_code
        if event=='call':
            if code is self.asdict_code:self.objects['dataclass_asdict_calls']+=1
            if code in self.copy_shapes:
                self.objects['deepcopy_'+self.copy_shapes[code]+'_calls']+=1
                x=frame.f_locals.get('x')
                if type(x) in (dict,list):self.objects['deepcopy_'+self.copy_shapes[code]+'_item_visits']+=len(x)
            category=self.code.get(code)
            if category=='COPY':
                x=frame.f_locals.get('x')
                category=('executor_copy_other' if isinstance(x,TerminalExecutor) else
                    'terminal_history_copy' if id(x)==self.root_history_id else
                    'current_'+self.mutable_ids[id(x)]+'_copy' if id(x) in self.mutable_ids else None)
            elif category=='CLONE':
                category=('inner_transaction_structural_clone' if any(x[1]=='inner_transaction_preplay_other' for x in self.stack) else
                    'GateC_current_state_structural_clone' if any(x[1]=='GateC_sealed_structural_clone_other' for x in self.stack) else 'N2_outer_structural_clone')
            if category:self.calls[category]+=1;self.stack.append([frame,category,time.perf_counter(),0.])
        elif self.stack and self.stack[-1][0] is frame:
            _,category,start,child=self.stack.pop();elapsed=time.perf_counter()-start
            self.parts[category]+=elapsed-child
            if self.stack:self.stack[-1][3]+=elapsed
    def run(self,fn):
        previous=sys.getprofile();start=time.perf_counter()
        try:sys.setprofile(self.hook);value=fn()
        finally:sys.setprofile(previous)
        return value,dict(actual_wall_s=time.perf_counter()-start,exclusive_s=dict(self.parts),
            calls=dict(self.calls),object_operations=dict(self.objects),callbacks=self.callbacks,
            instrumentation='pre-resolved code-object thread profiler, no method replacements; classified stages include observer overhead')
