"""Analytical continuous FIFO sidecar; rational mass/time maps, no time stepping.

Only origin-time first moments are needed for mean delay, but all components of
each simultaneous mixture are retained. FIFO uses LOCAL arrival order.
"""
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction as F
import math

from .n1a import require


def rational(value):
    if isinstance(value, F):
        return value
    require(isinstance(value, (int, float)) and math.isfinite(value), 'NONFINITE_FIFO_INPUT')
    return F(value)


def canonical_components(parts):
    result = defaultdict(F)
    for weight, a, b in parts:
        if weight:
            result[(a, b)] += weight
    return tuple((w, a, b) for (a, b), w in sorted(result.items()) if w)


@dataclass
class Cohort:
    mass: F
    components: tuple  # (weight, slope, intercept): original_time(q)=slope*q+intercept
    local_start: F
    local_slope: F

    def prefix_moment(self, mass):
        require(0 <= mass <= self.mass, 'COHORT_OVERDRAW')
        return sum((w*(a*mass*mass/2+b*mass) for w, a, b in self.components), F())

    def consume(self, mass):
        parts = self.components
        moment = self.prefix_moment(mass)
        self.components = canonical_components((w, a, b+a*mass) for w, a, b in parts)
        self.local_start += self.local_slope*mass
        self.mass -= mass
        return moment, parts


@dataclass
class Stream:
    start: F
    end: F
    rate: F
    components: tuple  # original_time(t)=a*t+b, continuous at receiving time t

    def mass(self):
        return self.rate*(self.end-self.start)

    def moment(self):
        return self.rate*sum((w*(a*(self.end*self.end-self.start*self.start)/2
                                 +b*(self.end-self.start))
                             for w, a, b in self.components), F())

    def clip(self, start, end):
        a, b = max(start, self.start), min(end, self.end)
        return Stream(a, b, self.rate, self.components) if b > a else None


class LocalFIFO:
    def __init__(self):
        self.rows = deque()
        self.temporal_correction_bound = F()

    def total(self):
        return sum((row.mass for row in self.rows), F())

    def original_moment(self):
        return sum((row.prefix_moment(row.mass) for row in self.rows), F())

    def append_impulse(self, cohort):
        if self.rows and self.rows[-1].local_start == cohort.local_start and not self.rows[-1].local_slope:
            old = self.rows.pop()
            total = old.mass+cohort.mass
            components = canonical_components((w*c.mass/total, a*c.mass/total, b)
                for c in (old, cohort) for w,a,b in c.components)
            cohort = Cohort(total, components, cohort.local_start, F())
        self.rows.append(cohort)

    def advance_piece(self, start, end, inputs, service_rate, roundoff_budget=F()):
        """One constant-density mixture interval; partial service is analytical."""
        start, end, service_rate = map(rational, (start, end, service_rate))
        duration = end-start
        require(duration > 0 and service_rate >= 0, 'INVALID_FIFO_INTERVAL')
        total_rate = sum((s.rate for s in inputs), F())
        if total_rate:
            components = canonical_components(
                (s.rate*w/total_rate, a/total_rate, a*start+b)
                for s in inputs for w, a, b in s.components)
            self.rows.append(Cohort(total_rate*duration, components, start, 1/total_rate))
        if not service_rate:
            return []
        wanted = service_rate*duration
        require(wanted <= self.total()+roundoff_budget, 'FIFO_SERVICE_EXCEEDS_ACTUALLY_INJECTED_BITS')
        wanted = min(wanted, self.total())  # Never manufacture source bits.
        result, sent = [], F()
        while wanted:
            row = self.rows[0]
            amount = min(wanted, row.mass)
            depart_start, depart_end = start+sent/service_rate, start+(sent+amount)/service_rate
            local_end = row.local_start+row.local_slope*amount
            require(row.local_start <= depart_start+roundoff_budget/service_rate
                    and local_end <= depart_end+roundoff_budget/service_rate,
                    'FIFO_SERVICE_PRECEDES_LOCAL_ARRIVAL')
            self.temporal_correction_bound += amount*(max(F(),row.local_start-depart_start)
                                                        +max(F(),local_end-depart_end))
            depart_start = max(depart_start, row.local_start)
            depart_end = max(depart_end, local_end)
            _, components = row.consume(amount)
            output_rate = amount/(depart_end-depart_start)
            out = canonical_components((w, a*output_rate, b-a*output_rate*depart_start)
                                       for w, a, b in components)
            result.append(Stream(depart_start, depart_end, output_rate, out))
            if not row.mass:
                self.rows.popleft()
            wanted -= amount
            sent += amount
        return result


