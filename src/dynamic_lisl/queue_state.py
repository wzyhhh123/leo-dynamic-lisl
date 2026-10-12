"""Per-satellite, per-commodity waiting-work accounting."""
from collections import defaultdict
import math


class QueueState:
    def __init__(self):
        self.bits = defaultdict(float)
        self.compensation = defaultdict(float)

    def get(self, node, commodity_id):
        return self.bits[(node, commodity_id)]

    def set(self, node, commodity_id, value, tolerance=1e-7):
        value = float(value)
        if value < -tolerance:
            raise AssertionError(f"NEGATIVE_QUEUE key={key} total={total} delta={delta} tolerance={tolerance}")
        self.bits[(node, commodity_id)] = max(0.0, value)


    def add(self, node, commodity_id, delta, tolerance=1e-7):
        key = (node, commodity_id)
        total = self.bits[key] + float(delta)
        if total < -tolerance:
            raise AssertionError(f"NEGATIVE_QUEUE key={key} total={total} delta={delta} tolerance={tolerance}")
        self.bits[key] = max(0.0, total)

    def total(self, commodity_id=None):
        return math.fsum(value for (_, key), value in self.bits.items()
                   if commodity_id is None or key == commodity_id)

    def snapshot(self):
        return {node + "|" + commodity: value
                for (node, commodity), value in sorted(self.bits.items()) if value != 0.0}
