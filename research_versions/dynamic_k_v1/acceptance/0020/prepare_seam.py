"""Static generation: copy one frozen method, replace coverage lookup only."""
import ast,difflib,hashlib,json,textwrap
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1]
def main():
    frozen=V/'runtime/n1b_fifo.py';source=frozen.read_text(encoding='utf-8')
    tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DeliveredAgeLedger')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_interval')
    before='\n'.join(source.splitlines()[method.lineno-1:method.end_lineno])+'\n'
    target='                for lo, hi in zip(cuts, cuts[1:]):\n                    parts = [s.clip(lo, hi) for s in incoming if s.start <= lo and s.end >= hi]'
    assert before.count(target)==1
    after=before.replace(target,'                for lo, hi, parts in self._coverage(incoming, cuts):')
    prefix='''"""Exact incoming coverage sweep only; all FIFO business methods inherited.

No flight-key index, persistent state/cache, global patch or time discretization.
An integer bitset orders active original incoming ordinals without resorting.
"""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction as F
from time import perf_counter
from .n1b_fifo import DeliveredAgeLedger, Stream, rational, canonical_components, require

def coverage_parts(incoming, cuts, stats=None):
    start_clock = perf_counter() if stats is not None else None
    starts, ends = defaultdict(list), defaultdict(list)
    for ordinal, stream in enumerate(incoming):
        if stream.start < stream.end:
            starts[stream.start].append(ordinal)
            ends[stream.end].append(ordinal)
    if stats is not None:
        stats.update(input_streams=len(incoming),cut_intervals=max(0,len(cuts)-1),
            legacy_coverage_predicate_iterations=len(incoming)*max(0,len(cuts)-1),
            optimized_coverage_predicate_iterations=0,endpoint_references=2*sum(map(len,starts.values())),
            build_s=perf_counter()-start_clock,maintenance_s=0.,enumeration_and_clip_s=0.,
            active_peak=0,parts_peak=0,clips=0,temporary_clip_Stream_objects=0,
            maintenance_endpoint_visits=0,peak_active_bitset_bits=0)
    active, active_count = 0, 0
    for lo, hi in zip(cuts, cuts[1:]):
        tick = perf_counter() if stats is not None else None
        for ordinal in ends.get(lo, ()):
            active &= ~(1 << ordinal)
            active_count -= 1
        for ordinal in starts.get(lo, ()):
            active |= 1 << ordinal
            active_count += 1
        if stats is not None:
            stats['maintenance_s'] += perf_counter()-tick
            stats['maintenance_endpoint_visits'] += len(ends.get(lo,()))+len(starts.get(lo,()))
            stats['active_peak']=max(stats['active_peak'],active_count)
            stats['peak_active_bitset_bits']=max(stats['peak_active_bitset_bits'],active.bit_length())
            tick=perf_counter()
        bits, parts = active, []
        while bits:
            bit = bits & -bits
            parts.append(incoming[bit.bit_length()-1].clip(lo, hi))
            bits ^= bit
        if stats is not None:
            stats['enumeration_and_clip_s'] += perf_counter()-tick
            stats['parts_peak']=max(stats['parts_peak'],len(parts))
            stats['clips']+=len(parts)
            stats['temporary_clip_Stream_objects']+=len(parts)
        yield lo, hi, parts

class SweepDeliveredAgeLedger(DeliveredAgeLedger):
    _coverage = staticmethod(coverage_parts)

    @classmethod
    def from_ledger(cls, ledger):
        require(isinstance(ledger, DeliveredAgeLedger), 'INVALID_FIFO_SEAM_SOURCE')
        result=cls.__new__(cls)
        result.__dict__=deepcopy(vars(ledger))
        return result

'''
    dest=V/'runtime/n4_p0j_fifo_sweep.py'
    with dest.open('x',encoding='utf-8',newline='\n') as f:f.write(prefix+after)
    restored=after.replace('                for lo, hi, parts in self._coverage(incoming, cuts):',target)
    assert ast.dump(ast.parse(textwrap.dedent(restored)))==ast.dump(ast.parse(textwrap.dedent(before)))
    diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='frozen/n1b_fifo.py::_interval',tofile='isolated/n4_p0j_fifo_sweep.py::_interval'))
    (A/'MINIMAL_INTERVAL_DIFF.patch').write_text(diff,encoding='utf-8')
    with (A/'SOURCE_PROVENANCE.json').open('x',encoding='utf-8') as f:
        json.dump(dict(frozen_source_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),
            seam_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
            restored_method_AST_exact_equal=True,changed_business_statement_count=0,
            change='ONLY_REPLACE_FOR_COVERAGE_SEARCH_WITH_EXACT_ORDERED_GENERATOR',global_monkeypatch=False),f,indent=2)
    print('SEAM_GENERATED_STATIC_PROVENANCE_PASS',flush=True)
if __name__=='__main__':main()
