"""Derive Gate F1 transition and post-expiry no-route metrics from D2 logs."""
from __future__ import annotations


def _merge(intervals):
    result = []
    for start, end in sorted((float(a), float(b)) for a, b in intervals if b > a):
        if result and start <= result[-1][1]+1e-12:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def _intersection_duration(interval, windows):
    a, b = interval
    return sum(max(0.0, min(b, d)-max(a, c)) for c, d in windows)


def _no_route_intervals(result, end_s):
    by_commodity = {}
    events = {}
    for row in result.get("route_state_events", ()):
        events.setdefault(row["commodity_id"], []).append(row)
    for key, rows in events.items():
        state = None
        start = None
        intervals = []
        for row in sorted(rows, key=lambda x: float(x["time_s"])):
            new = row["new_state"]
            now = float(row["time_s"])
            if new == "NO_ROUTE_TEMPORARY" and state != "NO_ROUTE_TEMPORARY":
                start = now
            elif state == "NO_ROUTE_TEMPORARY" and new == "ROUTED" and start is not None:
                intervals.append((start, now))
                start = None
            state = new
        if state == "NO_ROUTE_TEMPORARY" and start is not None:
            intervals.append((start, float(end_s)))
        by_commodity[key] = _merge(intervals)
    return by_commodity


def derive_separated_outage_metrics(result):
    """Partition no-route time without altering simulated dynamics.

    Transition time is the union of Gate B reservation/retarget/acquisition
    episodes.  Post-expiry time begins at a natural LINK_EXPIRE down event and
    is counted only outside transition episodes, preventing double counting.
    """
    end_s = float(result["metrics"]["evaluation_end_s"])
    transition = _merge((row["start_s"], row["end_s"])
                        for row in result.get("transition_episodes", ())
                        if row.get("end_s") is not None)
    expiries = sorted(float(row["time"])
                      for row in result.get("terminal_event_sequence", ())
                      if row["event"] == "LINK_DOWN"
                      and row.get("details", {}).get("reason") == "LINK_EXPIRE")
    by_commodity = _no_route_intervals(result, end_s)
    transition_by = {}
    post_by = {}
    for key, intervals in sorted(by_commodity.items()):
        transition_value = sum(_intersection_duration(interval, transition)
                               for interval in intervals)
        post_value = 0.0
        for interval in intervals:
            relevant = [value for value in expiries if value < interval[1]-1e-12]
            if not relevant:
                continue
            post_window = (max(interval[0], min(relevant)), interval[1])
            total = max(0.0, post_window[1]-post_window[0])
            post_value += max(0.0, total-_intersection_duration(post_window, transition))
        if transition_value > 1e-12:
            transition_by[key] = transition_value
        if post_value > 1e-12:
            post_by[key] = post_value
    return {
        "transition_period_outage_s": max(transition_by.values(), default=0.0),
        "transition_period_no_route_by_commodity_s": transition_by,
        "post_expiry_no_route_s": max(post_by.values(), default=0.0),
        "post_expiry_no_route_by_commodity_s": post_by,
        "forced_outage_duration": result["metrics"].get("outage_duration_s", 0.0),
        "forced_outage_duration_role": "DIAGNOSTIC_ONLY",
        "double_counting_forbidden": True,
    }
