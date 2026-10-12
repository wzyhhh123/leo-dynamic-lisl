"""Gate C0: continuous visibility as the only geometry input to Gate B."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path

from .terminal_executor import Connect


@dataclass(frozen=True)
class VisibilityWindow:
    sat_a: str
    sat_b: str
    start_s: float
    end_s: float
    left_censored: bool = False
    right_censored: bool = False
    distance_km: float | None = None
    plane_gap: int | None = None

    def contains(self, time_s):
        return self.start_s <= time_s < self.end_s

    def to_dict(self):
        return asdict(self)


class VisibilityCatalog:
    """Immutable half-open visibility windows keyed by satellite pair.

    A right-censored end is a prediction horizon, not a physical link expiry.
    The executor still uses it as the conservative validity end of this asset.
    """

    def __init__(self, windows, plane_by_satellite):
        self.plane_by_satellite = dict(plane_by_satellite)
        self.windows = {}
        for window in windows:
            if window.sat_a == window.sat_b:
                raise ValueError("Self visibility window")
            if not window.start_s < window.end_s:
                raise ValueError("Invalid visibility window")
            key = tuple(sorted((window.sat_a, window.sat_b)))
            if key != (window.sat_a, window.sat_b):
                window = VisibilityWindow(key[0], key[1], window.start_s, window.end_s,
                                          window.left_censored, window.right_censored,
                                          window.distance_km, window.plane_gap)
            self.windows.setdefault(key, []).append(window)
        for key, values in self.windows.items():
            values.sort(key=lambda x: (x.start_s, x.end_s))
            if any(a.end_s > b.start_s for a, b in zip(values, values[1:])):
                raise ValueError("Overlapping visibility windows for %r" % (key,))

    @classmethod
    def from_records(cls, records, plane_by_satellite):
        return cls((VisibilityWindow(**record) for record in records), plane_by_satellite)

    @classmethod
    def from_gate_a_asset(cls, intervals_path, satellite_ids, plane_ids):
        satellite_ids = list(satellite_ids)
        plane_by_satellite = dict(zip(satellite_ids, plane_ids))
        windows = []
        with Path(intervals_path).open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                i, j = row["i"], row["j"]
                windows.append(VisibilityWindow(
                    satellite_ids[i], satellite_ids[j], row["start_s"], row["end_s"],
                    row.get("left_censored", False), row.get("right_censored", False),
                    row.get("distance_mean_sampled_km"), row.get("plane_gap")))
        return cls(windows, plane_by_satellite)

    def current_window(self, sat_a, sat_b, time_s, inter_plane_only=True):
        if sat_a not in self.plane_by_satellite or sat_b not in self.plane_by_satellite:
            return None
        if inter_plane_only and self.plane_by_satellite[sat_a] == self.plane_by_satellite[sat_b]:
            return None
        for window in self.windows.get(tuple(sorted((sat_a, sat_b))), ()):
            if window.contains(time_s):
                return window
        return None

    def inter_plane_candidates(self, time_s, allowed_satellites=None):
        allowed = None if allowed_satellites is None else set(allowed_satellites)
        result = []
        for (a, b), windows in sorted(self.windows.items()):
            if allowed is not None and (a not in allowed or b not in allowed):
                continue
            if self.plane_by_satellite[a] == self.plane_by_satellite[b]:
                continue
            window = next((w for w in windows if w.contains(time_s)), None)
            if window:
                result.append(window)
        return result

    def terminal_pair_candidates(self, executor, time_s):
        result = []
        for window in self.inter_plane_candidates(time_s, executor.satellite_ids):
            for da in ("D1", "D2"):
                for db in ("D1", "D2"):
                    result.append(((window.sat_a, da), (window.sat_b, db), window))
        return result

    def connect_command(self, executor, a, b, retarget_a, retarget_b, acquisition,
                        orientation_a=(0.0, 1.0, 0.0),
                        orientation_b=(0.0, 1.0, 0.0), release_after=()):
        """Create a Gate B command only while geometry is currently valid."""
        a, b = tuple(a), tuple(b)
        window = self.current_window(a[0], b[0], executor.now)
        if window is None:
            raise ValueError("NOT_VISIBLE")
        command = Connect(a, b, window.end_s, retarget_a, retarget_b, acquisition,
                          orientation_a, orientation_b, tuple(release_after))
        # Gate B is authoritative for drain-aware ready time and reservations.
        # Submit to a clone so this method cannot partially change the executor.
        from copy import deepcopy
        trial = deepcopy(executor)
        try:
            trial.submit([command])
        except ValueError as error:
            message = str(error)
            if "strictly precede" in message:
                raise ValueError("INSUFFICIENT_LIFETIME") from error
            raise
        # One or both endpoints can still be DRAINING; the Gate B reservation log
        # is the authoritative drain-aware ready prediction.
        ready = next(x["details"]["predicted_ready"] for x in reversed(trial.log)
                     if x["event"] == "RESERVE_BOTH")
        if not ready < window.end_s:
            raise ValueError("INSUFFICIENT_LIFETIME")
        return command, dict(window=window.to_dict(), ready_time=ready,
                             remaining_lifetime_s=window.end_s-executor.now,
                             usable_lifetime_s=window.end_s-ready,
                             end_semantics=("prediction_horizon" if window.right_censored
                                            else "natural_visibility_expiry"))

