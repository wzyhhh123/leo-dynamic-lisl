"""Engineering-only B4 clone timing and three root-branch exact comparisons."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT / "src")]
from dynamic_lisl.common import read_json
from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_e2_experiments import GateE2Assets
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor
from dynamic_lisl.rollout_clone import APPEND_ONLY_HISTORY_FIELDS


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def history(engine):
    return {key: deepcopy(getattr(engine, key)) for key in
            (*APPEND_ONLY_HISTORY_FIELDS, "graph_event_sequence", "action_results",
             "transition_episodes", "reporting_samples")} | {
                 "terminal_log": deepcopy(engine.executor.log)}


def branch_state(engine):
    # Include all accounting, event, routing and reporting fields; physical
    # provider objects are compared through canonical state and their outputs.
    excluded = {"executor", "trace", "delay", "router", "actions", "queues", "in_flight"}
    return {key: value for key, value in vars(engine).items() if key not in excluded} | {
        "canonical": engine.canonical_state(), "terminal_log": engine.executor.log,
        "executor_invariant_checks": engine.executor.invariant_checks,
        "queue_fields": vars(engine.queues), "inflight_fields": vars(engine.in_flight),
        "router_fields": vars(engine.router),
    }


def main():
    out = PROJECT / "outputs" / ("b4_lightweight_clone_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    out.mkdir(parents=True)
    frozen = {str(path.relative_to(PROJECT)): digest(path)
              for path in (PROJECT / "configs").glob("*.json")}
    assets = GateE2Assets()
    manifest = read_json(PROJECT / "configs/gate_f3_execution_manifest_v1.json")
    template = next(row for row in manifest["runs"] if row["block_id"] == "P1"
                    and row["controller"] == "B4" and row["rho"] == 0.5)
    runner = P1RunExecutor(assets, {**template, "run_id": "ENGINEERING_CLONE_ONLY",
                                  "block_id": "ENGINEERING_PROFILE_ONLY"})
    engine = runner.engine
    state = controller_visible_state(engine)
    specs = tuple(runner.candidate_source(state, {"epoch_index": 0,
                   "regime": "Z_MODERATE", "terminal_executor": engine.executor}))
    proposed = runner.proposer.propose(engine.executor, specs, assets.physical,
                                      assets.fixed, "Z_MODERATE")
    by_id = {row.proposal_id: row for row in specs}
    timings = {"legacy": [], "lightweight": []}
    for _ in range(5):
        for mode, method in (("legacy", engine.clone_legacy_reference), ("lightweight", engine.clone)):
            start = time.perf_counter()
            cloned = method()
            timings[mode].append(time.perf_counter() - start)
            assert cloned.canonical_state() == engine.canonical_state()
            assert not cloned.reporting_enabled and cloned.reporting_samples == []
    before = history(engine)
    canonical_before = engine.canonical_state()
    forecast = runner.controller._forecast(state)
    records = [None]
    for stratum in ("BBM_REQUIRED", "MBB_STRUCTURALLY_FEASIBLE"):
        records.append(next(row for row in proposed["proposals"] if row["stratum"] == stratum))
    branches_report = []
    original = type(engine).clone
    for record in records:
        branch_pair = []
        results = []
        wall = {}
        for mode in ("legacy", "lightweight"):
            def capture(instance):
                branch = instance.clone_legacy_reference() if mode == "legacy" else original(instance)
                branch_pair.append(branch)
                return branch
            start = time.perf_counter()
            with patch.object(type(engine), "clone", capture):
                result = (runner.controller.evaluator.evaluate_hold(forecast) if record is None
                          else runner.controller.evaluator.evaluate_candidate(
                              forecast, record, by_id[record["proposal_id"]]))
            wall[mode] = time.perf_counter() - start
            results.append(asdict(result))
        assert results[0] == results[1], "BRANCH_RESULT_MISMATCH"
        assert branch_state(branch_pair[0]) == branch_state(branch_pair[1]), "BRANCH_STATE_MISMATCH"
        assert history(engine) == before and engine.canonical_state() == canonical_before
        row = {"proposal_id": None if record is None else record["proposal_id"],
               "stratum": "HOLD" if record is None else record["stratum"],
               "exact_equal": True, "wall_s": wall,
               "result": results[1]}
        branches_report.append(row)
        print(json.dumps({"completed": row["stratum"], "wall_s": wall}), flush=True)
        (out / "partial_branches.json").write_text(json.dumps(branches_report, indent=2), encoding="utf-8")
    assert all(digest(PROJECT / key) == value for key, value in frozen.items())
    medians = {key: statistics.median(values) for key, values in timings.items()}
    report = {"status": "B4_LIGHTWEIGHT_CLONE_ENGINEERING_PASS",
              "scope": "160-star rho=0.5 t=0 clone plus HOLD/first-BBM/first-MBB 10s forecasts",
              "registered_P1_executed": False, "full_17_branch_decision_compared": False,
              "clone_wall_s": timings, "clone_median_wall_s": medians,
              "clone_speedup": medians["legacy"] / medians["lightweight"],
              "raw_candidate_ids": [row.proposal_id for row in specs],
              "proposal_set_sha256": proposed["proposal_set_sha256"],
              "final_proposal_ids": [row["proposal_id"] for row in proposed["proposals"]],
              "branch_comparisons": branches_report,
              "config_hashes_unchanged": True, "config_hashes": frozen,
              "field_audit": {key: ("shallow history records / independent list" if key in APPEND_ONLY_HISTORY_FIELDS
                                     else "deepcopy unchanged") for key in vars(engine)},
              "terminal_log_policy": "full history retained; independent list; readonly old records",
              "reporting_override": "false/empty as in legacy ObservationalE2Engine.clone",
              "source_hashes": {str(path.relative_to(PROJECT)): digest(path) for path in
                  (PROJECT / "src/dynamic_lisl").glob("*.py")}}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "clone_speedup": report["clone_speedup"],
                      "clone_median_wall_s": medians, "status": report["status"]}), flush=True)


if __name__ == "__main__":
    main()
