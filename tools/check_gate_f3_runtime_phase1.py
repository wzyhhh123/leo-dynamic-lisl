"""Engineering-only Gate F3 runtime Phase 1 equivalence/performance check."""
from __future__ import annotations

import argparse
import cProfile
from copy import deepcopy
import datetime as dt
import hashlib
import json
from pathlib import Path
import pstats
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT))

from dynamic_lisl.candidate_proposer import FrozenTerminalPairProposer  # noqa: E402
from dynamic_lisl.common import read_json  # noqa: E402
from dynamic_lisl.gate_e2_experiments import GateE2Assets  # noqa: E402
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor  # noqa: E402
from dynamic_lisl.terminal_executor import TerminalExecutor  # noqa: E402
from dynamic_lisl.transition_profiler import (  # noqa: E402
    profile_transition_legacy_reference,
)


class LegacyReferenceTerminalExecutor(TerminalExecutor):
    """Pre-Phase-1 recursive submit clone; engineering comparison only."""

    def submit(self, commands):
        return self.submit_legacy_reference(commands)


class CapturingProposer:
    def __init__(self, inner):
        self.inner = inner
        self.results = []

    def propose(self, *args, **kwargs):
        result = self.inner.propose(*args, **kwargs)
        self.results.append(result)
        return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def deepcopy_counts(profiler):
    stats = pstats.Stats(profiler)
    primitive = total = 0
    for (filename, _line, name), values in stats.stats.items():
        if name == "deepcopy" and Path(filename).name == "copy.py":
            primitive += int(values[0])
            total += int(values[1])
    return {"primitive_calls": primitive, "total_calls": total}


def normalized_action(record):
    return {key: value for key, value in record.items()
            if key not in ("controller_decision_runtime_s",
                           "action_canonical_sha256")}


def equivalence_document(executor, result):
    proposal_sets = executor.proposer.results
    return {
        "raw_candidate_ids_by_epoch": [
            [row["proposal_id"] for row in executor.source.last_report[
                "selected_order"]]
        ] if len(proposal_sets) == 1 else None,
        "pruned_by_epoch": [[
            {"proposal_id": row["proposal_id"], "reason": row["reason"]}
            for row in proposal["pruned"]]
            for proposal in proposal_sets],
        "final_proposals_by_epoch": [[{
            key: row[key] for key in (
                "proposal_id", "ready_time_s", "remaining_lifetime_s",
                "usable_lifetime_s", "stratum", "safety_policy",
                "transition_profile_classification")
        } for row in proposal["proposals"]] for proposal in proposal_sets],
        "proposal_ids_by_epoch": [[row["proposal_id"]
                                   for row in proposal["proposals"]]
                                  for proposal in proposal_sets],
        "proposal_set_sha256_by_epoch": [
            proposal["proposal_set_sha256"] for proposal in proposal_sets],
        "selected_actions": [normalized_action(row)
                             for row in result["actions"]],
        "terminal_transition_types": [
            row["actual_gate_b_transition_type"] for row in result["actions"]],
        "canonical_live_state_after_prefix":
            result["canonical_state_sha256"],
        "total_queue_bits": result["total_queue_bits"],
        "total_inflight_bits": result["total_inflight_bits"],
    }


