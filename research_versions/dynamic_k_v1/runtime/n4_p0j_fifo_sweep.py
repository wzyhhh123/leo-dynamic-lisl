"""Exact incoming coverage sweep only; all FIFO business methods inherited.

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

    def _interval(self, record):
        start, end = rational(record['start']), rational(record['end'])
        require(start == self.now, 'NONCONTIGUOUS_AGE_CLOCK')
        self.scale = max(self.scale, sum((abs(rational(x)) for x in record['after']['A'].values()),F()),
                         sum((abs(rational(x)) for x in record['after']['D'].values()),F()))
        for commodity in self.commodities:
            key = commodity.commodity_id
            order, outgoing = self._order(record['service'], key)
            for node in order:
                incoming = []
                if node == commodity.source and record['external'][key] > 0:
                    rate = rational(record['external'][key])
                    incoming.append(Stream(start, end, rate, ((F(1), F(1), F(0)),)))
                    self.arrived[key] += rate*(end-start)
                for (edge, fk), pieces in list(self.flight.items()):
                    if fk == key and edge[1] == node and record['arrival'].get((edge, fk), 0.) > 0:
                        keep = []
                        for stream in pieces:
                            clipped = stream.clip(start, end)
                            if clipped:
                                incoming.append(clipped)
                                if stream.start < clipped.start:
                                    keep.append(Stream(stream.start, clipped.start, stream.rate, stream.components))
                                if stream.end > clipped.end:
                                    keep.append(Stream(clipped.end, stream.end, stream.rate, stream.components))
                            else:
                                keep.append(stream)
                        self.flight[(edge, fk)] = keep
                cuts = sorted({start, end} | {t for s in incoming for t in (s.start, s.end)})
                for lo, hi, parts in self._coverage(incoming, cuts):
                    if node == commodity.destination:
                        for stream in parts:
                            self._deliver(key, stream)
                        continue
                    edge = outgoing.get(node)
                    service = rational(record['service'].get((edge, key), 0.)) if edge else F()
                    outputs = self.queue[(node, key)].advance_piece(lo, hi, parts, service,self._budget())
                    mass = sum((s.mass() for s in outputs),F())
                    self._roundoff(service*(hi-lo)-mass,
                        dict(state='SERVICE', key=(node,key), time=str(hi)))
                    for stream in outputs:
                        self.sent_mass[(edge,key)] += stream.mass()
                        delay = self.shift[(edge, key)]
                        shifted = canonical_components((w, a, b-a*delay) for w, a, b in stream.components)
                        self.flight[(edge, key)].append(Stream(stream.start+delay, stream.end+delay,
                                                             stream.rate, shifted))
        self.now = end
        self._check_state(record['after'], 'INTERVAL_END')
