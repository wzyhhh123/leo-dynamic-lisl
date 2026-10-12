"""Versionable, controller-independent piecewise-constant fluid traffic traces."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math


@dataclass(frozen=True)
class TrafficSegment:
    start_s: float
    end_s: float
    rates_bit_s: dict
    label: str = ""


class PiecewiseConstantTrafficTrace:
    """An immutable cumulative-arrival definition, independent of simulator steps."""
    schema = "gate_d0_piecewise_constant_fluid_trace_v1"

    def __init__(self, commodity_ids, segments):
        self.commodity_ids = tuple(commodity_ids)
        if not self.commodity_ids or len(set(self.commodity_ids)) != len(self.commodity_ids):
            raise ValueError("DUPLICATE_OR_EMPTY_COMMODITY_IDS")
        self.segments = tuple(segments)
        if not self.segments:
            raise ValueError("EMPTY_TRAFFIC_TRACE")
        expected_start = 0.0
        for segment in self.segments:
            if (not math.isfinite(segment.start_s) or not math.isfinite(segment.end_s)
                    or segment.start_s != expected_start or segment.end_s <= segment.start_s):
                raise ValueError("NONCONTIGUOUS_OR_INVALID_TRAFFIC_SEGMENT")
            if set(segment.rates_bit_s) != set(self.commodity_ids):
                raise ValueError("TRAFFIC_COMMODITY_SET_MISMATCH")
            if any(not math.isfinite(float(rate)) or float(rate) < 0.0
                   for rate in segment.rates_bit_s.values()):
                raise ValueError("INVALID_TRAFFIC_RATE")
            expected_start = segment.end_s
        self.arrival_horizon_s = self.segments[-1].end_s

    @classmethod
    def from_dict(cls, document):
        segments = [TrafficSegment(float(row["start_s"]), float(row["end_s"]),
                                   {str(k): float(v) for k, v in row["rates_bit_s"].items()},
                                   str(row.get("label", "")))
                    for row in document["segments"]]
        trace = cls(tuple(document["commodity_ids"]), segments)
        if document.get("schema") not in (None, cls.schema):
            raise ValueError("UNKNOWN_TRAFFIC_TRACE_SCHEMA")
        return trace

    def to_dict(self):
        return {
            "schema": self.schema,
            "representation": "exogenous_fluid_workload_bits",
            "commodity_ids": list(self.commodity_ids),
            "arrival_horizon_s": self.arrival_horizon_s,
            "segments": [{"start_s": item.start_s, "end_s": item.end_s,
                          "label": item.label,
                          "rates_bit_s": {key: item.rates_bit_s[key]
                                          for key in sorted(item.rates_bit_s)}}
                         for item in self.segments],
        }

    def canonical_bytes(self):
        return (json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")

    def sha256(self):
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def rate_at(self, time_s):
        if time_s < 0.0:
            raise ValueError("NEGATIVE_TRACE_TIME")
        if time_s >= self.arrival_horizon_s:
            return {key: 0.0 for key in self.commodity_ids}
        for segment in self.segments:
            if segment.start_s <= time_s < segment.end_s:
                return dict(segment.rates_bit_s)
        raise AssertionError("TRACE_GAP")

    def boundaries_after(self, time_s):
        return tuple(segment.end_s for segment in self.segments if segment.end_s > time_s)

    def cumulative_arrivals(self, time_s):
        if time_s < 0.0:
            raise ValueError("NEGATIVE_TRACE_TIME")
        result = {key: 0.0 for key in self.commodity_ids}
        for segment in self.segments:
            duration = max(0.0, min(time_s, segment.end_s) - segment.start_s)
            if duration <= 0.0:
                continue
            for key, rate in segment.rates_bit_s.items():
                result[key] += rate * duration
        return result

    def total_arrivals(self):
        return self.cumulative_arrivals(self.arrival_horizon_s)
