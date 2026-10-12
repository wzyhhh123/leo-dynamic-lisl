"""Passive Gate F3 progress telemetry with atomic latest-state updates."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import uuid


MAX_HORIZON_S = 600.0
ARRIVAL_HORIZON_S = 240.0


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _phase(sim_time_s):
    return "ARRIVAL" if float(sim_time_s) < ARRIVAL_HORIZON_S else "DRAIN"


class PassiveProgressRecorder:
    """Write values supplied by the normal path; never invokes science APIs."""

    def __init__(self, output_dir, *, attempt_id, run_id, controller, rho):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.attempt_id = str(attempt_id)
        self.run_id = str(run_id)
        self.controller = str(controller)
        self.rho = float(rho)
        self.jsonl_path = self.output_dir / "progress.jsonl"
        self.latest_path = self.output_dir / "progress_latest.json"

    def _base(self, event, sim_time_s, decision_epoch_index):
        sim_time_s = float(sim_time_s)
        return {
            "schema": "gate_f3_passive_progress_v1",
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "controller": self.controller,
            "rho": self.rho,
            "status": "RUNNING",
            "epoch_status": str(event),
            "wall_clock_iso": _utc_now(),
            "sim_time_s": sim_time_s,
            "decision_epoch_index": int(decision_epoch_index),
            "phase": _phase(sim_time_s),
            "max_horizon_progress_pct": 100.0 * sim_time_s / MAX_HORIZON_S,
            "max_horizon_progress_is_completion_probability": False,
        }

    def epoch_start(self, *, sim_time_s, decision_epoch_index):
        self._write(self._base("EPOCH_START", sim_time_s, decision_epoch_index))

    def epoch_end(self, *, sim_time_s, decision_epoch_index, **available):
        record = self._base("EPOCH_END", sim_time_s, decision_epoch_index)
        record.update(available)
        self._write(record)

    def _write(self, record):
        line = json.dumps(record, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False) + "\n"
        with self.jsonl_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        temporary = self.latest_path.with_name(
            self.latest_path.name + ".tmp-" + uuid.uuid4().hex)
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, indent=2, sort_keys=True,
                                    ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.latest_path)
