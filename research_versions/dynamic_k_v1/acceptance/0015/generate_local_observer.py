"""Generate explicitly instance-local, read-only observation seams."""
import ast,json,difflib
from pathlib import Path
import support as w
def main():
    p=w.V/'acceptance/0012/event_auditor.py';s=p.read_text(encoding='utf-8');t=ast.parse(s)
    node=next(x for c in t.body if isinstance(c,ast.ClassDef) and c.name=='Auditor' for x in c.body if isinstance(x,ast.FunctionDef) and x.name=='context')
    before='\n'.join(s.splitlines()[node.lineno-1:node.end_lineno])+'\n';after=before
    after=after.replace('oldintegrate=Engine._integrate','oldintegrate=type(e)._integrate').replace('oldsettle=Engine._settle_propagation_rate_events','oldsettle=type(e)._settle_propagation_rate_events').replace('oldnext=Engine._next_time','oldnext=type(e)._next_time')
    after=after.replace('(Engine,\'_compensated_add\',staticmethod(comp))','(Engine,\'_compensated_add\',comp)')
    after=after.replace(']:stack.enter_context(patch.object(cls,name,fn))', ''']:
            obj=e.queues if cls is QueueState else e.in_flight if cls is InFlightState else e
            local=fn if name=='_compensated_add' else MethodType(fn,obj)
            stack.enter_context(patch.object(obj,name,local))''')
    header='''"""P0F instance-only observers. No global monkeypatch of runtime classes."""
from types import MethodType
import support as w
old_auditor=w.old.load('p0f_auditor_base',w.V/'acceptance/0012/event_auditor.py')
from p0f_auditor_base import *
class InstanceAuditor(Auditor):
'''
    dest=w.A/'local_observer.py'
    with dest.open('x',encoding='utf-8',newline='\n') as f:f.write(header+after)
    # Identical N1a measure function, interception restricted to an explicit subclass.
    p2=w.V/'runtime/n1a.py';s2=p2.read_text(encoding='utf-8');t2=ast.parse(s2)
    n=next(x for c in t2.body if isinstance(c,ast.ClassDef) and c.name=='FixedHorizonEvaluator' for x in c.body if isinstance(x,ast.FunctionDef) and x.name=='measure')
    b='\n'.join(s2.splitlines()[n.lineno-1:n.end_lineno])+'\n';a=b.replace('        validate_measurement(result)','        self.capture_and_validate(result)')
    head='''"""Explicit diagnostic evaluator subtype; unchanged measurement/assertions."""
from runtime.n1a import *
import support as w
class DiagnosticMeasure(FixedHorizonEvaluator):
    def capture_and_validate(self,result):
        paths=sorted(self.diagnostic_directory.glob('VALIDATION_INPUT_*.json'))
        w.write(self.diagnostic_directory/('VALIDATION_INPUT_'+str(len(paths)+1).zfill(3)+'.json'),result)
        validate_measurement(result)
'''
    with (w.A/'diagnostic_measure.py').open('x',encoding='utf-8',newline='\n') as f:f.write(head+a)
    w.write(w.A/'LOCAL_OBSERVER_SOURCE_DIFF.json',dict(instance_only_context_diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True))),
        diagnostic_measure_diff=''.join(difflib.unified_diff(b.splitlines(True),a.splitlines(True))),
        old_global_functions_modified=False,reference_values_written=False))
    print('LOCAL_OBSERVERS_GENERATED',flush=True)
if __name__=='__main__':main()
