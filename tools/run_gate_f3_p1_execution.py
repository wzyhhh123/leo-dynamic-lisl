"""Execute only the frozen Gate F3 P1 12-run block in manifest order."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
import uuid


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT/"src"))

from dynamic_lisl.common import read_json  # noqa: E402
from dynamic_lisl.gate_e2_experiments import GateE2Assets  # noqa: E402
from dynamic_lisl.gate_f3_p1_execution import (  # noqa: E402
    EXECUTION_SHA, F3_SHA, OVERLAY_SHA, P1RunExecutor, canonical_hash,
    file_hash, summarize_run,
)
from dynamic_lisl.gate_f3_p1_evidence import (  # noqa: E402
    detailed_invariant_report, final_state_evidence,
)
from dynamic_lisl.f3_progress import PassiveProgressRecorder  # noqa: E402
from dynamic_lisl.b4_runtime_seal import validate_runtime, paused_record  # noqa: E402


RUNTIME_PHASE1_SHA = "605220d3437a1580da9f87b68d71fbe607d9646c75a16e715281bed39bae73f4"
RUNTIME_PHASE2A_SHA = "ec6d9696a5dffcaa89dd21b2fdc7f7dabfd99b844915c1ae027439a585ea55f5"
RUNTIME_PHASE2B1_SHA = "1c0c4aaf5512b490a37661701074ca59daaefda45cd537f162470b9eb0799707"
RUNTIME_PHASE2B2_SHA = "fdc24c670a1c48562f9314e2ddb329aebc68e8a82ac14798e5271a0410a44862"
INFLIGHT_CLOSURE_SHA = "b4696d6afcc4967b49b4f4299d274bf5bd23e66c407a32f6154415e2d386919f"


HISTORICAL = {
    "configs/gate_f3_p1_status.json":
        "164bd07f8d80319b07029944db86b0cb70a4dacfef8227225d6b7ac2d6ea3ed3",
    "docs/GATE_F3_P1_RESULT_CN.md":
        "09a966f158a10849490661d6f7e03540e726e17f5abf197602e8e6a435a5af38",
    "outputs/gate_f3_p1_20260925T050259_813979Z/report.json":
        "2125233b4cf2256cd8587febb148c0d880dbbaca596d259519a4aa18f2bdace6",
    "configs/gate_f3_p1_execution_status.json":
        "ce8463e546afc69ba8cf26a7ff4822531d43120b1d0392ab4d1791ab55d50fb6",
    "docs/GATE_F3_P1_EXECUTION_RESULT_CN.md":
        "aa53cfbd294b7c61d76b19d93a825ea1d58d66b70a7898808573c91ad135a37e",
    "outputs/gate_f3_p1_execution_20260925T055958_725913Z/report.json":
        "716490760d78d745ba2bfd49f6e0ab7074333835bb495420d1e19eaed92f84d4",
    "outputs/gate_f3_p1_execution_20260925T055958_725913Z/run_ledger.jsonl":
        "eb583ae9ff2c25e6ad96e83df076e550a39437b96107954190cd9ca23b6e6168",
}

SCIENTIFIC_FILES = (
    "src/dynamic_lisl/baseline_controllers.py",
    "src/dynamic_lisl/scientific_controllers.py",
    "src/dynamic_lisl/rollout_controller.py",
    "src/dynamic_lisl/rollout_evaluator.py",
    "src/dynamic_lisl/forecast.py",
    "src/dynamic_lisl/production_candidate_source.py",
    "src/dynamic_lisl/candidate_proposer.py",
    "src/dynamic_lisl/controller_runner.py",
    "src/dynamic_lisl/terminal_executor.py",
    "src/dynamic_lisl/gate_c_simplified_feasibility.py",
    "src/dynamic_lisl/transition_service_orchestrator.py",
    "src/dynamic_lisl/common_router.py",
    "src/dynamic_lisl/traffic_trace.py",
    "configs/z_moderate_v1.json",
    "outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json",
    "configs/gate_d0_od_manifest_16.json",
    "configs/gate_f3_experiment_human_freeze_v1.json",
    "configs/gate_f3_execution_manifest_v1.json",
    "configs/gate_f3_candidate_source_drain_human_freeze_v1.json",
    "configs/gate_f3_traffic_profiles_v1.json",
    "configs/gate_f3_traffic_hotspot_migration_v1.json",
    "configs/hardware_gate_c_simplified_v1.json",
    "outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl",
)


def dump(path, value):
    """Crash-safe JSON evidence write in the destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+f".tmp-{uuid.uuid4().hex}")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True,
                                ensure_ascii=False, allow_nan=False)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def dump_jsonl(path, rows):
    """Crash-safe JSONL evidence write in the destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+f".tmp-{uuid.uuid4().hex}")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_valid(document, expected):
    body = dict(document)
    observed = body.pop("canonical_sha256")
    return observed == expected == canonical_hash(body)


def hashes(paths):
    return {name: file_hash(PROJECT/name) for name in paths}


def preflight():
    b4_chain, b4_overlays = validate_runtime(PROJECT)
    contract = read_json(PROJECT/"configs/gate_f3_experiment_human_freeze_v1.json")
    execution = read_json(PROJECT/"configs/gate_f3_execution_manifest_v1.json")
    overlay = read_json(PROJECT/"configs/gate_f3_candidate_source_drain_human_freeze_v1.json")
    runtime_phase1 = read_json(
        PROJECT/"configs/gate_f3_runtime_phase1_overlay_v1.json")
    runtime_phase1_report = read_json(
        PROJECT/runtime_phase1["equivalence_evidence"]["report"])
    runtime_phase2a = read_json(
        PROJECT/"configs/gate_f3_runtime_phase2a_overlay_v1.json")
    runtime_phase2a_report = read_json(
        PROJECT/runtime_phase2a["equivalence_evidence"]["report"])
    runtime_phase2b1 = read_json(
        PROJECT/"configs/gate_f3_runtime_phase2b1_overlay_v1.json")
    runtime_phase2b1_report = read_json(
        PROJECT/runtime_phase2b1["equivalence_evidence"]["report"])
    runtime_phase2b2 = read_json(
        PROJECT/"configs/gate_f3_runtime_phase2b2_overlay_v1.json")
    runtime_phase2b2_report = read_json(
        PROJECT/runtime_phase2b2["equivalence_evidence"]["report"])
    inflight_closure = read_json(
        PROJECT/"configs/gate_f3_inflight_closure_repair_v1.json")
    inflight_closure_report = read_json(
        PROJECT/inflight_closure["equivalence_evidence"]["report"])
    runtime_overlays = (runtime_phase1, runtime_phase2a,
                        runtime_phase2b1, runtime_phase2b2,
                        inflight_closure, b4_overlays[1], *b4_overlays[2:])
    p1 = [row for row in execution["runs"] if row["block_id"] == "P1"]
    a_to_e2 = read_json(PROJECT/"configs/gate_f0_frozen_a_to_e2_hashes.json")
    a_to_e2_observed = hashes(a_to_e2["files"])
    runtime_phase1_valid = (
        canonical_valid(runtime_phase1, RUNTIME_PHASE1_SHA)
        and file_hash(PROJECT/runtime_phase1[
            "equivalence_evidence"]["report"])
            == runtime_phase1["equivalence_evidence"]["report_sha256"]
        and runtime_phase1_report["pass"] is True
        and runtime_phase1_report["proposal_equivalence"] is True
        and runtime_phase1["frozen_scientific_semantics_changed"] is False
        and runtime_phase1["registered_P1_executed"] is False)
    runtime_phase2a_valid = (
        canonical_valid(runtime_phase2a, RUNTIME_PHASE2A_SHA)
        and file_hash(PROJECT/runtime_phase2a[
            "equivalence_evidence"]["report"])
            == runtime_phase2a["equivalence_evidence"]["report_sha256"]
        and runtime_phase2a_report["pass"] is True
        and runtime_phase2a_report["controller_equivalence"]
            == {"B1": True, "B3": True}
        and runtime_phase2a_report["phase2b_started"] is False
        and runtime_phase2a["frozen_scientific_semantics_changed"] is False
        and runtime_phase2a["registered_P1_executed"] is False)
    runtime_phase2b1_valid = (
        canonical_valid(runtime_phase2b1, RUNTIME_PHASE2B1_SHA)
        and file_hash(PROJECT/runtime_phase2b1[
            "equivalence_evidence"]["report"])
            == runtime_phase2b1["equivalence_evidence"]["report_sha256"]
        and runtime_phase2b1_report["pass"] is True
        and runtime_phase2b1_report["controller_equivalence"]
            == {"B1": True, "B3": True}
        and runtime_phase2b1_report["path_search_count_unchanged"] is True
        and runtime_phase2b1_report["phase2b2_started"] is False
        and runtime_phase2b1["frozen_scientific_semantics_changed"] is False
        and runtime_phase2b1["registered_P1_executed"] is False)
    runtime_phase2b2_valid = (
        canonical_valid(runtime_phase2b2, RUNTIME_PHASE2B2_SHA)
        and file_hash(PROJECT/runtime_phase2b2[
            "equivalence_evidence"]["report"])
            == runtime_phase2b2["equivalence_evidence"]["report_sha256"]
        and runtime_phase2b2_report["pass"] is True
        and runtime_phase2b2_report["controller_equivalence"]
            == {"B1": True, "B3": True}
        and runtime_phase2b2_report[
            "path_search_reduction_exactly_explained_by_destination_duplicates"]
            is True
        and runtime_phase2b2_report["phase2b3_started"] is False
        and runtime_phase2b2["frozen_scientific_semantics_changed"] is False
        and runtime_phase2b2["registered_P1_executed"] is False)
    inflight_closure_valid = (
        canonical_valid(inflight_closure, INFLIGHT_CLOSURE_SHA)
        and file_hash(PROJECT/inflight_closure[
            "equivalence_evidence"]["report"])
            == inflight_closure["equivalence_evidence"]["report_sha256"]
        and inflight_closure_report["pass"] is True
        and inflight_closure_report["inflight_closure_equivalence"] is True
        and inflight_closure_report["conservation_preserved"] is True
        and inflight_closure_report["thresholds_unchanged"] is True
        and inflight_closure_report["registered_P1_executed"] is False
        and inflight_closure["frozen_scientific_semantics_changed"] is False
        and inflight_closure["registered_P1_executed"] is False)
    runtime_overlay_paths = set().union(*(
        set(row["optimized_code_hashes"]) for row in runtime_overlays))

    runtime_successor_checks = []
    def runtime_chain_valid():
        for name in runtime_overlay_paths:
            cursor = None
            for runtime_overlay in runtime_overlays:
                optimized = runtime_overlay["optimized_code_hashes"].get(name)
                if optimized is None:
                    continue
                parent = runtime_overlay["parent_code_hashes"].get(name)
                if cursor is None:
                    cursor = parent
                    if name in a_to_e2["files"]:
                        if cursor != a_to_e2["files"][name]:
                            return False
                elif parent != cursor:
                    return False
                cursor = optimized
            if cursor is None:
                return False
            from runtime_successor_chain import validate_runtime_chain
            checked = validate_runtime_chain(PROJECT, name, cursor, file_hash(PROJECT/name))
            runtime_successor_checks.append(checked)
            if not checked['pass']:
                return False
        return all(
            a_to_e2_observed[name] == expected
            for name, expected in a_to_e2["files"].items()
            if name not in runtime_overlay_paths)

    runtime_overlay_chain_valid = runtime_chain_valid()
    parent_expected = contract["parent_hashes"]
    parent_observed = {
        group: hashes(names) for group, names in parent_expected.items()}
    prior_attempt_roots = sorted(
        (PROJECT/"outputs").glob("gate_f3_p1_execution_*"))
    prior_attempt_records = []
    for root in prior_attempt_roots:
        report_path = root/"report.json"
        abort_path = root/"RUNTIME_ABORT_RECORD.txt"
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            prior_attempt_records.append({
                "attempt": root.name,
                "status": report.get("status"),
                "result_seal": report.get("result_seal"),
                "source": "report.json",
            })
        elif abort_path.is_file():
            abort_text = abort_path.read_text(encoding="utf-8")
            prior_attempt_records.append({
                "attempt": root.name,
                "status": ("ABORTED_FOR_RUNTIME_ENGINEERING"
                           if "status = ABORTED_FOR_RUNTIME_ENGINEERING" in abort_text
                           else "UNKNOWN_ABORT_RECORD"),
                "result_seal": ("NO" if "P1_result_seal = NO" in abort_text
                                else None),
                "source": "RUNTIME_ABORT_RECORD.txt",
            })
        else:
            paused = paused_record(PROJECT, root, b4_chain)
            prior_attempt_records.append(paused or {
                "attempt": root.name, "status": "MISSING_STATUS_EVIDENCE",
                "result_seal": None, "source": None})
    historical_attempt_tree_hashes = {
        root.name: artifact_hashes(root) for root in prior_attempt_roots}
    def b4_parent_successor_valid(name,expected,actual):
        cursor=expected
        for runtime_overlay in b4_overlays:
            if runtime_overlay.get('parent_code_hashes',{}).get(name)==cursor:
                cursor=runtime_overlay['optimized_code_hashes'][name]
        if cursor==actual:
            return True
        if name=='src/dynamic_lisl/gate_f3_p1_execution.py':
            from dynamic_lisl.b4_runtime_seal import executor_compatibility_successor
            return executor_compatibility_successor(PROJECT,cursor,actual)
        return False
    checks = {
        "f3_canonical_sha_exact": canonical_valid(contract, F3_SHA),
        "execution_manifest_canonical_sha_exact":
            canonical_valid(execution, EXECUTION_SHA),
        "overlay_canonical_sha_exact": canonical_valid(overlay, OVERLAY_SHA),
        "all_frozen_parent_hashes_unchanged": all(
            b4_parent_successor_valid(name,expected,actual)
            for group, names in parent_expected.items()
            for name, expected in names.items()
            for actual in (parent_observed[group][name],)),
        "b4_runtime_seals_valid": True,
        "all_A_to_E2_semantics_unchanged_with_runtime_overlays": (
            len(a_to_e2["files"]) == 148
            and runtime_phase1_valid
            and runtime_phase2a_valid
            and runtime_phase2b1_valid
            and runtime_phase2b2_valid
            and inflight_closure_valid
            and runtime_overlay_chain_valid),
        "historical_blocked_evidence_unchanged": hashes(HISTORICAL) == HISTORICAL,
        "p1_exactly_12_unique": len(p1) == 12
            and len({row["run_id"] for row in p1}) == 12,
        "p1_all_planned_not_executed": all(
            row["performance_status"] == "PLANNED_NOT_EXECUTED" for row in p1),
        "p1_cross_product_exact": (
            {row["rho"] for row in p1} == {0.5, 0.8, 1.0}
            and {row["controller"] for row in p1} == {"B0", "B1", "B3", "B4"}
            and {row["topology_regime"] for row in p1} == {"Z_MODERATE"}
            and {row["router"] for row in p1} == {"SHORTEST_PROPAGATION_DELAY"}
            and {row["traffic_profile"] for row in p1}
                == {"TRAFFIC_HOTSPOT_MIGRATION_V1"}),
        "historical_execution_attempts_are_blocked_or_recorded_abort": (
            len(prior_attempt_roots) >= 1
            and len(prior_attempt_records) == len(prior_attempt_roots)
            and all((record["status"] in (
                        "BLOCKED", "ABORTED_FOR_RUNTIME_ENGINEERING")
                     or (record["status"] == "PAUSED_INCOMPLETE"
                         and record.get("archive_verified") is True))
                    and record["result_seal"] == "NO"
                    for record in prior_attempt_records)),
        "old_blocker_preserved": overlay["parent"]["historical_blocker"]
            == "GATE_F3_P1_EXECUTION_BLOCKED_BY_CANDIDATE_SOURCE_NOT_FROZEN",
    }
    report = {
        "schema": "gate_f3_p1_preflight_v1", "time_utc": utc_now(),
        "checks": checks, "pass": all(checks.values()),
        "P1_run_ids_in_frozen_order": [row["run_id"] for row in p1],
        "canonical_hashes": {"F3": F3_SHA, "execution_manifest": EXECUTION_SHA,
                             "F3_0_1_overlay": OVERLAY_SHA,
                             "runtime_phase1": RUNTIME_PHASE1_SHA,
                             "runtime_phase2a": RUNTIME_PHASE2A_SHA,
                             "runtime_phase2b1": RUNTIME_PHASE2B1_SHA,
                             "runtime_phase2b2": RUNTIME_PHASE2B2_SHA},
        "historical_hashes": hashes(HISTORICAL),
        "historical_attempt_records": prior_attempt_records,
        "historical_attempt_tree_hashes": historical_attempt_tree_hashes,
        "frozen_parent_hashes": parent_observed,
        "b4_runtime_chain": b4_chain,
        "runtime_successor_chain_checks": runtime_successor_checks,
    }
    return report, execution, p1


def artifact_hashes(directory, exclude=()):
    exclude = set(exclude)
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name not in exclude:
            result[str(path.relative_to(directory)).replace("\\", "/")] = file_hash(path)
    return result


class P1InvariantFailure(AssertionError):
    """Raised only after every available failure artifact is durable."""


def _write_run_artifact_hashes(run_dir):
    values = artifact_hashes(run_dir, exclude={"artifact_hashes.json"})
    document = {
        "schema": "gate_f3_p1_run_artifact_hashes_v1", "files": values,
        "canonical_sha256": canonical_hash(values),
    }
    dump(run_dir/"artifact_hashes.json", document)
    return document


def persist_run_evidence(run_dir, row, run, final, invariants,
                         scientific_hashes_unchanged):
    """Persist all evidence first; only then evaluate aggregate invariants."""
    run_manifest = {
        "schema": "gate_f3_p1_executed_run_manifest_v1",
        "frozen_manifest_row": row,
        "frozen_manifest_row_sha256": canonical_hash(row),
        "candidate_source_overlay_canonical_sha256": OVERLAY_SHA,
        "execution_manifest_canonical_sha256": EXECUTION_SHA,
    }
    state_evidence = final_state_evidence(row, run, final)

    # Required A--J ordering: no aggregate boolean is evaluated above here.
    dump(run_dir/"run_manifest.json", run_manifest)
    dump(run_dir/"final_metrics.json", final)
    dump(run_dir/"invariant_report.json", invariants)
    dump(run_dir/"final_state_evidence.json", state_evidence)
    dump_jsonl(run_dir/"action_timeline.jsonl", run.get("actions", ()))
    dump_jsonl(run_dir/"transition_timeline.jsonl",
               run["engine_result"].get("terminal_event_sequence", ()))
    dump_jsonl(run_dir/"candidate_source_audit.jsonl",
               run.get("candidate_audits", ()))
    dump_jsonl(run_dir/"timeseries_1s.jsonl", run.get("timeseries", ()))
    dump_jsonl(run_dir/"drain_continuation_audit.jsonl",
               run.get("drain_continuation_audit", ()))
    _write_run_artifact_hashes(run_dir)

    # Aggregate evaluation occurs only after the detailed evidence and its
    # hashes have been durably written.
    failed = [name for name, record in invariants["invariants"].items()
              if record["pass"] is not True]
    invariants["aggregate_pass"] = not failed
    invariants["aggregate_evaluated_after_initial_evidence_persistence"] = True
    dump(run_dir/"invariant_report.json", invariants)

    if failed:
        diagnostic = (
            "P1_RUN_INVARIANT_FAILURE\n"
            f"run_id={row['run_id']}\n"
            f"failed_checks={','.join(failed)}")
        evidence_names = sorted(
            path.name for path in run_dir.iterdir() if path.is_file())
        summary = {
            "schema": "gate_f3_p1_failure_summary_v1",
            "run_id": row["run_id"],
            "failure_stage": "POST_RUN_INVARIANT_VALIDATION",
            "failed_invariant_names": failed,
            "all_invariant_boolean_results": {
                name: record["pass"]
                for name, record in invariants["invariants"].items()},
            "first_failed_invariant_name": failed[0],
            "scientific_code_hashes_unchanged":
                bool(scientific_hashes_unchanged),
            "simulator_completed_before_validation": True,
            "final_simulation_time_s":
                run["engine_result"]["metrics"]["evaluation_end_s"],
            "complete_or_censored_classification": final.get("status"),
            "exception_text": diagnostic,
            "evidence_files_written": evidence_names+["failure_summary.json"],
        }
        dump(run_dir/"failure_summary.json", summary)
        _write_run_artifact_hashes(run_dir)
        raise P1InvariantFailure(diagnostic)

    _write_run_artifact_hashes(run_dir)
    return final, invariants


def write_run(run_dir, row, run, scientific_hashes_unchanged=True):
    final = summarize_run(row, run)
    invariants = detailed_invariant_report(row, run, final)
    return persist_run_evidence(
        run_dir, row, run, final, invariants,
        scientific_hashes_unchanged=scientific_hashes_unchanged)


def pair_record(a, b, name):
    result = {
        "contrast": name,
        "run_a": a["run_id"], "run_b": b["run_id"],
        "status_pair": [a["status"], b["status"]],
        "residual_backlog_bits_pair": [a["residual_backlog_bits"],
                                       b["residual_backlog_bits"]],
        "delivery_ratio_pair": [a["delivery_ratio"], b["delivery_ratio"]],
        "completion_time_s_pair": [a["completion_time_s"], b["completion_time_s"]],
    }
    if a["status"] == b["status"] == "COMPLETE":
        result.update({
            "comparison_policy": "COMPLETE_PAIR",
            "Delta_J_a_minus_b": a["J_bit_s"]-b["J_bit_s"],
            "relative_J_a_vs_b": (a["J_bit_s"]-b["J_bit_s"])/b["J_bit_s"],
            "Delta_mean_bit_delay_a_minus_b":
                a["mean_bit_delay_s"]-b["mean_bit_delay_s"],
        })
    else:
        result.update({
            "comparison_policy": "CENSOR_POLICY_APPLIED",
            "Delta_J_a_minus_b": None, "relative_J_a_vs_b": None,
            "Delta_mean_bit_delay_a_minus_b": None,
        })
    return result


def paired_analysis(final_by_key):
    primary = []
    secondary = []
    for rho in (0.5, 0.8, 1.0):
        values = {controller: final_by_key[(rho, controller)]
                  for controller in ("B0", "B1", "B3", "B4")}
        row = pair_record(values["B4"], values["B3"], "B4_vs_B3")
        row["rho"] = rho
        row["Delta_J_B4_minus_B3"] = row.pop("Delta_J_a_minus_b")
        row["relative_J_B4_vs_B3"] = row.pop("relative_J_a_vs_b")
        row["Delta_mean_bit_delay_B4_minus_B3"] = row.pop(
            "Delta_mean_bit_delay_a_minus_b")
        primary.append(row)
        for a, b in (("B4", "B1"), ("B3", "B1"), ("B1", "B0")):
            other = pair_record(values[a], values[b], f"{a}_vs_{b}")
            other["rho"] = rho
            secondary.append(other)
    return {
        "schema": "gate_f3_p1_paired_analysis_v1",
        "sign_convention": "Delta_J_B4_minus_B3 = J_B4 - J_B3",
        "primary_contrast": primary, "secondary_contrasts": secondary,
        "global_controller_ranking": "FORBIDDEN_AND_NOT_COMPUTED",
    }


def opening_figure(root, run_dirs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    controllers = ("B0", "B1", "B3", "B4")
    data = {"schema": "gate_f3_p1_opening_figure_data_v1", "rho": 0.8,
            "topology": "Z_MODERATE",
            "router": "SHORTEST_PROPAGATION_DELAY",
            "traffic": "TRAFFIC_HOTSPOT_MIGRATION_V1", "controllers": {}}
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for controller in controllers:
        run_dir = run_dirs[(0.8, controller)]
        rows = [json.loads(line) for line in
                (run_dir/"timeseries_1s.jsonl").read_text(encoding="utf-8").splitlines()]
        actions = [json.loads(line) for line in
                   (run_dir/"action_timeline.jsonl").read_text(encoding="utf-8").splitlines()]
        replaces = [x["decision_time_s"] for x in actions
                    if x["selected_action"] == "REPLACE"]
        transitions = sorted({float(x["time"]) for x in
            [json.loads(line) for line in
             (run_dir/"transition_timeline.jsonl").read_text(encoding="utf-8").splitlines()]})
        data["controllers"][controller] = {
            "timeseries": rows, "replace_markers_s": replaces,
            "physical_transition_markers_s": transitions,
        }
        axes[0].plot([x["time_s"] for x in rows],
                     [x["N_total_bits"] for x in rows], label=controller)
        axes[1].plot([x["time_s"] for x in rows],
                     [x["Q_total_bits"] for x in rows], label=controller)
        for value in replaces:
            axes[0].axvline(value, alpha=0.08, linewidth=0.7)
            axes[1].axvline(value, alpha=0.08, linewidth=0.7)
    for axis, ylabel in zip(axes, ("N(t) [bit]", "Q(t) [bit]")):
        for boundary in (60, 120, 180, 240):
            axis.axvline(boundary, color="black", linestyle="--", alpha=0.3)
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.2)
    axes[0].legend(ncol=4)
    axes[1].set_xlabel("Time [s]")
    fig.suptitle("Gate F3 P1 opening case: rho=0.8, Z_MODERATE")
    fig.tight_layout()
    fig.savefig(root/"opening_figure.png", dpi=180)
    plt.close(fig)
    dump(root/"opening_figure_data.json", data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="resume an existing authorized P1 root")
    progress = parser.add_mutually_exclusive_group()
    progress.add_argument(
        "--progress-dir",
        help="external passive telemetry directory (excluded from science artifacts)")
    progress.add_argument(
        "--disable-progress", action="store_true",
        help="explicitly disable passive telemetry (the compatibility default)")
    args = parser.parse_args()

    if args.output:
        root = Path(args.output).resolve()
        context = read_json(root/"execution_context.json")
        execution = read_json(PROJECT/"configs/gate_f3_execution_manifest_v1.json")
        p1 = [row for row in execution["runs"] if row["block_id"] == "P1"]
        if context["P1_run_ids_in_frozen_order"] != [x["run_id"] for x in p1]:
            raise AssertionError("RESUME_CONTEXT_MANIFEST_MISMATCH")
    else:
        report, execution, p1 = preflight()
        if not report["pass"]:
            print("GATE_F3_P1_BLOCKED_BY_FROZEN_INPUT_MISMATCH")
            print(json.dumps({k: v for k, v in report["checks"].items() if not v},
                             indent=2))
            return 2
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        root = PROJECT/"outputs"/f"gate_f3_p1_execution_{stamp}"
        root.mkdir(parents=True, exist_ok=False)
        dump(root/"preflight_report.json", report)
        dump(root/"execution_context.json", {
            "schema": "gate_f3_p1_execution_context_v1",
            "created_utc": utc_now(),
            "P1_run_ids_in_frozen_order": [x["run_id"] for x in p1],
            "F3_canonical_sha256": F3_SHA,
            "execution_manifest_canonical_sha256": EXECUTION_SHA,
            "overlay_canonical_sha256": OVERLAY_SHA,
        })
        dump(root/"scientific_code_hash_report.json", {
            "schema": "gate_f3_p1_scientific_code_hash_report_v1",
            "before": hashes(SCIENTIFIC_FILES), "after": None,
            "unchanged": None,
        })
        dump(root/"frozen_hash_report.json", {
            "schema": "gate_f3_p1_frozen_hash_report_v1",
            "preflight": report, "postflight": None,
        })

    progress_root = (Path(args.progress_dir).resolve()
                     if args.progress_dir and not args.disable_progress else None)
    if progress_root is not None:
        try:
            progress_root.relative_to(root)
        except ValueError:
            pass
        else:
            raise ValueError("PROGRESS_DIR_MUST_BE_OUTSIDE_SCIENTIFIC_ATTEMPT_ROOT")
        progress_root.mkdir(parents=True, exist_ok=True)

    ledger_path = root/"run_ledger.jsonl"
    existing = ([json.loads(line) for line in ledger_path.read_text(
        encoding="utf-8").splitlines()] if ledger_path.exists() else [])
    completed = {row["run_id"] for row in existing
                 if row["outcome"] in ("COMPLETE", "CENSORED")}
    if any(row["outcome"] == "FAILED" for row in existing):
        raise AssertionError("CANNOT_RESUME_AFTER_FATAL_FAILED_LEDGER_ENTRY")

    assets = GateE2Assets()
    ledger = list(existing)
    try:
        for ordinal, row in enumerate(p1, 1):
            if row["run_id"] in completed:
                continue
            run_dir = root/"runs"/row["run_id"]
            if run_dir.exists():
                raise AssertionError("PARTIAL_RUN_DIRECTORY_REQUIRES_MANUAL_AUDIT")
            run_dir.mkdir(parents=True)
            started = utc_now()
            print(f"P1 START {ordinal}/12 {row['run_id']}", flush=True)
            recorder = (PassiveProgressRecorder(
                progress_root, attempt_id=root.name, run_id=row["run_id"],
                controller=row["controller"], rho=row["rho"])
                if progress_root is not None else None)
            executor = P1RunExecutor(
                assets, row, progress_recorder=recorder,
                b4_parallel_workers=8 if row["controller"] == "B4" else 0)
            run = executor.run()
            scientific_before = read_json(
                root/"scientific_code_hash_report.json")["before"]
            final, invariants = write_run(
                run_dir, row, run,
                scientific_hashes_unchanged=(
                    scientific_before == hashes(SCIENTIFIC_FILES)))
            entry = {
                "run_id": row["run_id"],
                "manifest_row_sha256": canonical_hash(row),
                "execution_ordinal": ordinal, "controller": row["controller"],
                "rho": row["rho"], "traffic_hash": row["traffic_trace_sha256"],
                "topology_hash": file_hash(PROJECT/"configs/z_moderate_v1.json"),
                "router": row["router"],
                "candidate_source_overlay_sha256": OVERLAY_SHA,
                "start_timestamp": started, "finish_timestamp": utc_now(),
                "outcome": final["status"],
                "result_path": str(run_dir.relative_to(PROJECT)).replace("\\", "/"),
                "artifact_hash_summary": read_json(run_dir/"artifact_hashes.json")
                    ["canonical_sha256"],
            }
            ledger.append(entry)
            dump_jsonl(ledger_path, ledger)
            print(f"P1 DONE  {ordinal}/12 {final['status']} "
                  f"t={final['final_time_s']:.6f}s switches={final['switch_count']} "
                  f"runtime={final['runtime_s']:.2f}s", flush=True)
    except Exception as exc:
        failed_row = p1[len(ledger)] if len(ledger) < len(p1) else None
        if failed_row is not None:
            ledger.append({
                "run_id": failed_row["run_id"],
                "manifest_row_sha256": canonical_hash(failed_row),
                "execution_ordinal": len(ledger)+1,
                "controller": failed_row["controller"], "rho": failed_row["rho"],
                "start_timestamp": started if "started" in locals() else utc_now(),
                "finish_timestamp": utc_now(), "outcome": "FAILED",
                "failure": f"{type(exc).__name__}: {exc}",
            })
            dump_jsonl(ledger_path, ledger)
        dump(root/"report.json", {
            "schema": "gate_f3_p1_execution_report_v1",
            "status": "BLOCKED", "result_seal": "NO",
            "blocker": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "P1_registered_runs_executed": f"{sum(x['outcome'] in ('COMPLETE','CENSORED') for x in ledger)}/12",
            "P2_started": False, "RL_started": False,
        })
        print("Gate F3 P1 execution = BLOCKED", flush=True)
        print(f"GATE_F3_P1_EXECUTION_BLOCKED_BY_{type(exc).__name__.upper()}",
              flush=True)
        raise

    successful = [row for row in ledger
                  if row["outcome"] in ("COMPLETE", "CENSORED")]
    if len(successful) != 12 or len({x["run_id"] for x in successful}) != 12:
        raise AssertionError("P1_LEDGER_NOT_EXACTLY_12_SCIENTIFIC_OUTCOMES")
    final_by_key = {}
    run_dirs = {}
    for row in p1:
        run_dir = root/"runs"/row["run_id"]
        final = read_json(run_dir/"final_metrics.json")
        final_by_key[(float(row["rho"]), row["controller"])] = final
        run_dirs[(float(row["rho"]), row["controller"])] = run_dir
    analysis = paired_analysis(final_by_key)
    dump(root/"paired_analysis.json", analysis)
    opening_figure(root, run_dirs)
    finals = [final_by_key[(float(row["rho"]), row["controller"])] for row in p1]
    summary = {
        "schema": "gate_f3_p1_summary_v1",
        "registered_runs": 12,
        "COMPLETE_count": sum(x["status"] == "COMPLETE" for x in finals),
        "CENSORED_count": sum(x["status"] == "CENSORED" for x in finals),
        "FAILED_count": 0,
        "runs": finals,
        "primary_contrast_B4_vs_B3": analysis["primary_contrast"],
        "global_controller_ranking": "FORBIDDEN_AND_NOT_COMPUTED",
    }
    dump(root/"p1_summary.json", summary)

    scientific_report = read_json(root/"scientific_code_hash_report.json")
    scientific_report["after"] = hashes(SCIENTIFIC_FILES)
    scientific_report["unchanged"] = (
        scientific_report["before"] == scientific_report["after"])
    dump(root/"scientific_code_hash_report.json", scientific_report)
    post, _, _ = preflight()
    # The current attempt now coexists with the immutable historical attempt.
    # Compare only the tree(s) captured by this attempt's preflight.
    preflight_document = read_json(root/"preflight_report.json")
    historical_pre = preflight_document["historical_attempt_tree_hashes"]
    historical_post = post["historical_attempt_tree_hashes"]
    post["checks"]["historical_execution_attempts_are_blocked_or_recorded_abort"] = True
    post["checks"]["historical_attempt_trees_unchanged"] = all(
        historical_post.get(name) == tree
        for name, tree in historical_pre.items())
    post["pass"] = all(post["checks"].values())
    frozen_report = read_json(root/"frozen_hash_report.json")
    frozen_report["postflight"] = post
    dump(root/"frozen_hash_report.json", frozen_report)

    report = {
        "schema": "gate_f3_p1_execution_report_v1", "status": "PENDING_CHECKER",
        "result_seal": "NO", "output_root": str(root.relative_to(PROJECT)).replace("\\", "/"),
        "P1_registered_runs_executed": "12/12",
        "P1_COMPLETE_count": summary["COMPLETE_count"],
        "P1_CENSORED_count": summary["CENSORED_count"],
        "P1_FAILED_count": 0, "scientific_hashes_unchanged": scientific_report["unchanged"],
        "F3_performance_started": True, "P2_readiness": "READY",
        "P2_started": False, "RL_started": False,
    }
    dump(root/"report.json", report)
    dump(root/"artifact_hashes.json", {
        "schema": "gate_f3_p1_root_artifact_hashes_v1",
        "files": artifact_hashes(root, exclude={"artifact_hashes.json"}),
    })
    print(f"P1 EXECUTION DATA READY FOR CHECKER {root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
