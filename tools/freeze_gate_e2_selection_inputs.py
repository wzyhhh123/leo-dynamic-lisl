"""One-time freeze of A-Pre-E2 evidence and Gate E2 selected scenarios."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
FROZEN=PROJECT/"configs/gate_e2_frozen_a_to_pre_e2_hashes.json"
SELECTION=PROJECT/"configs/gate_e2_selection_hashes.json"
if FROZEN.exists() or SELECTION.exists():
    raise FileExistsError("REFUSE_TO_OVERWRITE_GATE_E2_FROZEN_HASHES")
def read(path):return json.loads(path.read_text(encoding="utf-8-sig"))
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
pre=read(PROJECT/"configs/pre_e2_absolute_time_status.json")
if pre.get("pre_e2_absolute_time_regression")!="PASS":
    raise RuntimeError("PRE_E2_PASS_REQUIRED")
files=dict(read(PROJECT/"configs/pre_e2_frozen_a_to_e1_hashes.json")["files"])
extra=[
 "configs/pre_e2_absolute_time_status.json",
 "configs/pre_e2_frozen_a_to_e1_hashes.json",
 "docs/PRE_E2_ABSOLUTE_TIME_REGRESSION_CN.md",
 "src/dynamic_lisl/absolute_time_regression.py",
 "tests/test_pre_e2_absolute_time.py",
 "tools/check_pre_e2_absolute_time.py"]
evidence=PROJECT/pre["evidence"]
extra.extend(path.relative_to(PROJECT).as_posix() for path in sorted(evidence.iterdir())
             if path.is_file())
for name in extra:
    if name not in files:
        path=PROJECT/name
        if not path.is_file():raise FileNotFoundError(name)
        files[name]=sha(path)
FROZEN.write_text(json.dumps({
 "schema":"gate_e2_frozen_a_to_pre_e2_hashes_v1",
 "source_pre_e2_evidence":pre["evidence"],"files":files},
 indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
selected_files=[
 "configs/gate_e2_candidate_inventory.json",
 "configs/gate_e2_selected_scenarios.json",
 "src/dynamic_lisl/gate_e2_enumeration.py",
 "tests/test_gate_e2_enumeration.py",
 "tools/prepare_gate_e2_enumeration.py"]
SELECTION.write_text(json.dumps({
 "schema":"gate_e2_selection_hashes_v1",
 "frozen_before_any_paired_branch_execution":True,
 "files":{name:sha(PROJECT/name) for name in selected_files}},
 indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"a_to_pre_e2_files":len(files),
                  "selection_files":len(selected_files),"status":"FROZEN"}))
