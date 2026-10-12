"""One-time frozen Gate A-E1 evidence baseline for the Pre-E2 gate."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
OUT=PROJECT/"configs/pre_e2_frozen_a_to_e1_hashes.json"
if OUT.exists(): raise FileExistsError("REFUSE_TO_OVERWRITE_PRE_E2_FROZEN_BASELINE")
def read(path):return json.loads(path.read_text(encoding="utf-8-sig"))
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
 return h.hexdigest()
status=read(PROJECT/"configs/gate_e1_status.json")
if status.get("gate_e1")!="PASS":raise RuntimeError("GATE_E1_PASS_REQUIRED")
files=dict(read(PROJECT/"configs/gate_e1_frozen_a_to_e0_hashes.json")["files"])
extra=[
 "configs/gate_e1_execution_manifest.json","configs/gate_e1_break_even_manifest.json",
 "configs/gate_e1_manifest_hashes.json","configs/gate_e1_frozen_a_to_e0_hashes.json",
 "configs/gate_e1_status.json","docs/GATE_E1_EXECUTION_CONTRACT_CN.md",
 "docs/GATE_E1_MECHANISM_RESULT_CN.md","src/dynamic_lisl/gate_e1_experiments.py",
 "tests/test_gate_e1.py","tools/prepare_gate_e1_manifests.py","tools/check_gate_e1.py"]
evidence=PROJECT/status["evidence"]
extra.extend(path.relative_to(PROJECT).as_posix() for path in sorted(evidence.iterdir()) if path.is_file())
for name in extra:
 if name not in files:
  path=PROJECT/name
  if not path.is_file():raise FileNotFoundError(name)
  files[name]=sha(path)
document={"schema":"pre_e2_frozen_a_to_e1_hashes_v1",
          "captured_before_pre_e2_formal_regression":True,
          "source_gate_e1_evidence":status["evidence"].replace("\\","/"),
          "files":files}
OUT.write_text(json.dumps(document,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"frozen_files":len(files),"status":"FROZEN"}))
