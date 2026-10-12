"""Gate C v1 terminal geometry: ideal RTN attitude and bilateral conic FoR.

This module deliberately stops at geometric feasibility. It does not model a
PAT controller, gimbal dynamics, jitter, tracking-rate limits, or link budget.
All vectors are expressed in the same instantaneous TEME frame.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _unit(vector, label="vector"):
    value = np.asarray(vector, dtype=float)
    if value.shape[-1] != 3 or not np.isfinite(value).all():
        raise ValueError("%s must be finite (...,3)" % label)
    norm = np.linalg.norm(value, axis=-1, keepdims=True)
    if np.any(norm <= 0.0):
        raise ValueError("%s has zero norm" % label)
    return value/norm


def rtn_basis(position_km, velocity_km_s):
    """Return ideal nadir-pointing (R,T,N) unit axes in the input frame."""
    r = np.asarray(position_km, dtype=float)
    v = np.asarray(velocity_km_s, dtype=float)
    if r.shape != v.shape or r.shape[-1] != 3:
        raise ValueError("Position and velocity must have the same (...,3) shape")
    radial = _unit(r, "position")
    normal = _unit(np.cross(r, v), "orbit normal")
    transverse = _unit(np.cross(normal, radial), "transverse")
    return radial, transverse, normal


def validate_rtn(position_km, velocity_km_s, tolerance=1e-12):
    radial, transverse, normal = rtn_basis(position_km, velocity_km_s)
    dots = (np.sum(radial*transverse, axis=-1), np.sum(transverse*normal, axis=-1),
            np.sum(normal*radial, axis=-1))
    handed = np.sum(np.cross(radial, transverse)*normal, axis=-1)
    orthogonality = max(float(np.max(np.abs(value))) for value in dots)
    handed_error = float(np.max(np.abs(handed-1.0)))
    return {"passed": orthogonality <= tolerance and handed_error <= tolerance,
            "max_abs_orthogonality_error": orthogonality,
            "max_abs_right_handed_error": handed_error}


def mounting_boresight(position_km, velocity_km_s, mounting_rtn):
    """Transform a configured [R,T,N] mounting vector into TEME."""
    mount = _unit(np.asarray(mounting_rtn, dtype=float), "mounting_rtn")
    if mount.shape != (3,):
        raise ValueError("A terminal mounting must be one [R,T,N] vector")
    radial, transverse, normal = rtn_basis(position_km, velocity_km_s)
    return _unit(mount[0]*radial + mount[1]*transverse + mount[2]*normal,
                 "TEME boresight")


def angle_deg(a, b):
    a = _unit(a, "angle vector a")
    b = _unit(b, "angle vector b")
    return np.degrees(np.arccos(np.clip(np.sum(a*b, axis=-1), -1.0, 1.0)))


def conic_for_pass(boresight, line_of_sight, half_angle_deg, epsilon_deg=1e-10):
    if not math.isfinite(half_angle_deg) or not 0.0 < half_angle_deg <= 180.0:
        raise ValueError("FoR half-angle must be in (0,180] degrees")
    angle = angle_deg(boresight, line_of_sight)
    return np.asarray(angle <= half_angle_deg+epsilon_deg), angle


@dataclass(frozen=True)
class TerminalGeometryConfig:
    mountings_rtn: dict
    for_half_angle_deg: dict
    numerical_epsilon_deg: float = 1e-10

    @classmethod
    def from_dict(cls, data):
        mountings = data["terminal_mounting_rtn"]
        half_angles = data["for_half_angle_deg"]
        for terminal in ("D1", "D2"):
            if terminal not in mountings or terminal not in half_angles:
                raise ValueError("D1 and D2 mounting/FoR entries are required")
            vector = np.asarray(mountings[terminal], dtype=float)
            if vector.shape != (3,) or abs(np.linalg.norm(vector)-1.0) > 1e-12:
                raise ValueError("Terminal mounting must be a unit RTN vector")
        return cls({key: tuple(value) for key, value in mountings.items()},
                   {key: float(value) for key, value in half_angles.items()},
                   float(data.get("numerical_epsilon_deg", 1e-10)))


def bilateral_for(position_a, velocity_a, terminal_a, position_b, velocity_b,
                  terminal_b, config):
    """Evaluate scalar states and return a machine-readable rejection reason."""
    if terminal_a not in config.mountings_rtn or terminal_b not in config.mountings_rtn:
        raise ValueError("Unknown dynamic terminal mounting")
    displacement = np.asarray(position_b, dtype=float)-np.asarray(position_a, dtype=float)
    u_ab = _unit(displacement, "line of sight")
    bore_a = mounting_boresight(position_a, velocity_a, config.mountings_rtn[terminal_a])
    bore_b = mounting_boresight(position_b, velocity_b, config.mountings_rtn[terminal_b])
    local_pass, local_angle = conic_for_pass(
        bore_a, u_ab, config.for_half_angle_deg[terminal_a], config.numerical_epsilon_deg)
    remote_pass, remote_angle = conic_for_pass(
        bore_b, -u_ab, config.for_half_angle_deg[terminal_b], config.numerical_epsilon_deg)
    local_value = bool(np.asarray(local_pass).item())
    remote_value = bool(np.asarray(remote_pass).item())
    reason = (None if local_value and remote_value else
              "FOR_FAIL_BILATERAL" if not local_value and not remote_value else
              "FOR_FAIL_LOCAL" if not local_value else "FOR_FAIL_REMOTE")
    return {"feasible": reason is None, "reason": reason,
            "local_angle_deg": float(np.asarray(local_angle).item()),
            "remote_angle_deg": float(np.asarray(remote_angle).item()),
            "local_half_angle_deg": config.for_half_angle_deg[terminal_a],
            "remote_half_angle_deg": config.for_half_angle_deg[terminal_b],
            "local_boresight_teme": np.asarray(bore_a).tolist(),
            "remote_boresight_teme": np.asarray(bore_b).tolist()}


def bilateral_for_margin(position_a, velocity_a, terminal_a, position_b, velocity_b,
                         terminal_b, config):
    """Vectorized signed angular margin; nonnegative means both ends pass."""
    displacement = np.asarray(position_b, dtype=float)-np.asarray(position_a, dtype=float)
    u_ab = _unit(displacement, "line of sight")
    bore_a = mounting_boresight(position_a, velocity_a, config.mountings_rtn[terminal_a])
    bore_b = mounting_boresight(position_b, velocity_b, config.mountings_rtn[terminal_b])
    local = config.for_half_angle_deg[terminal_a]-angle_deg(bore_a, u_ab)
    remote = config.for_half_angle_deg[terminal_b]-angle_deg(bore_b, -u_ab)
    return np.minimum(local, remote)