def run_mode(assets, legacy, sim_end_s):
    row = next(value for value in read_json(
        PROJECT / "configs/gate_f3_execution_manifest_v1.json")["runs"]
        if value["block_id"] == "P1"
        and value["controller"] == "B1"
        and float(value["rho"]) == 0.5)
    row = {
        **row,
        "run_id": ("ENGINEERING_PROFILE_ONLY-PHASE1-LEGACY"
                   if legacy else "ENGINEERING_PROFILE_ONLY-PHASE1-OPTIMIZED"),
        "block_id": "ENGINEERING_PROFILE_ONLY",
        "performance_status": "ENGINEERING_PROFILE_ONLY_NOT_SCIENTIFIC_RESULT",
    }
    executor = P1RunExecutor(assets, row, progress_recorder=None)
    if legacy:
        executor.engine.executor.__class__ = LegacyReferenceTerminalExecutor
        inner = FrozenTerminalPairProposer(
            profile_transition_legacy_reference)
    else:
        inner = FrozenTerminalPairProposer()
    executor.proposer = CapturingProposer(inner)
    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    result = executor.run_engineering_prefix(sim_end_s)
    profiler.disable()
    wall = time.perf_counter()-started
    proposer_wall = sum(
        float(value["proposer_wall_s"])
        for value in result["epoch_runtime_records"])
    return {
        "wall_clock_s": wall,
        "proposer_wall_s": proposer_wall,
        "deepcopy": deepcopy_counts(profiler),
        "decision_epochs": len(result["epoch_runtime_records"]),
        "equivalence": equivalence_document(executor, result),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-end-s", type=float, default=0.0)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if args.sim_end_s < 0.0 or args.sim_end_s > 4.0:
        raise SystemExit("PHASE1_PREFIX_MUST_BE_WITHIN_0_TO_4_SECONDS")
    if args.output_dir:
        out = Path(args.output_dir)
        if not out.is_absolute():
            out = PROJECT / out
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime(
            "%Y%m%dT%H%M%S_%fZ")
        out = PROJECT / "outputs" / (
            "gate_f3_runtime_phase1_" + stamp)
    if out.exists() and any(out.iterdir()):
        raise SystemExit("OUTPUT_DIR_MUST_BE_NEW_OR_EMPTY")
    out.mkdir(parents=True, exist_ok=True)

    frozen_before = {
        path: digest(PROJECT/path) for path in (
            "configs/gate_f3_execution_manifest_v1.json",
            "configs/gate_f3_experiment_human_freeze_v1.json",
            "configs/gate_f3_candidate_source_drain_human_freeze_v1.json",
            "src/dynamic_lisl/f3_progress.py",
        )}
    assets = GateE2Assets()
    legacy = run_mode(assets, True, args.sim_end_s)
    optimized = run_mode(assets, False, args.sim_end_s)
    equivalent = legacy["equivalence"] == optimized["equivalence"]
    proposer_speedup = (
        legacy["proposer_wall_s"]/optimized["proposer_wall_s"]
        if optimized["proposer_wall_s"] > 0.0 else None)
    old_calls = legacy["deepcopy"]["total_calls"]
    new_calls = optimized["deepcopy"]["total_calls"]
    report = {
        "schema": "gate_f3_runtime_phase1_report_v1",
        "classification": "ENGINEERING_PROFILE_ONLY",
        "registered_P1_executed": False,
        "sim_end_s": args.sim_end_s,
        "legacy": legacy,
        "optimized": optimized,
        "proposal_equivalence": equivalent,
        "proposer_speedup": proposer_speedup,
        "deepcopy_total_call_reduction": old_calls-new_calls,
        "deepcopy_total_call_reduction_fraction": (
            (old_calls-new_calls)/old_calls if old_calls else None),
        "frozen_inputs_unchanged": frozen_before == {
            path: digest(PROJECT/path) for path in frozen_before},
        "router_optimization_started": False,
        "P1_started": False,
        "P2_started": False,
        "RL_started": False,
    }
    report["pass"] = bool(
        equivalent and report["frozen_inputs_unchanged"]
        and legacy["decision_epochs"] == optimized["decision_epochs"]
        and proposer_speedup is not None and proposer_speedup > 1.0)
    report["status"] = (
        "GATE_F3_RUNTIME_PHASE1_PASS" if report["pass"]
        else "GATE_F3_RUNTIME_PHASE1_FAIL")
    dump(out / "report.json", report)
    dump(out / "legacy_equivalence.json", legacy["equivalence"])
    dump(out / "optimized_equivalence.json", optimized["equivalence"])
    dump(out / "frozen_hashes.json", frozen_before)
    dump(out / "artifact_hashes.json", {
        path.relative_to(out).as_posix(): digest(path)
        for path in sorted(out.rglob("*"))
        if path.is_file() and path.name != "artifact_hashes.json"})
    print(json.dumps({
        "status": report["status"],
        "output_dir": str(out),
        "sim_end_s": args.sim_end_s,
        "decision_epochs": optimized["decision_epochs"],
        "proposal_equivalence": equivalent,
        "legacy_proposer_wall_s": legacy["proposer_wall_s"],
        "optimized_proposer_wall_s": optimized["proposer_wall_s"],
        "proposer_speedup": proposer_speedup,
        "deepcopy_total_call_reduction":
            report["deepcopy_total_call_reduction"],
    }, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
