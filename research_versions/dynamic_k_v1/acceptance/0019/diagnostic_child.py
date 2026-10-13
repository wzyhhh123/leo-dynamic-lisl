"""ONE short synthetic FIFO diagnosis; never constructs/scorers a physical root.

The frozen source is loaded unchanged for control. An isolated AST copy adds
integer counters only, with no global monkeypatch, profiler or time quantization.
"""
import ast
from collections import deque
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace, ModuleType

A = Path(__file__).resolve().parent
V = A.parents[1]
sys.path.insert(0, str(V))
import runtime.n1b_fifo as original

def emit(value):
    with (A/'DIAGNOSTIC_PROGRESS.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps(value, sort_keys=True), flush=True)

def normalized(x):
    if isinstance(x, F): return {'rational': str(x)}
    if isinstance(x, dict):
        return sorted([(normalized(k), normalized(v)) for k,v in x.items()], key=lambda p:repr(p[0]))
    if isinstance(x, (list, tuple, deque)): return [normalized(v) for v in x]
    if hasattr(x, '__dict__'): return normalized(vars(x))
    return x

def count_stmt(key, expression='1'):
    return ast.parse("COUNTS[%r] = COUNTS.get(%r, 0) + (%s)"%(key,key,expression)).body[0]

def counted_module():
    source = (V/'runtime/n1b_fifo.py').read_bytes()
    tree = ast.parse(source)
    tracked = {'Cohort': {'consume','prefix_moment'}, 'Stream': {'clip','moment'},
               'LocalFIFO': {'total','original_moment','advance_piece','append_impulse'},
               'DeliveredAgeLedger': {'_interval','_order','_roundoff','_check_state','metrics'}}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level:
            node.module='runtime.'+node.module; node.level=0
        if isinstance(node, ast.FunctionDef) and node.name=='canonical_components':
            node.body.insert(0, count_stmt('canonical_components'))
        if not isinstance(node, ast.ClassDef): continue
        if node.name in ('Cohort','Stream'):
            node.body.append(ast.parse('def __post_init__(self):\n    COUNTS[%r] = COUNTS.get(%r,0)+1' %
                                      (node.name+'_created',node.name+'_created')).body[0])
        for method in node.body:
            if not isinstance(method,ast.FunctionDef): continue
            if method.name in tracked.get(node.name,set()):
                method.body.insert(0,count_stmt(node.name+'.'+method.name))
            if node.name=='Cohort' and method.name=='consume':
                method.body.insert(1,count_stmt('cohort_partial_consumes','int(mass < self.mass)'))
            if node.name=='DeliveredAgeLedger' and method.name=='_interval':
                class Inserts(ast.NodeTransformer):
                    def visit_Assign(self, stmt):
                        self.generic_visit(stmt)
                        if len(stmt.targets)==1 and isinstance(stmt.targets[0],ast.Name):
                            name=stmt.targets[0].id
                            if name=='cuts':
                                return [stmt,count_stmt('incoming_streams_seen','len(incoming)'),
                                        count_stmt('incoming_scan_comparisons','len(incoming)*(len(cuts)-1)'),
                                        count_stmt('cut_intervals','len(cuts)-1')]
                            if name=='parts': return [stmt,count_stmt('true_overlap_clips','len(parts)')]
                        return stmt
                method=Inserts().visit(method)
    module=ModuleType('fifo_count_only_0019'); module.__file__=str(V/'runtime/n1b_fifo.py')
    module.COUNTS={}; sys.modules[module.__name__]=module
    ast.fix_missing_locations(tree)
    exec(compile(tree,'<0019_counter_only_ast_of_frozen_fifo>','exec'), module.__dict__)
    return module, hashlib.sha256(source).hexdigest()

def engine():
    zero=SimpleNamespace(total=lambda:0)
    return SimpleNamespace(now=0, queues=zero, in_flight=zero, arrived={}, delivered={},
        nodes=('src','dst'), commodities=(SimpleNamespace(commodity_id='c', source='src',destination='dst'),))

def interval_fixture(module, n, layout):
    ledger=module.DeliveredAgeLedger(engine())
    if layout=='disjoint': windows=[(F(i,n),F(i+1,n)) for i in range(n)]
    else: windows=[(F(i,4*n), F(3,4)+F(i+1,4*n)) for i in range(n)]
    streams=[module.Stream(lo,hi,F(1),((F(1),F(1),F(0)),)) for lo,hi in windows]
    mass=sum((s.mass() for s in streams),F())
    ledger.flight[(('src','dst'),'c')]=streams;ledger.arrived['c']=mass
    record=dict(start=0,end=1,external={'c':0}, service={}, arrival={(('src','dst'),'c'):1},
                after=dict(A={'c':mass},D={'c':mass},Q={},I={}))
    cuts=sorted({F(0),F(1)}|{x for pair in windows for x in pair})
    overlaps=sum(sum(lo<=a and hi>=b for lo,hi in windows) for a,b in zip(cuts,cuts[1:]))
    before=normalized(record)
    t=time.perf_counter();ledger._interval(record);wall=time.perf_counter()-t
    assert before==normalized(record), 'READ_ONLY_OBSERVER_INPUT_CHANGED'
    metrics=ledger.metrics()
    assert metrics['exact_rational']['M_D_bit_s']=='0'
    assert ledger.arrived['c']==ledger.delivered['c'] and not sum((s.mass() for ss in ledger.flight.values() for s in ss),F())
    return normalized(ledger), dict(layout=layout,n=n,wall_s=wall,
        scan_comparisons=n*(len(cuts)-1),true_overlaps=overlaps,cut_intervals=len(cuts)-1,
        exact_delivered_mass=str(mass),exact_age_integral='0',input_unmodified=True)

def fifo_fixture(module, n):
    q=module.LocalFIFO()
    for i in range(n):
        lo,hi=F(i),F(i+1)
        q.advance_piece(lo,hi,[module.Stream(lo,hi,F(1),((F(1),F(1),F(0)),))],0)
    assert len(q.rows)==n and q.total()==n
    total=F(n); origin_before=q.original_moment()
    outputs=q.advance_piece(F(n),F(n+1),[],F(n,2)+F(1,2))
    sent=sum((s.mass() for s in outputs),F())
    assert sent+q.total()==total and sum((s.moment() for s in outputs),F())+q.original_moment()==origin_before
    return normalized(q),normalized(outputs),dict(n=n,sent=str(sent),remaining=str(q.total()),
        output_streams=len(outputs),remaining_rows=len(q.rows),exact_mass_and_origin_moment_conserved=True)

def metrics_fixture(module,n):
    ledger=module.DeliveredAgeLedger(engine());ledger.now=F(1);ledger.arrived['c']=F(n)
    ledger.delivered['c']=F(n);ledger.MD['c']=F(n)
    ledger.roundoff_audit=[dict(state='Q',key=('src','c'),time=str(F(i,n)),difference_bits='1/1000000') for i in range(n)]
    t=time.perf_counter();result=ledger.metrics();wall=time.perf_counter()-t
    assert result['roundoff_audit'] is not ledger.roundoff_audit
    return normalized(result), dict(audit_rows=n,wall_s=wall,output_rows=len(result['roundoff_audit']))

def main():
    assert sys.getprofile() is None and sys.gettrace() is None
    counted, sha=counted_module();results=[]
    for layout, sizes in [('disjoint',(32,64,128,256)),('dense',(16,32,64))]:
        for n in sizes:
            control, plain=interval_fixture(original,n,layout);counted.COUNTS.clear()
            actual, measured=interval_fixture(counted,n,layout)
            assert control==actual, 'COUNTER_COPY_STATE_DIFFERENCE'
            assert counted.COUNTS['incoming_scan_comparisons']==plain['scan_comparisons']
            assert counted.COUNTS['true_overlap_clips']==plain['true_overlaps']
            row=dict(kind='FROZEN_INTERVAL_SYNTHETIC',plain=plain,instrumented=measured,
                     counts=dict(counted.COUNTS),complete_state_exact_equal=True)
            emit(row);results.append(row)
    for n in (16,64,256):
        plain=fifo_fixture(original,n);counted.COUNTS.clear();actual=fifo_fixture(counted,n)
        assert plain==actual
        row=dict(kind='FROZEN_LOCAL_FIFO_SYNTHETIC',result=actual[2],counts=dict(counted.COUNTS),complete_state_exact_equal=True)
        emit(row);results.append(row)
    for n in (1000,7595,15000):
        control,plain=metrics_fixture(original,n);counted.COUNTS.clear();actual,measured=metrics_fixture(counted,n)
        assert actual==control
        row=dict(kind='FROZEN_METRICS_SYNTHETIC_AUDIT_OUTPUT',plain=plain,instrumented=measured,counts=dict(counted.COUNTS),complete_result_exact_equal=True)
        emit(row);results.append(row)
    emit(dict(status='PASS_DIAGNOSTIC_FIXTURES_ONLY',source_sha256=sha,rows=results,
              physical_root_runs=0,prediction_branch_runs=0,profiler_callbacks=0,
              AST_copy='INTEGER_COUNTERS_ONLY_NO_OPTIMIZATION',original_BBM_replayed=False))

if __name__=='__main__': main()
