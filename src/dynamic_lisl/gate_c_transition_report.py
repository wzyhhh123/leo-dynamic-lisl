"""Stable Gate C summary of transition consequences from the frozen profiler."""
from __future__ import annotations


def summarize_transition_consequence(profile):
    log = profile.get("transition_log", [])
    reserve = next((item for item in log if item["event"] == "RESERVE_BOTH"), None)
    link_up = next((item for item in log if item["event"] == "LINK_UP"), None)
    link_downs = [item for item in log if item["event"] == "LINK_DOWN"]
    if reserve is None:
        mode = "HOLD_OR_EXPIRY_ONLY"
    elif link_downs and link_up and min(item["time"] for item in link_downs) < link_up["time"]:
        mode = "BBM"
    elif link_up and link_downs:
        mode = "MBB"
    else:
        mode = "SETUP_ONLY"
    episodes = profile.get("episodes", [])
    first = episodes[0] if episodes else None
    active_counts = [len(item["active_components"]) for item in profile.get("timeline", [])]
    admit_counts = [len(item["admit_components"]) for item in profile.get("timeline", [])]
    return {
        "transition_mode": mode,
        "ready_time": reserve["details"].get("predicted_ready") if reserve else None,
        "link_up_time": link_up["time"] if link_up else None,
        "old_link_down_time": min((item["time"] for item in link_downs), default=None),
        "outage_occurs": bool(episodes),
        "outage_start": first["start_s"] if first else None,
        "outage_end": episodes[-1]["end_s"] if episodes else None,
        "outage_duration": profile.get("outage_duration"),
        "partition_occurs": profile.get("partition_occurs", False),
        "recovery_time": profile.get("recovery_time"),
        "active_graph_component_count": max(active_counts, default=1),
        "admit_graph_component_count": max(admit_counts, default=1),
        "classification": profile.get("classification"),
    }
