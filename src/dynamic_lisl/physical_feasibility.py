"""Gate C2/C5 physical and terminal feasibility; no network policy decisions."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from copy import deepcopy


@dataclass(frozen=True)
class HardwareParameter:
    parameter: str
    value: object
    unit: str
    source: str
    status: str
    notes: str = ""

    def to_dict(self):
        return asdict(self)


class HardwareContract:
    STATUSES = {"literature_calibrated", "provisional", "sensitivity_only", "unresolved"}

    def __init__(self, parameters=(), range_check=None, fov_check=None, tracking_check=None):
        self.parameters = {p.parameter: p for p in parameters}
        if any(p.status not in self.STATUSES for p in parameters):
            raise ValueError("Unknown hardware parameter status")
        self.range_check = range_check
        self.fov_check = fov_check
        self.tracking_check = tracking_check

    @property
    def calibration_status(self):
        return ("CALIBRATED" if self.parameters and
                all(p.status == "literature_calibrated" for p in self.parameters.values())
                else "PENDING")

    def check(self, context):
        checks = (("HARDWARE_RANGE_FAIL", self.range_check),
                  ("FOV_FAIL", self.fov_check),
                  ("TRACKING_FAIL", self.tracking_check))
        for reason, callback in checks:
            if callback is not None and not callback(context):
                return reason
        return None

    def to_dict(self):
        return dict(calibration_status=self.calibration_status,
                    parameters=[p.to_dict() for p in self.parameters.values()])


def provisional_hardware_fixture(max_range_km=None):
    """Test interface fixture. 5000 km is deliberately not copied here."""
    parameters = [
        HardwareParameter("hardware_max_lisl_range", max_range_km, "km", "unfrozen",
                          "provisional" if max_range_km is not None else "unresolved",
                          "Independent from the Gate A 5000 km diagnostic cutoff"),
        HardwareParameter("terminal_mounting_body_frame", None, "frame", "unfrozen",
                          "unresolved"),
        HardwareParameter("field_of_view", None, "deg", "unfrozen", "unresolved"),
        HardwareParameter("slew_rate", None, "deg/s", "unfrozen", "unresolved"),
        HardwareParameter("slew_acceleration", None, "deg/s^2", "unfrozen", "unresolved"),
        HardwareParameter("tracking_angular_rate", None, "deg/s", "unfrozen", "unresolved"),
        HardwareParameter("tracking_angular_acceleration", None, "deg/s^2", "unfrozen", "unresolved"),
        HardwareParameter("acquisition_time", None, "s", "synthetic Gate C fixture", "provisional"),
        HardwareParameter("pointing_keep_out", None, "deg", "unfrozen", "unresolved"),
    ]
    def range_check(context):
        distance = context["window"].distance_km
        return max_range_km is None or distance is None or distance <= max_range_km
    return HardwareContract(parameters, range_check=range_check)


class PhysicalFeasibility:
    """Return a command or one machine-readable physical rejection reason."""
    def __init__(self, catalog, hardware):
        self.catalog = catalog
        self.hardware = hardware

    def evaluate(self, executor, a, b, retarget_a=1.0, retarget_b=1.0,
                 acquisition=1.0, release_after=(), orientation_a=(0.0, 1.0, 0.0),
                 orientation_b=(0.0, 1.0, 0.0)):
        a, b = tuple(a), tuple(b)
        if a not in executor.terminals or b not in executor.terminals:
            return dict(accepted=False, reason="TERMINAL_BUSY", command=None)
        window = self.catalog.current_window(a[0], b[0], executor.now)
        if window is None:
            return dict(accepted=False, reason="NOT_VISIBLE", command=None)
        hardware_reason = self.hardware.check(dict(window=window, executor=executor,
                                                   terminals=(a, b), time_s=executor.now))
        if hardware_reason:
            return dict(accepted=False, reason=hardware_reason, command=None)
        try:
            command, geometry = self.catalog.connect_command(
                executor, a, b, retarget_a, retarget_b, acquisition,
                orientation_a, orientation_b, release_after)
        except ValueError as error:
            message = str(error)
            mapping = {
                "NOT_VISIBLE": "NOT_VISIBLE",
                "INSUFFICIENT_LIFETIME": "INSUFFICIENT_LIFETIME",
                "Terminal busy or reserved": "RESERVATION_CONFLICT",
                "MBB requires": "TERMINAL_BUSY",
                "Parallel pending": "RESERVATION_CONFLICT",
                "Use KEEP": "DUPLICATE_LINK",
            }
            reason = next((value for key, value in mapping.items() if key in message),
                          "SETUP_NOT_COMPLETABLE")
            return dict(accepted=False, reason=reason, command=None, detail=message)
        return dict(accepted=True, reason=None, command=command, geometry=geometry,
                    hardware_calibration=self.hardware.calibration_status)


def allocate_terminal_pairs(executor, satellite_pairs, allowed_satellites=None):
    """Deterministic order-invariant allocator for idle terminal pairs.

    This is a resource allocator, not matching or topology optimization.
    """
    allowed = set(executor.satellite_ids if allowed_satellites is None else allowed_satellites)
    normalized = sorted(set(tuple(sorted(x)) for x in satellite_pairs))
    if any(a not in allowed or b not in allowed for a, b in normalized):
        raise ValueError("SUBSET_EXTERNAL_SATELLITE")
    used = set()
    result = []
    for a, b in normalized:
        choices_a = [(a, d) for d in ("D1", "D2")
                     if executor.terminals[(a, d)].phase == "IDLE"
                     and executor.terminals[(a, d)].reservation_id is None
                     and (a, d) not in used]
        choices_b = [(b, d) for d in ("D1", "D2")
                     if executor.terminals[(b, d)].phase == "IDLE"
                     and executor.terminals[(b, d)].reservation_id is None
                     and (b, d) not in used]
        if not choices_a or not choices_b:
            raise ValueError("TERMINAL_BUSY")
        pair = (choices_a[0], choices_b[0])
        used.update(pair)
        result.append(pair)
    return result
