"""Gate F3-1a reporting-only invariant and final-state evidence builders."""
from __future__ import annotations

import math

from .gate_f3_p1_execution import f3_trace_identity


def invariant_record(name, passed, observed, expected, tolerance=None,
                     first_failure_time_s=None, first_failure_object=None,
                     diagnostic=None):
    """Create one explicit record without changing the underlying check."""
    margin = None
    max_violation = None
    if (isinstance(observed, (int, float)) and not isinstance(observed, bool)
            and isinstance(expected, (int, float)) and not isinstance(expected, bool)):
        margin = float(expected)-float(observed)
        max_violation = max(0.0, float(observed)-float(expected))
    return {
        "name": name, "pass": bool(passed),
        "observed_value": observed,
        "limit_or_expected_value": expected,
        "tolerance": tolerance, "margin": margin,
        "first_failure_time_s": first_failure_time_s,
        "first_failure_object": first_failure_object,
        "max_violation": max_violation,
        "diagnostic": diagnostic,
    }


def detailed_invariant_report(row, run, final_metrics):
    """Build all frozen post-run checks, leaving aggregate PASS unevaluated."""
    result = run["engine_result"]
    metrics = result["metrics"]
    trace_hash, _ = f3_trace_identity(row["rho"])
    conservation_tolerance = float(metrics["arrived_bits"])*1e-12+1e-3
    conservation_value = float(metrics["max_abs_conservation_error_bits"])
    capacity_tolerance = 0.01
    capacity_value = float(metrics["max_capacity_violation_bit_s"])
    queue_values = [float(value) for value in result.get("queues", {}).values()]
    minimum_queue = min(queue_values, default=0.0)
    negative_count = int(metrics["negative_queue_count"])
    final_time = float(metrics["evaluation_end_s"])
    residual = float(metrics["residual_backlog_bits"])
    zero_threshold = 0.01
    drain_limit = 600.0
    status_semantics = (
        (final_metrics["status"] == "COMPLETE" and residual <= zero_threshold)
        or (final_metrics["status"] == "CENSORED"
            and abs(final_time-drain_limit) <= 1e-12
            and residual > zero_threshold))

    audits = run.get("candidate_audits", ())
    max_bbm_before = max((int(x["raw_BBM_count_before_cap"])
                          for x in audits), default=0)
    max_mbb_before = max((int(x["raw_MBB_count_before_cap"])
                          for x in audits), default=0)
    max_bbm_after = max((int(x["raw_BBM_count_after_cap"])
                         for x in audits), default=0)
    max_mbb_after = max((int(x["raw_MBB_count_after_cap"])
                         for x in audits), default=0)
    max_raw_total = max((int(x["raw_BBM_count_after_cap"])
                         +int(x["raw_MBB_count_after_cap"])
                         for x in audits), default=0)
    max_final = max((int(x["final_proposal_count"])
                     for x in audits), default=0)

    times = [float(x["time_s"]) for x in run.get("timeseries", ())]
    expected_last = float(math.floor(final_time+1e-12))
    reporting_details = {
        "expected_first_time_s": 0.0,
        "expected_last_time_s": expected_last,
        "actual_first_time_s": times[0] if times else None,
        "actual_last_time_s": times[-1] if times else None,
        "expected_count": int(expected_last)+1,
        "actual_count": len(times),
        "strictly_monotonic": all(b > a for a, b in zip(times, times[1:])),
        "duplicate_timestamp_count": len(times)-len(set(times)),
    }
    reporting_pass = bool(times) and all((
        abs(times[0]) <= 1e-12,
        abs(times[-1]-expected_last) <= 1e-12,
        len(times) == int(expected_last)+1,
        reporting_details["strictly_monotonic"],
        reporting_details["duplicate_timestamp_count"] == 0,
    ))

    invariants = {
        "traffic_identity": invariant_record(
            "traffic_identity", trace_hash == row["traffic_trace_sha256"],
            trace_hash, row["traffic_trace_sha256"], diagnostic={
                "rho": row["rho"], "profile": row["traffic_profile"]}),
        "work_conservation": invariant_record(
            "work_conservation", conservation_value <= conservation_tolerance,
            conservation_value, conservation_tolerance,
            tolerance=conservation_tolerance, diagnostic={
                "max_relative_conservation_error":
                    metrics["max_relative_conservation_error"],
                "frozen_check_formula":
                    "max_abs_error <= arrived_bits*1e-12 + 1e-3",
                "first_failure_not_instrumented": True}),
        "capacity": invariant_record(
            "capacity", capacity_value <= capacity_tolerance,
            capacity_value, capacity_tolerance, tolerance=capacity_tolerance,
            diagnostic={"edge_and_time_of_maximum_not_instrumented": True}),
        "queue_nonnegative": invariant_record(
            "queue_nonnegative", negative_count == 0,
            {"minimum_queue_bits": minimum_queue,
             "negative_queue_count": negative_count},
            {"negative_queue_count": 0}, tolerance=0.0,
            diagnostic={"first_offending_queue_not_instrumented": True}),
        "drain_status": invariant_record(
            "drain_status", final_time <= drain_limit+1e-12,
            {"final_time_s": final_time,
             "total_unfinished_work_bits": residual,
             "arrival_horizon_s": float(metrics["arrival_horizon_s"])},
            {"drain_limit_s": drain_limit,
             "zero_threshold_bits": zero_threshold}),
        "complete_or_censored_semantics": invariant_record(
            "complete_or_censored_semantics", status_semantics,
            {"status": final_metrics["status"], "final_time_s": final_time,
             "total_unfinished_work_bits": residual},
            {"COMPLETE": "unfinished<=0.01",
             "CENSORED": "final_time=600 and unfinished>0.01"}),
        "candidate_raw_BBM_cap": invariant_record(
            "candidate_raw_BBM_cap", max_bbm_after <= 32,
            max_bbm_after, 32, tolerance=0,
            diagnostic={"maximum_uncapped_BBM_count": max_bbm_before}),
        "candidate_raw_MBB_cap": invariant_record(
            "candidate_raw_MBB_cap", max_mbb_after <= 32,
            max_mbb_after, 32, tolerance=0,
            diagnostic={"maximum_uncapped_MBB_count": max_mbb_before}),
        "candidate_raw_total_cap": invariant_record(
            "candidate_raw_total_cap", max_raw_total <= 64,
            max_raw_total, 64, tolerance=0),
        "final_proposer_top_k": invariant_record(
            "final_proposer_top_k", max_final <= 16,
            max_final, 16, tolerance=0),
        "reporting_timeseries_consistency": invariant_record(
            "reporting_timeseries_consistency", reporting_pass,
            reporting_details,
            {"grid_s": 1.0, "first_time_s": 0.0,
             "last_time_s": expected_last}),
        "decision_epoch_boundary": invariant_record(
            "decision_epoch_boundary", all(
                float(item["decision_time_s"]) < 600.0-1e-12
                for item in run.get("actions", ())),
            max((float(item["decision_time_s"])
                 for item in run.get("actions", ())), default=None),
            "strictly less than 600 s"),
    }
    return {
        "schema": "gate_f3_p1_detailed_invariant_report_v2",
        "run_id": row["run_id"],
        "aggregate_pass": None,
        "aggregate_evaluated_after_initial_evidence_persistence": False,
        "invariants": invariants,
    }


def final_state_evidence(row, run, final_metrics):
    result = run["engine_result"]
    metrics = result["metrics"]
    terminal = result.get("final_state", {}).get("terminal", {})
    links = terminal.get("links", ())
    return {
        "schema": "gate_f3_p1_final_state_evidence_v1",
        "run_id": row["run_id"],
        "diagnostic_only_not_accepted_scientific_result": True,
        "final_time_s": metrics["evaluation_end_s"],
        "total_arrived_bits": metrics["arrived_bits"],
        "total_delivered_bits": metrics["delivered_bits"],
        "total_queue_bits": metrics["queued_bits_at_end"],
        "total_inflight_bits": metrics["in_flight_bits_at_end"],
        "total_unfinished_work_bits": metrics["residual_backlog_bits"],
        "complete_or_censored_classification": final_metrics["status"],
        "active_dynamic_bindings": [item for item in links
                                    if not item.get("draining", False)],
        "pending_reservations": terminal.get("reservations", []),
        "pending_gate_b_events_count": len(terminal.get("events", [])),
        "controller_action_count": len(run.get("actions", ())),
        "candidate_source_decision_count": len(run.get("candidate_audits", ())),
    }
