"""One-time Gate E0 manifest and Gate A-D baseline hash capture."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new(path, document):
    if path.exists():
        raise FileExistsError(f"REFUSE_TO_OVERWRITE_FROZEN_RECORD:{path}")
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False,
                               sort_keys=True)+"\n", encoding="utf-8")


manifest_files = (
    "configs/gate_e0_sweep_manifest.json",
    "configs/gate_e0_scenario_selection_manifest.json",
)
manifest_hashes = {name: sha(PROJECT/name) for name in manifest_files}
write_new(PROJECT/"configs/gate_e0_manifest_hashes.json", {
    "schema": "gate_e0_manifest_hashes_v1",
    "version": 1,
    "frozen_before_e1_e2": True,
    "files": manifest_hashes,
})

prior = json.loads((PROJECT/"configs/gate_d2_frozen_baseline_hashes.json").read_text(
    encoding="utf-8"))["files"]
d2_status = json.loads((PROJECT/"configs/gate_d2_status.json").read_text(encoding="utf-8"))
d2_evidence = Path(d2_status["evidence"])
extra = [
    "configs/gate_d2_frozen_baseline_hashes.json",
    "configs/gate_d2_fixture_manifest.json",
    "configs/gate_d2_status.json",
    "docs/GATE_D2_INTEGRATION_AUDIT_CN.md",
    "docs/GATE_D2_TRANSITION_SERVICE_CONTRACT_CN.md",
    "docs/GATE_D2_TRANSITION_SERVICE_RESULT_CN.md",
    "src/dynamic_lisl/transition_service_orchestrator.py",
    "src/dynamic_lisl/gate_d2_fixtures.py",
    "tests/test_gate_d2.py",
    "tools/check_gate_d2.py",
]
for path in sorted((PROJECT/d2_evidence).iterdir()):
    if path.is_file():
        extra.append(path.relative_to(PROJECT).as_posix())
files = dict(prior)
for name in extra:
    if name in files:
        continue
    path = PROJECT/name
    if not path.is_file():
        raise FileNotFoundError(f"FROZEN_INPUT_MISSING:{name}")
    files[name] = sha(path)
write_new(PROJECT/"configs/gate_e0_frozen_a_to_d_hashes.json", {
    "schema": "gate_e0_frozen_a_to_d_hashes_v1",
    "captured_before_gate_e0_formal_acceptance": True,
    "source_gate_d2_evidence": d2_evidence.as_posix(),
    "files": files,
})

print(json.dumps({"manifest_files": len(manifest_hashes),
                  "frozen_a_to_d_files": len(files)}, sort_keys=True))
