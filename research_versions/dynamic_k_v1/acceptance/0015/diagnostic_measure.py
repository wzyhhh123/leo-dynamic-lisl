"""Explicit diagnostic evaluator subtype; unchanged measurement/assertions."""
from runtime.n1a import *
import support as w
class DiagnosticMeasure(FixedHorizonEvaluator):
    def capture_and_validate(self,result):
        paths=sorted(self.diagnostic_directory.glob('VALIDATION_INPUT_*.json'))
        w.write(self.diagnostic_directory/('VALIDATION_INPUT_'+str(len(paths)+1).zfill(3)+'.json'),result)
        validate_measurement(result)
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
        self.capture_and_validate(result)
        return result
