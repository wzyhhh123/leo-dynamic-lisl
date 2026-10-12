"""Event-time energy integration over unchanged Gate B and D2 interfaces.

Explicit test horizons/tolerances are engineering inputs, never science defaults.
Gate B logs contain complete post-transition terminal inventories. Integrating
these successive states includes every intermediate phase, not observation grids.
"""
from copy import deepcopy
import hashlib
import json
import math

EXECUTION_STATES = ('IDLE', 'RETARGETING', 'ACQUIRING', 'ACTIVE', 'DRAINING')
ENERGY_STATES = EXECUTION_STATES[:4]
POWER_W = dict(IDLE=5., RETARGETING=40., ACQUIRING=40., ACTIVE=45., DRAINING=45.)
COUNT = 320


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value, name, minimum=0., maximum=math.inf):
    require(type(value) in (int, float) and math.isfinite(value)
            and minimum <= value <= maximum, 'INVALID_NUMERIC:' + name)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf-8')).hexdigest()


def normalized(rows):
    result = {}
    for row in rows:
        key = tuple(row['terminal_id'])
        require(key not in result, 'DUPLICATE_TERMINAL')
        require(row['phase'] in EXECUTION_STATES, 'UNKNOWN_EXECUTION_STATE')
        result[key] = (row['phase'], tuple(row['current_peer']) if row['current_peer'] else None,
                       row['reservation_id'])
    require(len(result) == COUNT, 'EXACTLY_320_DYNAMIC_TERMINALS_REQUIRED')
    return result


def topology_sample(time, state):
    links = {'ACTIVE': set(), 'DRAINING': set()}
    for key, (phase, peer, _) in state.items():
        if phase in links:
            require(peer in state and state[peer][0] == phase and state[peer][1] == key,
                    'NON_BILATERAL_PHYSICAL_CONNECTION')
            links[phase].add(tuple(sorted((key, peer))))
    retarget = sum(v[0] == 'RETARGETING' for v in state.values())
    acquiring = sum(v[0] == 'ACQUIRING' for v in state.values())
    setup = {v[2] for v in state.values()
             if v[0] in ('RETARGETING', 'ACQUIRING')}
    require(None not in setup, 'SETUP_WITHOUT_RESERVATION')
    return dict(t_s=time, K_active_admissible=len(links['ACTIVE']),
                K_draining=len(links['DRAINING']), setup_connection_count=len(setup),
                setup_terminal_count=retarget+acquiring,
                retargeting_terminal_count=retarget, acquiring_terminal_count=acquiring,
                setup_reserved_terminal_count=sum(v[2] is not None for v in state.values()))


class TerminalEnergyLedger:
    """Consumes append-only real Gate B transition logs, with exact initial state."""
    def __init__(self, executor):
        require(executor.now == 0., 'ACCOUNTING_MUST_START_AT_ZERO')
        executor.assert_invariants()
        self.state = normalized(executor.snapshot()['terminals'])
        self.inventory = set(self.state)
        self.now = 0.
        self.cursor = len(executor.log)
        self.history_sha256 = digest(executor.log)
        self.dwell = {key: dict.fromkeys(EXECUTION_STATES, 0.) for key in self.inventory}
        self.samples = [topology_sample(0., self.state)]

    def _integrate_until(self, until):
        finite(until, 'terminal_event_time')
        require(until >= self.now, 'NONMONOTONIC_TERMINAL_LOG')
        dt = until-self.now
        for key, (phase, _, _) in self.state.items():
            self.dwell[key][phase] += dt
        self.now = until

    def capture(self, executor):
        require(len(executor.log) >= self.cursor
                and digest(executor.log[:self.cursor]) == self.history_sha256,
                'TERMINAL_HISTORY_TRUNCATED_OR_CHANGED')
        finite(executor.now, 'executor_time')
        for event in executor.log[self.cursor:]:
            require(event['time'] <= executor.now, 'TERMINAL_EVENT_IN_FUTURE')
            self._integrate_until(event['time'])
            state = normalized(event['terminals'])
            require(set(state) == self.inventory, 'TERMINAL_INVENTORY_CHANGED')
            self.state = state
            sample = topology_sample(event['time'], state)
            if self.samples[-1]['t_s'] == event['time']:
                self.samples[-1] = sample
            else:
                self.samples.append(sample)
        require(normalized(executor.snapshot()['terminals']) == self.state,
                'UNLOGGED_TERMINAL_STATE_CHANGE')
        self._integrate_until(executor.now)
        self.cursor = len(executor.log)
        self.history_sha256 = digest(executor.log)

    def metrics(self):
        samples = deepcopy(self.samples)
        if samples[-1]['t_s'] != self.now:
            samples.append(topology_sample(self.now, self.state))
        five = {phase: math.fsum(row[phase] for row in self.dwell.values())
                for phase in EXECUTION_STATES}
        four = {phase: five[phase] for phase in ENERGY_STATES}
        four['ACTIVE'] += five['DRAINING']
        energy = math.fsum(POWER_W[phase]*time for phase, time in five.items())
        baseline = COUNT*self.now*POWER_W['IDLE']
        increment = math.fsum((POWER_W[phase]-5.)*time for phase, time in five.items())
        return dict(E_LCT_J=energy, DeltaE_LCT_J=increment,
                    standby_baseline_energy_J=baseline,
                    four_energy_state_dwell_s=four, five_execution_state_dwell_s=five,
                    per_terminal_execution_dwell_s=[
                        dict(terminal_id=list(key), dwell_s=dict(self.dwell[key]))
                        for key in sorted(self.dwell)],
                    K_time_series=samples)


