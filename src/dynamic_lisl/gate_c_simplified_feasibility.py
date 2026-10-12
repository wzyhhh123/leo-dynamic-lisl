"""Gate C simplified terminal-pair feasibility adapter.

The Gate B executor remains authoritative for reservations, draining and setup.
This adapter only combines a terminal-pair geometry catalog with that executor.
"""
from __future__ import annotations


class TerminalPairPhysicalFeasibility:
    def __init__(self, catalog, hardware=None):
        self.catalog = catalog
        self.hardware = hardware

    def evaluate(self, executor, a, b, retarget_a=1.0, retarget_b=1.0,
                 acquisition=1.0, release_after=(), orientation_a=(0.0, 1.0, 0.0),
                 orientation_b=(0.0, 1.0, 0.0)):
        a, b = tuple(a), tuple(b)
        if a not in executor.terminals or b not in executor.terminals:
            return {"accepted": False, "reason": "UNKNOWN_DYNAMIC_TERMINAL", "command": None}
        window = self.catalog.current_window(a, b, executor.now)
        if window is None:
            return {
                "accepted": False,
                "reason": self.catalog.diagnose(a, b, executor.now) or "NOT_VISIBLE",
                "command": None,
            }
        if self.hardware is not None:
            reason = self.hardware.check({
                "window": window,
                "executor": executor,
                "terminals": (a, b),
                "time_s": executor.now,
            })
            if reason:
                return {"accepted": False, "reason": reason, "command": None}
        try:
            command, geometry = self.catalog.connect_command(
                executor, a, b, retarget_a, retarget_b, acquisition,
                orientation_a, orientation_b, release_after,
            )
        except ValueError as error:
            message = str(error)
            mapping = {
                "INSUFFICIENT_LIFETIME": "INSUFFICIENT_LIFETIME",
                "Terminal busy or reserved": "RESERVATION_CONFLICT",
                "MBB requires": "TERMINAL_BUSY",
                "Parallel pending": "RESERVATION_CONFLICT",
                "Use KEEP": "DUPLICATE_LINK",
                "FOR_FAIL_LOCAL": "FOR_FAIL_LOCAL",
                "FOR_FAIL_REMOTE": "FOR_FAIL_REMOTE",
                "FOR_FAIL_BILATERAL": "FOR_FAIL_BILATERAL",
                "NOT_VISIBLE": "NOT_VISIBLE",
            }
            reason = next((value for key, value in mapping.items() if key in message),
                          "SETUP_NOT_COMPLETABLE")
            return {"accepted": False, "reason": reason, "command": None, "detail": message}
        return {
            "accepted": True,
            "reason": None,
            "command": command,
            "geometry": geometry,
            "hardware_calibration": (
                self.hardware.calibration_status if self.hardware is not None else "PARAMETRIC"
            ),
        }
