"""Explicit regression for all three bilateral FoR rejection codes."""
import unittest

import numpy as np

from dynamic_lisl.gate_c_terminal_geometry import TerminalGeometryConfig, bilateral_for


class GateCFoRReasonTests(unittest.TestCase):
    def test_local_remote_and_bilateral_reasons_are_distinct(self):
        config = TerminalGeometryConfig.from_dict({
            "terminal_mounting_rtn": {"D1": [0, 0, 1], "D2": [0, 0, -1]},
            "for_half_angle_deg": {"D1": 2.0, "D2": 2.0},
        })
        pa = np.array([7000.0, 0.0, 0.0]); va = np.array([0.0, 7.5, 0.0])
        pb = np.array([7000.0, 0.0, 100.0]); vb = np.array([0.0, 7.5, 0.0])
        self.assertEqual(bilateral_for(pa, va, "D2", pb, vb, "D2", config)["reason"],
                         "FOR_FAIL_LOCAL")
        self.assertEqual(bilateral_for(pa, va, "D1", pb, vb, "D1", config)["reason"],
                         "FOR_FAIL_REMOTE")
        self.assertEqual(bilateral_for(pa, va, "D2", pb, vb, "D1", config)["reason"],
                         "FOR_FAIL_BILATERAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
