"""F3-only continuation adapter over the unchanged D2 engine API."""
from __future__ import annotations

from dataclasses import dataclass
import math


F3_COMPLETE_THRESHOLD_BITS = 0.01
F3_CENSOR_LIMIT_S = 600.0
F3_COMPLETE = "COMPLETE"
F3_CENSORED = "CENSORED"
F3_CONTINUE_DRAIN = "CONTINUE_DRAIN"
F3_BOUNDARY_REACHED = "BOUNDARY_REACHED"
NO_PROGRESS_CODE = "GATE_F3_DRAIN_ADAPTER_BLOCKED_BY_NO_PROGRESS_INTERFACE"


def unfinished_work_bits(engine):
    return float(engine.queues.total()+engine.in_flight.total())


def classify_f3_termination(time_s, unfinished_bits, *,
                            complete_threshold_bits=F3_COMPLETE_THRESHOLD_BITS,
                            censor_limit_s=F3_CENSOR_LIMIT_S):
    """Apply only the frozen F3 COMPLETE/CENSORED decision."""
    time_s = float(time_s)
    unfinished_bits = float(unfinished_bits)
    if not math.isfinite(time_s) or not math.isfinite(unfinished_bits):
        raise ValueError("NONFINITE_F3_DRAIN_STATE")
    if unfinished_bits <= float(complete_threshold_bits):
        return F3_COMPLETE
    if time_s >= float(censor_limit_s)-1e-12:
        return F3_CENSORED
    return F3_CONTINUE_DRAIN


@dataclass(frozen=True)
class DrainAdvanceOutcome:
    status: str
    result: dict | None
    continuation_iterations: int
    start_time_s: float
    final_time_s: float
    final_unfinished_bits: float
    d2_early_returns_ignored: int


class F3DrainContinuationAdapter:
    """Advance the real D2 engine without treating its return as F3 completion."""

    complete_threshold_bits = F3_COMPLETE_THRESHOLD_BITS
    censor_limit_s = F3_CENSOR_LIMIT_S

    def __init__(self, max_continuation_iterations=100000):
        self.max_continuation_iterations = int(max_continuation_iterations)
        if self.max_continuation_iterations <= 0:
            raise ValueError("POSITIVE_CONTINUATION_ITERATION_LIMIT_REQUIRED")

    def advance_to_boundary(self, engine, boundary_s):
        boundary_s = float(boundary_s)
        if boundary_s <= float(engine.now)+1e-13:
            raise ValueError("F3_DRAIN_BOUNDARY_MUST_BE_IN_FUTURE")
        if boundary_s > self.censor_limit_s+1e-12:
            raise ValueError("F3_DRAIN_BOUNDARY_EXCEEDS_CENSOR_LIMIT")
        start = float(engine.now)
        initial = classify_f3_termination(start, unfinished_work_bits(engine))
        if initial != F3_CONTINUE_DRAIN:
            return DrainAdvanceOutcome(
                initial, None, 0, start, start, unfinished_work_bits(engine), 0)

        last_result = None
        ignored = 0
        for iteration in range(1, self.max_continuation_iterations+1):
            before_time = float(engine.now)
            before_state = engine.canonical_state_sha256()
            last_result = engine.run(boundary_s)
            after_time = float(engine.now)
            after_state = engine.canonical_state_sha256()
            residual = unfinished_work_bits(engine)
            status = classify_f3_termination(after_time, residual)
            if status in (F3_COMPLETE, F3_CENSORED):
                return DrainAdvanceOutcome(
                    status, last_result, iteration, start, after_time,
                    residual, ignored)
            if after_time >= boundary_s-1e-12:
                return DrainAdvanceOutcome(
                    F3_BOUNDARY_REACHED, last_result, iteration, start,
                    after_time, residual, ignored)

            # D2 returned below its own numerical threshold, but F3 still owns
            # the experiment termination decision.  Continue only after proof
            # of real time/state progress.
            ignored += 1
            if (after_time <= before_time+1e-13
                    and after_state == before_state):
                raise RuntimeError(NO_PROGRESS_CODE)
        raise RuntimeError("GATE_F3_DRAIN_ADAPTER_ITERATION_LIMIT_EXCEEDED")
