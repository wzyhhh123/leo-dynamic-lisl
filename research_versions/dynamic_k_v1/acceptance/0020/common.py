"""Append-only acceptance utilities and explicit local seam construction."""
import hashlib,importlib.util,json,sys
from pathlib import Path
from collections import deque
from fractions import Fraction as F
from copy import deepcopy
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(V),str(P/'src')]
from runtime.n1b_fifo import DeliveredAgeLedger,Stream,Cohort,LocalFIFO
from runtime.n4_p0j_fifo_sweep import SweepDeliveredAgeLedger,coverage_parts
from runtime.n4_p0 import data_hash
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
def write(name,value):
    p=A/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def norm(x):
    if isinstance(x,F):return {'Fraction':str(x)}
    if isinstance(x,dict):return sorted([(norm(k),norm(v)) for k,v in x.items()],key=lambda p:repr(p[0]))
    if isinstance(x,(tuple,list,deque)):return [norm(v) for v in x]
    if isinstance(x,(set,frozenset)):return sorted(map(repr,x))
    if hasattr(x,'__dict__'):return norm(vars(x))
    if callable(x):return 'BOUND_FUNCTION'
    return x
def digest_state(ledger):return data_hash(vars(ledger))
def source_verify():
    doc=json.loads((A/'SOURCE_PROVENANCE.json').read_text())
    assert hashlib.sha256((V/'runtime/n1b_fifo.py').read_bytes()).hexdigest()==doc['frozen_source_sha256']
    assert hashlib.sha256((V/'runtime/n4_p0j_fifo_sweep.py').read_bytes()).hexdigest()==doc['seam_sha256']
    assert doc['restored_method_AST_exact_equal']
def old_context():return load('fifo20_bound_workflow',V/'acceptance/0011/workflow.py')
def variant_binding():
    from runtime.n4_p0f_events import VariantBinding
    d=json.loads((V/'acceptance/0015/VARIANT_BINDING.json').read_text())
    return VariantBinding(str(V/'acceptance/0015/variant_dependencies.json'),d['manifest_sha256'])
def counted_sweep_class(rows):
    class MeasuredSweep(SweepDeliveredAgeLedger):
        @staticmethod
        def _coverage(incoming,cuts):
            stats={}
            try:yield from coverage_parts(incoming,cuts,stats)
            finally:rows.append(stats)
    return MeasuredSweep