class FixedHorizonEvaluator:
    """advance_to uses D2's real event loop, including when traffic is empty.

The ledger and the D2 engine travel together in clone/checkpoint/restore. A
restored state cannot silently start a new energy window at the checkpoint.
"""
    def __init__(self, engine, *, T_s, time_tolerance_s, energy_tolerance_J,
                 business_tolerance_bits, evidence_binding):
        finite(T_s, 'engineering_T', minimum=1e-12)
        require(engine.now == 0. and T_s >= engine.trace.arrival_horizon_s,
                'INITIAL_ZERO_TIME_AND_T_AT_LEAST_INJECTION_END_REQUIRED')
        for value, name in ((time_tolerance_s, 'time_tolerance'),
                            (energy_tolerance_J, 'energy_tolerance'),
                            (business_tolerance_bits, 'business_tolerance')):
            finite(value, name)
        from .bindings import EngineeringBinding
        require(isinstance(evidence_binding, EngineeringBinding),
                'PINNED_ENGINEERING_BINDING_REQUIRED')
        evidence_binding.verify()
        self.engine = engine
        self.T = T_s
        self.tolerances = dict(time_s=time_tolerance_s, energy_J=energy_tolerance_J,
                               business_bits=business_tolerance_bits)
        self.evidence_binding = deepcopy(evidence_binding)
        self.input_trace_sha256 = engine.trace.sha256()
        self.initial_state_sha256 = engine.canonical_state_sha256()
        self.ledger = TerminalEnergyLedger(engine.executor)

    def advance_to(self, until_s):
        self.evidence_binding.verify()
        finite(until_s, 'advance_target', maximum=self.T)
        require(until_s >= self.engine.now, 'NONMONOTONIC_EVALUATION')
        require(self.engine.trace.sha256() == self.input_trace_sha256,
                'INPUT_TRACE_CHANGED')
        self.engine.advance_to(until_s)
        require(abs(self.engine.now-until_s) <= self.tolerances['time_s'],
                'ENGINE_DID_NOT_REACH_REQUESTED_TIME')
        require(self.engine.executor.now == self.engine.now, 'CLOCK_MISMATCH')
        self.ledger.capture(self.engine.executor)
        return self.measure()

    def run(self):
        return self.advance_to(self.T)

    def clone(self):
        return deepcopy(self)

    def checkpoint(self):
        """In-memory causal checkpoint, not an untrusted pickle serialization API."""
        return self.clone()

    @classmethod
    def restore(cls, checkpoint):
        require(type(checkpoint) is cls, 'INVALID_N1A_CHECKPOINT')
        return checkpoint.clone()

    def measure(self):
        e = self.engine
        require(e.now == self.ledger.now, 'ENERGY_NOT_CAPTURED_TO_ENGINE_TIME')
        rows = e.timeline
        require(bool(rows) and rows[0]['time_s'] == 0.
                and rows[-1]['time_s'] == e.now, 'INCOMPLETE_BUSINESS_TIMELINE')
        areas = []
        for left, right in zip(rows, rows[1:]):
            dt = right['time_s']-left['time_s']
            require(dt >= 0., 'NONMONOTONIC_BUSINESS_TIMELINE')
            # This is UNWEIGHTED N(t), unlike the legacy weighted objective.
            a = left['arrived_bits']-left['delivered_bits']
            b = right['arrived_bits']-right['delivered_bits']
            require(min(a, b) >= -self.tolerances['business_bits'], 'NEGATIVE_BACKLOG')
            areas.append(.5*(max(0., a)+max(0., b))*dt)
        arrived = math.fsum(e.arrived.values())
        expected_arrived = math.fsum(e.trace.cumulative_arrivals(e.now).values())
        tol = self.tolerances['business_bits']
        require(abs(arrived-expected_arrived) <= tol, 'INJECTION_ACCOUNTING_MISMATCH')
        raw_delivered = math.fsum(e.delivered.values())
        require(-tol <= raw_delivered <= arrived+tol, 'DELIVERY_OUT_OF_RANGE')
        delivered = min(arrived, max(0., raw_delivered))
        remaining = e.queues.total()+e.in_flight.total()
        reached = abs(e.now-self.T) <= self.tolerances['time_s']
        result = dict(schema='dynamic_k_n1a_engineering_result_v1',
                      scope='ENGINEERING_TEST_ONLY', scientific_gate_pass=False,
                      bindings=self.evidence_binding.verify(),
                      input_trace_sha256=self.input_trace_sha256,
                      initial_state_sha256=self.initial_state_sha256,
                      T_s=self.T, injection_end_s=e.trace.arrival_horizon_s,
                      simulated_until_s=e.now, dynamic_terminal_count=COUNT,
                      tolerances=deepcopy(self.tolerances),
                      evaluation_completed_normally=reached,
                      terminal_accounting_covers_0_T=reached,
                      all_offered_business_delivered=(e.now >= e.trace.arrival_horizon_s
                                                     and remaining <= tol
                                                     and abs(arrived-delivered) <= tol),
                      termination_reason='REACHED_T' if reached else 'ENGINEERING_CHECKPOINT',
                      offered_bits=arrived, delivered_bits=delivered, N_T_bits=remaining,
                      queued_bits=e.queues.total(), in_flight_bits=e.in_flight.total(),
                      J_T_bit_s=math.fsum(areas), R_del_T=delivered/arrived if arrived else 1.,
                      delivered_bit_age_integral_bit_s=None, mean_delivered_fluid_delay_s=None,
                      delivered_fluid_age_implemented=False)
        result.update(self.ledger.metrics())
        validate_measurement(result)
        return result


