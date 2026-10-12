"""Propagation-state accounting for work that has left a sender queue."""
from collections import defaultdict
import math
from dataclasses import dataclass


@dataclass(order=True, frozen=True)
class RateArrivalEvent:
    time_s: float
    sequence: int
    edge: tuple
    commodity_id: str
    delta_rate_bit_s: float


class InFlightState:
    def __init__(self):
        self.bits = defaultdict(float)
        self.compensation = defaultdict(float)
        self.arrival_rates = defaultdict(float)


    def add_bits(self, edge, commodity_id, delta, tolerance=1e-6):
        key = (edge, commodity_id)
        total = self.bits[key] + float(delta)
        if total < -tolerance:
            raise AssertionError("NEGATIVE_IN_FLIGHT")
        self.bits[key] = max(0.0, total)

    def total(self, commodity_id=None):
        return math.fsum(value for (_, key), value in self.bits.items()
                   if commodity_id is None or key == commodity_id)

    def set_bits(self, edge, commodity_id, value, tolerance=1e-6):
        value = float(value)
        if value < -tolerance:
            raise AssertionError("NEGATIVE_IN_FLIGHT")
        self.bits[(edge, commodity_id)] = max(0.0, value)

    def snapshot(self):
        return {edge[0] + "->" + edge[1] + "|" + commodity: value
                for (edge, commodity), value in sorted(self.bits.items()) if value != 0.0}
