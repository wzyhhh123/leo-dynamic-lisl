"""ENGINEERING_PROFILE_ONLY short-prefix profiler for production Gate F3 B1."""
from __future__ import annotations

import argparse
import cProfile
import csv
import io
import json
from pathlib import Path
import pstats
import statistics
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from dynamic_lisl.common import read_json  # noqa: E402
from dynamic_lisl.f3_progress import PassiveProgressRecorder  # noqa: E402
from dynamic_lisl.gate_e2_experiments import GateE2Assets  # noqa: E402
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor  # noqa: E402


PROFILE_RUN_ID = "ENGINEERING_PROFILE_ONLY-B1-RHO0p5-SHORT_PREFIX"


def percentile95(values):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    return ordered[max(0, int(0.95 * len(ordered) + 0.999999999)-1)]


def build_parser():
    parser = argparse.ArgumentParser(
        description="Engineering-only cProfile harness; never a registered P1 run")
    parser.add_argument("--sim-end-s", type=float, default=20.0)
    parser.add_argument("--output-dir", default="outputs/manual_b1_profile")
    progress = parser.add_mutually_exclusive_group()
    progress.add_argument(
        "--progress", dest="telemetry_enabled", action="store_true",
        help="enable PassiveProgressRecorder (default)")
    progress.add_argument(
        "--no-progress", dest="telemetry_enabled", action="store_false",
        help="disable passive progress telemetry for overhead measurement")
    parser.set_defaults(telemetry_enabled=True)
    return parser


def make_progress_recorder(output_dir, row, telemetry_enabled):
    if not telemetry_enabled:
        return None
    return PassiveProgressRecorder(
        output_dir, attempt_id=output_dir.name, run_id=row["run_id"],
        controller=row["controller"], rho=row["rho"])


def main():
    args = build_parser().parse_args()
    if args.sim_end_s < 0.0 or args.sim_end_s > 240.0:
        raise SystemExit("--sim-end-s must be within [0, 240] for this short-prefix tool")

    out = Path(args.output_dir)
    if not out.is_absolute():
        out = PROJECT / out
    if out.exists() and any(out.iterdir()):
        raise SystemExit("PROFILE_OUTPUT_DIR_MUST_BE_NEW_OR_EMPTY")
    out.mkdir(parents=True, exist_ok=True)

    manifest = read_json(PROJECT / "configs/gate_f3_execution_manifest_v1.json")
    registered = {row["run_id"] for row in manifest["runs"]
                  if row["block_id"] == "P1"}
    template = next(row for row in manifest["runs"]
                    if row["block_id"] == "P1"
                    and row["controller"] == "B1"
                    and float(row["rho"]) == 0.5)
    row = {**template, "run_id": PROFILE_RUN_ID,
           "block_id": "ENGINEERING_PROFILE_ONLY",
           "performance_status": "ENGINEERING_PROFILE_ONLY_NOT_SCIENTIFIC_RESULT"}
    if row["run_id"] in registered:
        raise AssertionError("PROFILE_MUST_NOT_USE_REGISTERED_P1_RUN_ID")

    recorder = make_progress_recorder(out, row, args.telemetry_enabled)
    profiler = cProfile.Profile()
    wall_start = time.perf_counter()
    profiler.enable()
    assets = GateE2Assets()
    executor = P1RunExecutor(assets, row, progress_recorder=recorder)
    result = executor.run_engineering_prefix(args.sim_end_s)
    profiler.disable()
    total_wall = time.perf_counter()-wall_start
    profiler.dump_stats(str(out / "cprofile.prof"))

    text = io.StringIO()
    stats = pstats.Stats(profiler, stream=text).strip_dirs().sort_stats("cumulative")
    stats.print_stats(50)
    (out / "cprofile_top50.txt").write_text(text.getvalue(), encoding="utf-8")

    fields = (
        "sim_time_s", "decision_epoch_index", "candidate_source_wall_s",
        "proposer_wall_s", "controller_observe_wall_s",
        "network_advance_wall_s", "gate_b_execution_wall_s",
        "epoch_total_wall_s", "final_proposal_count",
    )
    with (out / "epoch_runtime.csv").open(
            "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in result["epoch_runtime_records"]:
            writer.writerow({key: record.get(key) for key in fields})

    epoch_times = [row["epoch_total_wall_s"]
                   for row in result["epoch_runtime_records"]]
    proposal_counts = [row["final_proposal_count"]
                       for row in result["epoch_runtime_records"]]
    simulated = float(result["actual_sim_time_s"])
    report = {
        "schema": "gate_f3_b1_engineering_runtime_profile_v1",
        "classification": "ENGINEERING_PROFILE_ONLY",
        "not_a_registered_P1_experiment": True,
        "not_scientific_performance_evidence": True,
        "registered_P1_run_id_used": False,
        "telemetry_enabled": bool(args.telemetry_enabled),
        "run_id": row["run_id"],
        "scale": 160,
        "topology": "Z_MODERATE",
        "router": "SHORTEST_PROPAGATION_DELAY",
        "rho": 0.5,
        "traffic": "TRAFFIC_HOTSPOT_MIGRATION_V1",
        "requested_sim_end_s": float(args.sim_end_s),
        "simulated_seconds": simulated,
        "total_wall_clock_s": total_wall,
        "wall_seconds_per_simulated_second": (
            total_wall/simulated if simulated > 0.0 else None),
        "decision_epoch_count": len(epoch_times),
        "epoch_wall_s": {
            "mean": statistics.fmean(epoch_times) if epoch_times else None,
            "p95": percentile95(epoch_times),
            "max": max(epoch_times) if epoch_times else None,
        },
        "timing_totals_s": {
            "candidate_source": sum(x["candidate_source_wall_s"]
                                    for x in result["epoch_runtime_records"]),
            "proposer": sum(x["proposer_wall_s"]
                            for x in result["epoch_runtime_records"]),
            "B1_observe": sum(x["controller_observe_wall_s"]
                              for x in result["epoch_runtime_records"]),
            "network_advance": sum(x["network_advance_wall_s"]
                                   for x in result["epoch_runtime_records"]),
            "Gate_B_execution": sum(x["gate_b_execution_wall_s"]
                                    for x in result["epoch_runtime_records"]),
        },
        "proposal_count_distribution": {
            "values": proposal_counts,
            "min": min(proposal_counts) if proposal_counts else None,
            "mean": statistics.fmean(proposal_counts) if proposal_counts else None,
            "max": max(proposal_counts) if proposal_counts else None,
        },
        "final_prefix_state": {
            "canonical_state_sha256": result["canonical_state_sha256"],
            "total_queue_bits": result["total_queue_bits"],
            "total_inflight_bits": result["total_inflight_bits"],
            "action_count": result["action_count"],
        },
        "P2_started": False,
        "RL_started": False,
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "status": "ENGINEERING_PROFILE_ONLY_COMPLETE",
        "output_dir": str(out),
        "simulated_seconds": simulated,
        "total_wall_clock_s": total_wall,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
