"""Validate sealed exact semantic-preserving runtime hash overlays in tests."""
from __future__ import annotations

import hashlib
import json


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _valid_overlay(project, overlay_path):
    if not overlay_path.is_file():
        return None
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    body = dict(overlay)
    observed_canonical = body.pop("canonical_sha256", None)
    evidence = overlay.get("equivalence_evidence", {})
    report_path = project/evidence.get("report", "")
    if not report_path.is_file():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    phase1_equivalent = report.get("proposal_equivalence") is True
    phase2a_equivalent = (
        report.get("controller_equivalence") == {"B1": True, "B3": True}
        and report.get("phase2b_started") is False)
    phase2b1_equivalent = (
        report.get("controller_equivalence") == {"B1": True, "B3": True}
        and report.get("path_search_count_unchanged") is True
        and report.get("phase2b2_started") is False)
    phase2b2_equivalent = (
        report.get("controller_equivalence") == {"B1": True, "B3": True}
        and report.get(
            "path_search_reduction_exactly_explained_by_destination_duplicates")
            is True
        and report.get("phase2b3_started") is False)
    inflight_closure_equivalent = (
        report.get("inflight_closure_equivalence") is True
        and report.get("conservation_preserved") is True
        and report.get("thresholds_unchanged") is True
        and report.get("registered_P1_executed") is False)
    b4_hash_equivalent = (
        report.get("b4_decision_hash_reuse_equivalence") is True
        and report.get("legacy_decision") == report.get("optimized_decision")
        and isinstance(report.get("legacy_decision"), dict)
        and report.get("legacy_branch_results") == report.get("optimized_branch_results")
        and isinstance(report.get("legacy_branch_results"), list)
        and report.get("config_hashes_unchanged") is True
        and report.get("registered_P1_executed") is False)
    if not bool(
            observed_canonical == _canonical(body)
            and overlay.get("status") == "PASS"
            and overlay.get("frozen_scientific_semantics_changed") is False
            and overlay.get("registered_P1_executed") is False
            and evidence.get("report_sha256") == _sha(report_path)
            and report.get("pass") is True
            and (phase1_equivalent or phase2a_equivalent
                 or phase2b1_equivalent or phase2b2_equivalent
                 or inflight_closure_equivalent or b4_hash_equivalent)):
        return None
    return overlay


def approved_runtime_phase1_change(project, name, frozen_hash, current_hash):
    """Accept only a sealed ordered overlay chain for this file.

    The historical function name is retained so frozen Gate E1 and Pre-E2
    tests do not need to change.
    """
    paths = (
        project/"configs/gate_f3_runtime_phase1_overlay_v1.json",
        project/"configs/gate_f3_runtime_phase2a_overlay_v1.json",
        project/"configs/gate_f3_runtime_phase2b1_overlay_v1.json",
        project/"configs/gate_f3_runtime_phase2b2_overlay_v1.json",
        project/"configs/gate_f3_inflight_closure_repair_v1.json",
        project/"configs/gate_f3_b4_decision_hash_reuse_overlay_v1.json",
    )
    cursor = frozen_hash
    for path in paths:
        overlay = _valid_overlay(project, path)
        if overlay is None:
            return False
        parent = overlay.get("parent_code_hashes", {}).get(name)
        optimized = overlay.get("optimized_code_hashes", {}).get(name)
        if parent is None and optimized is None:
            continue
        if parent != cursor or optimized is None:
            return False
        if _sha(project/name) != current_hash and optimized == current_hash:
            return False
        cursor = optimized
    if cursor == current_hash:
        return True
    from dynamic_lisl.b4_runtime_seal import approved_production_file_successor
    return approved_production_file_successor(project,name,cursor,current_hash)
