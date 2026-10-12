"""Freeze the Gate E2 execution implementation before the formal run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "configs/gate_e2_execution_code_hashes.json"

FILES = (
    "configs/gate_e2_execution_points.json",
    "configs/gate_e2_execution_points_hashes.json",
    "configs/gate_e2_selected_scenarios.json",
    "docs/GATE_E2_EXECUTION_CONTRACT_CN.md",
    "src/dynamic_lisl/gate_e2_experiments.py",
    "src/dynamic_lisl/gate_e2_parallel.py",
    "tests/test_gate_e2_execution.py",
    "tools/check_gate_e2.py",
    "tools/prepare_gate_e2_execution_points.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists():
    raise FileExistsError("REFUSE_TO_OVERWRITE_GATE_E2_EXECUTION_CODE_HASHES")

missing = [name for name in FILES if not (PROJECT / name).is_file()]
if missing:
    raise FileNotFoundError(f"MISSING_GATE_E2_EXECUTION_FILES: {missing}")

record = {
    "schema": "gate_e2_execution_code_hashes_v1",
    "frozen_before_formal_scientific_execution": True,
    "files": {name: sha256(PROJECT / name) for name in FILES},
}
OUT.write_text(
    json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False))
