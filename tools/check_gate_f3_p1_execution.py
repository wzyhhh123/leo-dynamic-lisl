"""Validate the sealed state of the newest authorized Gate F3 P1 attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
HISTORICAL = {
    "configs/gate_f3_p1_status.json":
        "164bd07f8d80319b07029944db86b0cb70a4dacfef8227225d6b7ac2d6ea3ed3",
    "docs/GATE_F3_P1_RESULT_CN.md":
        "09a966f158a10849490661d6f7e03540e726e17f5abf197602e8e6a435a5af38",
    "outputs/gate_f3_p1_20260925T050259_813979Z/report.json":
        "2125233b4cf2256cd8587febb148c0d880dbbaca596d259519a4aa18f2bdace6",
}


def read(path):
    return json.loads((PROJECT/path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256((PROJECT/path).read_bytes()).hexdigest()


def main():
    status = read("configs/gate_f3_p1_execution_status.json")
    root = PROJECT/status["evidence"]
    report = json.loads((root/"report.json").read_text(encoding="utf-8"))
    ledger = [json.loads(line) for line in
              (root/"run_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    scientific = json.loads((root/"scientific_code_hash_report.json").read_text(
        encoding="utf-8"))
    checks = {
        "historical_blocked_evidence_unchanged": all(
            digest(path) == expected for path, expected in HISTORICAL.items()),
        "new_attempt_is_blocked": report["status"] == "BLOCKED"
            and status["Gate_F3_P1_execution"] == "BLOCKED",
        "result_not_sealed": report["result_seal"] == "NO"
            and status["P1_result_seal"] == "NO",
        "exactly_one_failed_first_manifest_row": len(ledger) == 1
            and ledger[0]["execution_ordinal"] == 1
            and ledger[0]["outcome"] == "FAILED",
        "zero_scientific_outcomes": status["P1_registered_runs_executed"] == "0/12",
        "remaining_blocks_not_started": not status["P2_started"]
            and not status["RL_started"],
        "frozen_scientific_hashes_unchanged": scientific["unchanged"] is True,
    }
    result = {
        "schema": "gate_f3_p1_execution_check_v1",
        "checks": checks, "pass": all(checks.values()),
        "execution_status": status["Gate_F3_P1_execution"],
        "blocker": status["blocker"],
    }
    out = root/"blocked_attempt_check.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True,
                              ensure_ascii=False)+"\n", encoding="utf-8")
    if not result["pass"]:
        raise SystemExit("GATE_F3_P1_BLOCKED_ATTEMPT_EVIDENCE_CHECK_FAILED")
    print("Gate F3 P1 execution = BLOCKED")
    print("P1 result seal = NO")
    print(status["blocker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
