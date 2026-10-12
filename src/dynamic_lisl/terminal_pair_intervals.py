"""Refine satellite visibility into bilateral terminal-pair FoR intervals."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
import math

import numpy as np
from scipy.optimize import brentq

from .gate_c_terminal_geometry import bilateral_for, bilateral_for_margin
from .terminal_executor import Connect


@dataclass(frozen=True)
class TerminalPairWindow:
    sat_a: str
    terminal_a: str
    sat_b: str
    terminal_b: str
    start_s: float
    end_s: float
    left_censored: bool = False
    right_censored: bool = False
    parent_start_s: float | None = None
    parent_end_s: float | None = None
    plane_gap: int | None = None
    distance_km: float | None = None

    @property
    def endpoint_a(self):
        return self.sat_a, self.terminal_a

    @property
    def endpoint_b(self):
        return self.sat_b, self.terminal_b

    def contains(self, time_s):
        return self.start_s <= time_s < self.end_s

    def to_dict(self):
        return asdict(self)


def _time_grid(start_s, end_s, step_s):
    count = int(math.floor((end_s - start_s) / step_s))
    values = start_s + np.arange(count + 1, dtype=float) * step_s
    if end_s - values[-1] > 1e-12:
        values = np.append(values, end_s)
    else:
        values[-1] = end_s
    if len(values) == 2 and end_s-start_s > 1e-9:
        values = np.array([start_s, (start_s+end_s)/2.0, end_s])
    return values


def _intervals_from_samples(margin, grid, values, time_tolerance_s, epsilon):
    cuts = [float(grid[0]), float(grid[-1])]
    for left, right, f_left, f_right in zip(grid[:-1], grid[1:], values[:-1], values[1:]):
        if abs(f_left) <= epsilon:
            cuts.append(float(left))
        if f_left * f_right < 0.0:
            cuts.append(float(brentq(margin, float(left), float(right), xtol=time_tolerance_s)))
    if abs(values[-1]) <= epsilon:
        cuts.append(float(grid[-1]))
    cuts = sorted(set(cuts))
    intervals = []
    for left, right in zip(cuts[:-1], cuts[1:]):
        if right-left <= time_tolerance_s/10.0:
            continue
        if float(margin((left+right)/2.0)) >= -epsilon:
            if intervals and abs(intervals[-1][1]-left) <= time_tolerance_s:
                intervals[-1] = (intervals[-1][0], right)
            else:
                intervals.append((left, right))
    return intervals


def positive_intervals(margin, start_s, end_s, scan_step_s=2.0,
                       time_tolerance_s=1e-3, epsilon=1e-10):
    """Numerically find maximal half-open intervals where margin >= 0."""
    if not (math.isfinite(start_s) and math.isfinite(end_s) and start_s < end_s):
        raise ValueError("Invalid parent interval")
    if scan_step_s <= 0 or time_tolerance_s <= 0:
        raise ValueError("Positive scan step and tolerance required")
    grid = _time_grid(start_s, end_s, scan_step_s)
    values = np.asarray([float(margin(t)) for t in grid], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite FoR margin")
    return _intervals_from_samples(margin, grid, values, time_tolerance_s, epsilon)


def _pair_margin(model, sat_a, terminal_a, sat_b, terminal_b, config):
    def margin(time_s):
        position, velocity = model.state(np.atleast_1d(np.asarray(time_s, dtype=float)), (sat_a, sat_b))
        value = bilateral_for_margin(
            position[:, 0], velocity[:, 0], terminal_a,
            position[:, 1], velocity[:, 1], terminal_b, config,
        )
        return float(value[0]) if np.ndim(time_s) == 0 else value
    return margin


def refine_terminal_pair_windows(model, satellite_catalog, config, allowed_satellites=None,
                                 scan_step_s=2.0, time_tolerance_s=1e-3):
    """Expand every parent satellite window into four terminal-pair windows.

    SGP4 states are evaluated once per parent interval and shared by the four
    terminal combinations. Only sign-changing roots call SGP4 again.
    """
    allowed = None if allowed_satellites is None else set(allowed_satellites)
    result = []
    for (sat_a, sat_b), parents in sorted(satellite_catalog.windows.items()):
        if allowed is not None and (sat_a not in allowed or sat_b not in allowed):
            continue
        if satellite_catalog.plane_by_satellite[sat_a] == satellite_catalog.plane_by_satellite[sat_b]:
            continue
        for parent in parents:
            grid = _time_grid(parent.start_s, parent.end_s, scan_step_s)
            position, velocity = model.state(grid, (sat_a, sat_b))
            for terminal_a in ("D1", "D2"):
                for terminal_b in ("D1", "D2"):
                    margin = _pair_margin(model, sat_a, terminal_a, sat_b, terminal_b, config)
                    sampled = bilateral_for_margin(
                        position[:, 0], velocity[:, 0], terminal_a,
                        position[:, 1], velocity[:, 1], terminal_b, config,
                    )
                    intervals = _intervals_from_samples(
                        margin, grid, np.asarray(sampled), time_tolerance_s, 1e-10
                    )
                    for start_s, end_s in intervals:
                        result.append(TerminalPairWindow(
                            sat_a, terminal_a, sat_b, terminal_b, start_s, end_s,
                            parent.left_censored and abs(start_s-parent.start_s) <= time_tolerance_s,
                            parent.right_censored and abs(end_s-parent.end_s) <= time_tolerance_s,
                            parent.start_s, parent.end_s, parent.plane_gap, parent.distance_km,
                        ))
    return result


class TerminalPairCatalog:
    """Half-open terminal-pair windows with optional live FoR diagnostics."""
    def __init__(self, windows, plane_by_satellite, parent_catalog=None, model=None, config=None):
        self.plane_by_satellite = dict(plane_by_satellite)
        self.parent_catalog = parent_catalog
        self.model = model
        self.config = config
        self.windows = {}
        for window in windows:
            if window.endpoint_a == window.endpoint_b or not window.start_s < window.end_s:
                raise ValueError("Invalid terminal-pair window")
            key = self._key(window.endpoint_a, window.endpoint_b)
            self.windows.setdefault(key, []).append(window)
        for values in self.windows.values():
            values.sort(key=lambda value: (value.start_s, value.end_s))
            if any(a.end_s > b.start_s for a, b in zip(values, values[1:])):
                raise ValueError("Overlapping terminal-pair windows")

    @staticmethod
    def _key(a, b):
        return tuple(sorted((tuple(a), tuple(b))))

    @classmethod
    def from_records(cls, records, plane_by_satellite, **kwargs):
        return cls((TerminalPairWindow(**record) for record in records), plane_by_satellite, **kwargs)

    def current_window(self, a, b, time_s):
        for window in self.windows.get(self._key(a, b), ()):
            if window.contains(time_s):
                return window
        return None

    def terminal_pair_candidates(self, time_s, allowed_satellites=None):
        allowed = None if allowed_satellites is None else set(allowed_satellites)
        result = []
        for values in self.windows.values():
            window = next((item for item in values if item.contains(time_s)), None)
            if window is None:
                continue
            if allowed is not None and (window.sat_a not in allowed or window.sat_b not in allowed):
                continue
            result.append(window)
        return sorted(result, key=lambda value: (
            value.sat_a, value.terminal_a, value.sat_b, value.terminal_b
        ))

    def diagnose(self, a, b, time_s):
        if self.parent_catalog is None or self.model is None or self.config is None:
            return "FOR_FAIL_BILATERAL"
        parent = self.parent_catalog.current_window(a[0], b[0], time_s)
        if parent is None:
            return "NOT_VISIBLE"
        position, velocity = self.model.state(np.array([time_s]), (a[0], b[0]))
        return bilateral_for(
            position[0, 0], velocity[0, 0], a[1],
            position[0, 1], velocity[0, 1], b[1], self.config,
        )["reason"]

    def connect_command(self, executor, a, b, retarget_a, retarget_b, acquisition,
                        orientation_a=(0.0, 1.0, 0.0),
                        orientation_b=(0.0, 1.0, 0.0), release_after=(),
                        numerical_epsilon_s=1e-9):
        a, b = tuple(a), tuple(b)
        window = self.current_window(a, b, executor.now)
        if window is None:
            raise ValueError(self.diagnose(a, b, executor.now) or "NOT_VISIBLE")
        command = Connect(a, b, window.end_s, retarget_a, retarget_b, acquisition,
                          orientation_a, orientation_b, tuple(release_after))
        trial = deepcopy(executor)
        try:
            trial.submit([command])
        except ValueError as error:
            if "strictly precede" in str(error):
                raise ValueError("INSUFFICIENT_LIFETIME") from error
            raise
        ready = next(item["details"]["predicted_ready"] for item in reversed(trial.log)
                     if item["event"] == "RESERVE_BOTH")
        usable = window.end_s-ready
        if usable <= numerical_epsilon_s:
            raise ValueError("INSUFFICIENT_LIFETIME")
        return command, {
            "window": window.to_dict(), "ready_time": ready,
            "remaining_lifetime_s": window.end_s-executor.now,
            "usable_lifetime_s": usable,
            "end_semantics": "prediction_horizon" if window.right_censored else "terminal_pair_for_expiry",
        }