class AgeSemanticConflict(ValueError):
    def __init__(self, code, evidence):
        self.code, self.evidence = code, evidence
        super().__init__(code + ': ' + repr(evidence))


class DeliveredAgeLedger:
    """Consumes observer records without changing D2 or adding business events."""
    def __init__(self, engine):
        require(engine.now == 0 and not engine.queues.total() and not engine.in_flight.total()
                and not any(engine.arrived.values()) and not any(engine.delivered.values()),
                'INITIAL_HISTORY_REQUIRES_EXPLICIT_ORIGINAL_TIME_METADATA')
        self.nodes = tuple(engine.nodes)
        self.commodities = tuple(engine.commodities)
        self.queue = defaultdict(LocalFIFO)
        self.flight = defaultdict(list)
        self.shift = {}
        self.delivered = defaultdict(F)
        self.delivered_original_moment = defaultdict(F)
        self.MD = defaultdict(F)
        self.arrived = defaultdict(F)
        self.cursor = 0
        self.now = F()
        self.closure_audit = []
        self.roundoff_audit = []
        self.mass_error_bound = F()
        self.scale = F(1)
        self.sent_mass = defaultdict(F)

    def _budget(self):
        # An explicit engineering acceptance envelope; no assertion of a
        # universal IEEE error theorem or permission to fill missing metadata.
        return rational(64*math.ulp(float(self.scale)))*(self.cursor+1)

    def _roundoff(self, difference, evidence):
        if abs(difference) > self._budget():
            raise AgeSemanticConflict('COHORT_MASS_CONFLICT_EXCEEDS_IEEE_ENVELOPE', evidence)
        if difference:
            self.mass_error_bound += abs(difference)
            self.roundoff_audit.append(dict(difference_bits=str(difference), **evidence))

    def clone(self):
        return deepcopy(self)

    def consume(self, engine):
        require(len(engine.age_observations) >= self.cursor, 'OBSERVER_HISTORY_LOST')
        for record in engine.age_observations[self.cursor:]:
            if record['kind'] == 'SCHEDULE':
                for event in record['emitted_events']:
                    if event.delta_rate_bit_s > 0:
                        self.shift[(event.edge, event.commodity_id)] = rational(event.time_s)-rational(record['time'])
            elif record['kind'] == 'INTERVAL':
                self._interval(record)
            elif record['kind'] == 'CLOSURE':
                self._closure(record['event'])
            else:
                raise ValueError('UNKNOWN_AGE_OBSERVATION')
            self.cursor += 1
        require(self.now == rational(engine.now), 'AGE_CLOCK_MISMATCH')
        self._check_state(engine.age_scalar_state(), 'FINAL')

    def _order(self, service, commodity):
        # Frozen positive-delay shortest-path service forms a destination DAG.
        outgoing, indegree = {}, dict.fromkeys(self.nodes, 0)
        for (edge, key), rate in service.items():
            if key == commodity and rate > 0:
                require(edge[0] not in outgoing, 'MULTIPLE_NEXT_HOPS_FOR_ONE_COMMODITY')
                outgoing[edge[0]] = edge
                indegree[edge[1]] += 1
        ready, order = sorted(n for n in self.nodes if not indegree[n]), []
        while ready:
            node = ready.pop(0)
            order.append(node)
            if node in outgoing:
                nxt = outgoing[node][1]
                indegree[nxt] -= 1
                if not indegree[nxt]:
                    ready.append(nxt)
                    ready.sort()
        require(len(order) == len(self.nodes), 'CYCLIC_SERVICE_DAG_NOT_AUTHORIZED')
        return order, outgoing

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
                for lo, hi in zip(cuts, cuts[1:]):
                    parts = [s.clip(lo, hi) for s in incoming if s.start <= lo and s.end >= hi]
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

    def _deliver(self, key, stream):
        mass, origin = stream.mass(), stream.moment()
        delivery_moment = stream.rate*(stream.end*stream.end-stream.start*stream.start)/2
        require(delivery_moment >= origin, 'NEGATIVE_DELIVERED_AGE')
        self.delivered[key] += mass
        self.delivered_original_moment[key] += origin
        self.MD[key] += delivery_moment-origin

    def _closure(self, event):
        edge, key = tuple(event['edge']), event['commodity_id']
        pieces = self.flight[(edge, key)]
        known_mass = sum((s.mass() for s in pieces), F())
        actual_mass = rational(event['closed_bits'])
        if actual_mass and not known_mass and not self.sent_mass[(edge,key)]:
            raise AgeSemanticConflict('CLOSURE_HAS_NO_KNOWN_SOURCE_COHORT',deepcopy(event))
        # Only known physical cohorts move. A rounded duplicate scalar residue
        # contributes to the uncertainty budget, never to an invented cohort.
        self._roundoff(actual_mass-known_mass, dict(
                time=event['time_s'], edge=edge, commodity=key,
                legacy_closed_bits=str(actual_mass), known_cohort_bits=str(known_mass),
                state='CLOSURE', legacy_event=deepcopy(event)))
        now = rational(event['time_s'])
        origin = sum((s.moment() for s in pieces), F())
        if event['credited_to'] == 'DELIVERED':
            self.delivered[key] += known_mass
            self.delivered_original_moment[key] += origin
            self.MD[key] += now*known_mass-origin
        elif known_mass:
            # Zero-duration arrivals mix proportionally at this local timestamp.
            components = canonical_components((s.mass()*w/known_mass,
                a*(s.end-s.start)/known_mass, a*s.start+b)
                for s in pieces for w,a,b in s.components)
            # Retain the full affine original-time distribution of every piece.
            self.queue[(edge[1], key)].append_impulse(Cohort(known_mass, components, now, F()))
        self.flight[(edge, key)] = []
        self.closure_audit.append(dict(time=str(now), edge=edge, commodity=key,
                                      mass=str(known_mass), original_moment=str(origin)))

    def _check_state(self, raw, boundary):
        expected = dict(Q={k:v.total() for k,v in self.queue.items()},
            I={k:sum((s.mass() for s in v),F()) for k,v in self.flight.items()},
            A=dict(self.arrived), D=dict(self.delivered))
        for kind in expected:
            for key in set(expected[kind]) | set(raw[kind]):
                known, observed = expected[kind].get(key,F()), rational(raw[kind].get(key,0.))
                commodity = key if kind in ('A','D') else key[1]
                if observed > 0 and not known and not self.arrived[commodity]:
                    raise AgeSemanticConflict('STATE_HAS_NO_KNOWN_SOURCE_COHORT',
                        dict(state=kind,key=key,legacy_bits=str(observed)))
                self._roundoff(observed-known, dict(
                        boundary=boundary, time=str(self.now), state=kind, key=key,
                        cohort_bits=str(known), legacy_bits=str(observed)))
        for commodity in self.commodities:
            key=commodity.commodity_id
            require(self.arrived[key]==self.delivered[key]
                +sum((q.total() for (node,k),q in self.queue.items() if k==key),F())
                +sum((s.mass() for (edge,k),pieces in self.flight.items() if k==key for s in pieces),F()),
                'EXACT_COHORT_MASS_CONSERVATION_FAILED')

    def metrics(self):
        delivered = sum(self.delivered.values(), F())
        md = sum(self.MD.values(), F())
        remaining_moment = sum((self.now*q.total()-q.original_moment()
                                for q in self.queue.values()), F())
        remaining_moment += sum((self.now*s.mass()-s.moment()
                                 for pieces in self.flight.values() for s in pieces), F())
        conversion = math.ulp(float(md))/2 if md else 0.
        temporal_bound=sum((q.temporal_correction_bound for q in self.queue.values()),F())
        require(md>=0 and remaining_moment>=0 and md<=self.now*delivered,'INVALID_COHORT_AGE_RANGE')
        bound = 2*self.now*self.mass_error_bound+temporal_bound
        return dict(delivered_bits=float(delivered), delivered_bit_age_integral_bit_s=float(md),
            mean_delivered_fluid_delay_s=float(md/delivered) if delivered else None,
            remaining_bit_age_integral_bit_s=float(remaining_moment),
            exact_rational=dict(delivered_bits=str(delivered), M_D_bit_s=str(md),
                                remaining_bit_age_integral_bit_s=str(remaining_moment)),
            metric_status=('IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT' if self.roundoff_audit or temporal_bound
                           else 'EXACT_RATIONAL_ENCODED_TRACE_WITH_FLOAT_OUTPUT_ROUNDING'),
            roundoff_mass_envelope_bits=float(self.mass_error_bound),
            temporal_correction_age_bound_bit_s=float(temporal_bound),
            delivered_age_absolute_error_bound_bit_s=math.nextafter(float(bound)+conversion,math.inf),
            closure_audit=deepcopy(self.closure_audit),roundoff_audit=deepcopy(self.roundoff_audit))
