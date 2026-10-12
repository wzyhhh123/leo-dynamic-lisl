"""Version-local read-only D2 observer. Each legacy method executes exactly once."""
from copy import deepcopy
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine


class ObservedD2Engine(TransitionAwareNetworkServiceEngine):
    def __init__(self, *args, **kwargs):
        self.age_observations = []
        super().__init__(*args, **kwargs)

    def _schedule_service_segments(self, new_rates, force_refresh=False):
        prior_sequence = self.sequence
        old_rates = dict(self.service_rates)
        super()._schedule_service_segments(new_rates, force_refresh)
        new_events = sorted(e for e in self.propagation_agenda if e.sequence > prior_sequence)
        self.age_observations.append(dict(kind='SCHEDULE', time=self.now,
            old_rates=old_rates, new_rates=dict(self.service_rates),
            launch_delays=dict(self.service_delays),
            emitted_events=deepcopy(new_events)))

    def _integrate(self, next_time, external, inputs, queue_derivative, delivery_rates):
        record = dict(kind='INTERVAL', start=self.now, end=next_time,
            dt=next_time-self.now, external=dict(external),
            service=dict(self.service_rates), arrival=dict(self.in_flight.arrival_rates),
            delivery=dict(delivery_rates), before=self.age_scalar_state())
        super()._integrate(next_time, external, inputs, queue_derivative, delivery_rates)
        record['after'] = self.age_scalar_state()
        self.age_observations.append(record)

    def _finalize_quiescent_propagation(self, settled_deltas):
        cursor = len(self.propagation_closure_events)
        super()._finalize_quiescent_propagation(settled_deltas)
        for event in self.propagation_closure_events[cursor:]:
            self.age_observations.append(dict(kind='CLOSURE', event=deepcopy(event)))

    def age_scalar_state(self):
        return dict(Q=dict(self.queues.bits), I=dict(self.in_flight.bits),
                    A=dict(self.arrived), D=dict(self.delivered))

    def business_state(self):
        """Every legacy field, not merely canonical_state's subset."""
        return {key: value for key, value in self.__dict__.items()
                if key != 'age_observations'}
