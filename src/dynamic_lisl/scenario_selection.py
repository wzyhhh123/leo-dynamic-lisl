"""Result-blind deterministic scenario selection for the frozen Gate E contract."""
from __future__ import annotations


SCENARIO_CLASSES = (
    "E-A_BBM_NO_ROUTE", "E-B_BBM_CONNECTED_REROUTE",
    "E-C_GENUINE_MBB", "E-D_SHARED_CONGESTION_EXTERNALITY",
)
KAPPA2_BINS = (
    ("low", 0.0, 0.1), ("medium", 0.1, 0.35),
    ("high", 0.35, 0.7), ("very_high", 0.7, 1.0),
)
FORBIDDEN_RESULT_KEYS = {
    "j_hold", "j_switch", "j_real", "j_ideal", "delta_j", "relative_effect",
    "mean_delay", "delivery_ratio", "reversal", "performance_score",
}
REQUIRED_KEYS = {
    "scenario_id", "scenario_class", "t0_s", "old_edge", "new_edge",
    "terminal_ids", "gate_c_legal", "kappa2",
}
OPTIONAL_STRUCTURAL_KEYS = {
    "transition_type", "connected_during_transition", "remaining_lifetime_s",
    "terminal_occupancy", "hop_difference", "path_difference", "shared_edges",
    "has_third_party_od", "focus_commodities",
}


def kappa2_bin(value):
    value = float(value)
    for name, left, right in KAPPA2_BINS:
        inside = left < value < right if name == "very_high" else left < value <= right
        if inside:
            return name
    return None


def _edge(value):
    return tuple(sorted(tuple(value)))


def _terminal_ids(value):
    return tuple(sorted(tuple(tuple(x) for x in value)))


def validate_result_blind_candidate(candidate):
    lowered = {str(key).lower() for key in candidate}
    forbidden = sorted(lowered & FORBIDDEN_RESULT_KEYS)
    if forbidden:
        raise ValueError("RESULT_FIELD_FORBIDDEN_IN_SCENARIO_SELECTION:"+",".join(forbidden))
    missing = sorted(REQUIRED_KEYS-set(candidate))
    if missing:
        raise ValueError("SCENARIO_SELECTION_FIELD_MISSING:"+",".join(missing))
    unknown = sorted(set(candidate)-REQUIRED_KEYS-OPTIONAL_STRUCTURAL_KEYS)
    if unknown:
        raise ValueError("NONSTRUCTURAL_SELECTION_FIELD_FORBIDDEN:"+",".join(unknown))
    if candidate["scenario_class"] not in SCENARIO_CLASSES:
        raise ValueError("UNKNOWN_SCENARIO_CLASS")
    if not candidate["gate_c_legal"]:
        return False
    if kappa2_bin(candidate["kappa2"]) is None:
        return False
    return True


def deterministic_select(candidates, quota_per_class_bin=1):
    """Select lexicographically first legal cases without reading outcomes."""
    quota = int(quota_per_class_bin)
    if quota <= 0:
        raise ValueError("POSITIVE_SCENARIO_QUOTA_REQUIRED")
    eligible = []
    for candidate in candidates:
        if validate_result_blind_candidate(candidate):
            item = dict(candidate)
            item["kappa2_bin"] = kappa2_bin(item["kappa2"])
            eligible.append(item)
    eligible.sort(key=lambda x: (
        float(x["t0_s"]), _edge(x["old_edge"]), _edge(x["new_edge"]),
        _terminal_ids(x["terminal_ids"]), str(x["scenario_id"])))
    selected = []
    availability = []
    for scenario_class in SCENARIO_CLASSES:
        for bin_name, _, _ in KAPPA2_BINS:
            group = [x for x in eligible if x["scenario_class"] == scenario_class
                     and x["kappa2_bin"] == bin_name]
            chosen = group[:quota]
            selected.extend(chosen)
            availability.append({
                "scenario_class": scenario_class, "kappa2_bin": bin_name,
                "eligible_count": len(group),
                "selected_ids": [x["scenario_id"] for x in chosen],
                "status": "SELECTED" if chosen else "NO_ELIGIBLE_CASE",
            })
    return {"selected": selected, "availability": availability,
            "ordering": ["t0_s", "old_edge", "new_edge", "terminal_ids", "scenario_id"],
            "result_fields_read": []}