def validate_measurement(result):
    """Reject nonfinite, out-of-range and contradictory measured fields."""
    r = result
    require(r['schema'] == 'dynamic_k_n1a_engineering_result_v1'
            and r['scope'] == 'ENGINEERING_TEST_ONLY'
            and r['scientific_gate_pass'] is False, 'ENGINEERING_LABEL_REQUIRED')
    require(r['dynamic_terminal_count'] == COUNT, 'TERMINAL_COUNT_MISMATCH')
    tol = r['tolerances']
    for k in ('time_s', 'energy_J', 'business_bits'):
        finite(tol[k], k)
    T = finite(r['T_s'], 'T_s', minimum=1e-12)
    until = finite(r['simulated_until_s'], 'until', maximum=T)
    finite(r['injection_end_s'], 'injection_end', minimum=1e-12, maximum=T)
    def close(a, b, tolerance, code):
        require(abs(a-b) <= tolerance, code)
    for name in ('evaluation_completed_normally', 'terminal_accounting_covers_0_T',
                 'all_offered_business_delivered', 'delivered_fluid_age_implemented'):
        require(type(r[name]) is bool, 'BOOLEAN_REQUIRED:' + name)
    reached = abs(until-T) <= tol['time_s']
    require(r['evaluation_completed_normally'] == reached
            and r['terminal_accounting_covers_0_T'] == reached, 'COMPLETION_CLOCK_MISMATCH')
    require(r['termination_reason'] == ('REACHED_T' if reached else 'ENGINEERING_CHECKPOINT'),
            'TERMINATION_REASON_MISMATCH')
    five, four = r['five_execution_state_dwell_s'], r['four_energy_state_dwell_s']
    require(set(five) == set(EXECUTION_STATES) and set(four) == set(ENERGY_STATES),
            'DWELL_STATE_SET_MISMATCH')
    for state, value in five.items():
        finite(value, state, maximum=COUNT*until+COUNT*tol['time_s'])
    for state, value in four.items():
        finite(value, state, maximum=COUNT*until+COUNT*tol['time_s'])
        close(value, five[state]+(five['DRAINING'] if state == 'ACTIVE' else 0.),
              COUNT*tol['time_s'], 'ENERGY_EXECUTION_DWELL_MISMATCH')
    per_terminal = r['per_terminal_execution_dwell_s']
    require(len(per_terminal) == COUNT
            and len({tuple(row['terminal_id']) for row in per_terminal}) == COUNT,
            'PER_TERMINAL_INVENTORY_MISMATCH')
    for row in per_terminal:
        require(set(row['dwell_s']) == set(EXECUTION_STATES), 'PER_TERMINAL_STATES_MISMATCH')
        for value in row['dwell_s'].values():
            finite(value, 'terminal_dwell', maximum=until+tol['time_s'])
        close(math.fsum(row['dwell_s'].values()), until, tol['time_s'], 'TERMINAL_TIME_GAP')
    for state in five:
        close(math.fsum(row['dwell_s'][state] for row in per_terminal), five[state],
              COUNT*tol['time_s'], 'TERMINAL_AGGREGATE_MISMATCH')
    close(math.fsum(five.values()), COUNT*until, COUNT*tol['time_s'], 'TOTAL_DWELL_GAP')
    for name in ('E_LCT_J', 'standby_baseline_energy_J', 'DeltaE_LCT_J', 'offered_bits',
                 'delivered_bits', 'N_T_bits', 'queued_bits', 'in_flight_bits', 'J_T_bit_s'):
        finite(r[name], name)
    close(r['E_LCT_J'], math.fsum(POWER_W[s]*five[s] for s in five),
          tol['energy_J'], 'ENERGY_DWELL_MISMATCH')
    close(r['standby_baseline_energy_J'], COUNT*until*5., tol['energy_J'], 'BASELINE_MISMATCH')
    close(r['DeltaE_LCT_J'], r['E_LCT_J']-r['standby_baseline_energy_J'],
          tol['energy_J'], 'INCREMENTAL_ENERGY_MISMATCH')
    require(r['E_LCT_J'] <= COUNT*until*45.+tol['energy_J'], 'ENERGY_UPPER_BOUND')
    close(r['offered_bits'], r['delivered_bits']+r['N_T_bits'],
          tol['business_bits'], 'BUSINESS_CONSERVATION_MISMATCH')
    close(r['N_T_bits'], r['queued_bits']+r['in_flight_bits'],
          tol['business_bits'], 'RESIDUAL_STATE_MISMATCH')
    require(r['delivered_bits'] <= r['offered_bits'], 'DELIVERED_EXCEEDS_OFFERED')
    finite(r['R_del_T'], 'delivery_ratio', maximum=1.)
    close(r['R_del_T'], r['delivered_bits']/r['offered_bits'] if r['offered_bits'] else 1.,
          1e-12, 'DELIVERY_RATIO_MISMATCH')
    require(r['J_T_bit_s'] <= r['offered_bits']*until+tol['business_bits']*until,
            'BACKLOG_AREA_UPPER_BOUND')
    complete = (until >= r['injection_end_s'] and r['N_T_bits'] <= tol['business_bits']
                and abs(r['offered_bits']-r['delivered_bits']) <= tol['business_bits'])
    require(r['all_offered_business_delivered'] == complete, 'DELIVERY_COMPLETION_MISMATCH')
    require(r['delivered_bit_age_integral_bit_s'] is None
            and r['mean_delivered_fluid_delay_s'] is None
            and r['delivered_fluid_age_implemented'] is False, 'N1B_NOT_IMPLEMENTED')
    samples = r['K_time_series']
    require(bool(samples) and samples[0]['t_s'] == 0. and samples[-1]['t_s'] == until,
            'INCOMPLETE_TOPOLOGY_TIMELINE')
    previous = -1.
    for sample in samples:
        t = finite(sample['t_s'], 'K_time', maximum=until)
        require(t > previous, 'DUPLICATE_OR_NONMONOTONIC_K_TIME')
        previous = t
        for key in ('K_active_admissible', 'K_draining', 'setup_connection_count',
                    'setup_terminal_count', 'retargeting_terminal_count',
                    'acquiring_terminal_count', 'setup_reserved_terminal_count'):
            value = sample[key]
            require(type(value) is int and 0 <= value <= (160 if key in (
                'K_active_admissible', 'K_draining', 'setup_connection_count') else COUNT),
                'TOPOLOGY_COUNT_OUT_OF_RANGE:' + key)
        require(sample['setup_terminal_count'] == sample['retargeting_terminal_count']
                + sample['acquiring_terminal_count'], 'SETUP_SUM_MISMATCH')
        require(2*(sample['K_active_admissible']+sample['K_draining'])
                + sample['setup_terminal_count'] <= COUNT, 'PHYSICAL_OCCUPANCY_EXCEEDED')
        require(sample['setup_terminal_count'] <= sample['setup_reserved_terminal_count']
                and sample['setup_connection_count'] <= sample['setup_terminal_count']
                and sample['setup_reserved_terminal_count'] % 2 == 0,
                'SETUP_RESERVATION_MISMATCH')
    # Link-time and terminal-time agree independently of log sampling density.
    for count_key, state in (('K_active_admissible', 'ACTIVE'), ('K_draining', 'DRAINING'),
                             ('retargeting_terminal_count', 'RETARGETING'),
                             ('acquiring_terminal_count', 'ACQUIRING')):
        area = math.fsum(a[count_key]*(b['t_s']-a['t_s']) for a, b in zip(samples, samples[1:]))
        close(area*(2 if state in ('ACTIVE', 'DRAINING') else 1), five[state],
              COUNT*tol['time_s'], 'TOPOLOGY_DWELL_AREA_MISMATCH')
    return True
