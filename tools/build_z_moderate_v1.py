"""One-time writer for the frozen Z_MODERATE v1 structural asset."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from dynamic_lisl.z_moderate_construction import construct_z_moderate

OUT = PROJECT / "configs/z_moderate_v1.json"
if OUT.exists():
    raise FileExistsError("REFUSE_TO_OVERWRITE_Z_MODERATE_V1")
document = construct_z_moderate(PROJECT)
if document["status"] != "CONSTRUCTED":
    raise RuntimeError("Z_MODERATE_CONSTRUCTION_INFEASIBLE_AT_REGISTERED_EPOCH")
OUT.write_text(
    json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(json.dumps({
    "status": document["status"],
    "canonical_sha256": document["canonical_sha256"],
    "selected_addition": document["selected_addition"],
    "structural_audit": document["structural_audit"],
}, indent=2, ensure_ascii=False))
