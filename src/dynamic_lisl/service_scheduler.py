"""Equal-weight, work-conserving max-min service allocation."""
import math


def equal_weight_fair_share(capacity_bit_s, demands_bit_s, tolerance=1e-12):
    if capacity_bit_s < 0.0:
        raise ValueError("NEGATIVE_CAPACITY")
    if any(value < 0.0 or math.isnan(value) for value in demands_bit_s.values()):
        raise ValueError("INVALID_DEMAND")
    allocation = {key: 0.0 for key in demands_bit_s}
    remaining = {key: float(value) for key, value in demands_bit_s.items()
                 if value > tolerance}
    capacity = float(capacity_bit_s)
    while remaining and capacity > tolerance:
        share = capacity / len(remaining)
        satisfied = [key for key, demand in remaining.items()
                     if math.isfinite(demand) and demand <= share + tolerance]
        if not satisfied:
            for key in remaining:
                allocation[key] += share
            capacity = 0.0
            break
        for key in sorted(satisfied):
            amount = min(remaining[key], capacity)
            allocation[key] += amount
            capacity -= amount
            del remaining[key]
    if sum(allocation.values()) > capacity_bit_s + max(tolerance, abs(capacity_bit_s)*1e-12):
        raise AssertionError("CAPACITY_VIOLATION")
    return allocation
