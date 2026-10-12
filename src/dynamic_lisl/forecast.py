"""Gate F2 branch-local current-rate-persistence traffic forecast."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment


@dataclass(frozen=True)
class CurrentRatePersistenceForecast:
    start_time_s: float
    horizon_s: float
    rates_bit_s: dict

    forecast_type = "CURRENT_RATE_PERSISTENCE"

    def __post_init__(self):
        if self.horizon_s != 10.0:
            raise ValueError("GATE_F2_FORECAST_HORIZON_MUST_BE_10_SECONDS")
        if self.start_time_s < 0.0:
            raise ValueError("NEGATIVE_FORECAST_START")
        if any(float(value) < 0.0 for value in self.rates_bit_s.values()):
            raise ValueError("NEGATIVE_FORECAST_RATE")

    @property
    def end_time_s(self):
        return self.start_time_s+self.horizon_s

    def document(self):
        return {
            "schema": "gate_f2_current_rate_persistence_forecast_v1",
            "forecast_type": self.forecast_type,
            "forecast_start_time_s": self.start_time_s,
            "forecast_horizon_s": self.horizon_s,
            "rates_bit_s": {key: float(self.rates_bit_s[key])
                             for key in sorted(self.rates_bit_s)},
            "realized_future_trace_access": False,
        }

    def sha256(self):
        payload = json.dumps(self.document(), sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_trace(self):
        """Return an absolute-time trace used only by a cloned branch engine."""
        rates = {key: float(self.rates_bit_s[key]) for key in sorted(self.rates_bit_s)}
        return PiecewiseConstantTrafficTrace(
            tuple(sorted(rates)),
            (TrafficSegment(0.0, self.end_time_s, rates,
                            "gate_f2_current_rate_persistence"),),
        )


def attach_forecast_to_clone(engine, forecast):
    """Replace only the cloned engine's future exogenous traffic source."""
    if abs(engine.now-forecast.start_time_s) > 1e-12:
        raise AssertionError("FORECAST_AND_BRANCH_TIME_MISMATCH")
    trace = forecast.to_trace()
    if set(trace.commodity_ids) != set(engine.by_id):
        raise AssertionError("FORECAST_COMMODITY_SET_MISMATCH")
    engine.trace = trace
    engine.boundaries = list(trace.boundaries_after(engine.now))
    engine.boundary_index = 0
    return engine

