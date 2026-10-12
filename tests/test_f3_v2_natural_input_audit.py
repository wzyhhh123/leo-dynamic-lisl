"""Read-only provenance validator controls; no solver/controller execution."""
import copy
import tempfile
import unittest
from pathlib import Path

from audit_f3_v2_natural_inputs import (EPOCH, validate_metadata, validate_windows,
    verify_hashes, digest, local_path, verify_executor_overlay)


def fixture():
    ids = ['X%d_%d' % (p, s) for p in range(18) for s in range(1, 41)]
    meta = dict(frame='TEMEOfDate', propagator='SGP4', gravity='WGS72', epoch_utc=EPOCH,
        position_unit='km', velocity_unit='km/s', distance_unit='km', time_unit='s',
        satellite_count=720, start_s=0., stop_s=600., step_s=30, synthetic_tle=True,
        max_range_km=5000, sat_ids=ids, plane_ids=[p for p in range(18) for _ in range(40)])
    sub = dict(parent_indices=list(range(160)), satellite_ids=ids[:160], plane_ids=[0, 1, 2, 3],
        frame='TEMEOfDate', epoch_utc=EPOCH)
    parent = dict(i=0, j=40, start_s=0., end_s=600., right_censored=True, left_censored=True, plane_gap=1)
    window = dict(sat_a=ids[0], sat_b=ids[40], terminal_a='D2', terminal_b='D1',
        start_s=0., end_s=600., right_censored=True, left_censored=True,
        parent_start_s=0., parent_end_s=600., plane_gap=1, distance_km=1200.)
    return meta, sub, parent, window


class NaturalInputAuditControls(unittest.TestCase):
    def test_exact_mapping_and_half_open_window(self):
        meta, sub, p, w = fixture()
        nodes = validate_metadata(meta, sub)
        cat, stats = validate_windows([w], [p], meta['sat_ids'], nodes, .001)
        self.assertEqual(stats['right_censored_windows'], 1)
        self.assertIsNotNone(cat.current_window(('X0_1', 'D2'), ('X1_1', 'D1'), 570.))
        self.assertIsNone(cat.current_window(('X0_1', 'D2'), ('X1_1', 'D1'), 600.))

    def test_frame_epoch_unit_and_duplicate_id_rejected(self):
        meta, sub, _, _ = fixture()
        for key, value in [('frame', 'J2000'), ('epoch_utc', 'other'), ('position_unit', 'm')]:
            bad = copy.deepcopy(meta); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_metadata(bad, sub)
        bad = copy.deepcopy(meta); bad['sat_ids'][1] = bad['sat_ids'][0]
        with self.assertRaisesRegex(ValueError, 'ID_PLANE'):
            validate_metadata(bad, sub)

    def test_parent_misbinding_rejected(self):
        meta, sub, p, w = fixture(); w['parent_end_s'] = 599.
        with self.assertRaisesRegex(ValueError, 'PARENT_MISMATCH'):
            validate_windows([w], [p], meta['sat_ids'], sub['satellite_ids'], .001)

    def test_right_censor_is_not_natural_expiry(self):
        meta, sub, p, w = fixture(); w['end_s'] = 599.
        with self.assertRaisesRegex(ValueError, 'RIGHT_CENSOR'):
            validate_windows([w], [p], meta['sat_ids'], sub['satellite_ids'], .001)
        w['right_censored'] = False
        _, stats = validate_windows([w], [p], meta['sat_ids'], sub['satellite_ids'], .001)
        self.assertEqual(stats['known_terminal_pair_expiry_windows'], 1)
        self.assertEqual(stats['right_censored_windows'], 0)

    def test_overlap_and_wrong_terminal_rejected(self):
        meta, sub, p, w = fixture()
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            validate_windows([w, copy.deepcopy(w)], [p], meta['sat_ids'], sub['satellite_ids'], .001)
        w['terminal_a'] = 'FIXED'
        with self.assertRaisesRegex(ValueError, 'INVALID_TERMINAL'):
            validate_windows([w], [p], meta['sat_ids'], sub['satellite_ids'], .001)

    def test_subsets_do_not_rename_parent_ids(self):
        meta, sub, _, _ = fixture(); sub['satellite_ids'][0] = 'RENAMED'
        with self.assertRaisesRegex(ValueError, 'SUBSET_ID'):
            validate_metadata(meta, sub)

    def test_nonfinite_window_rejected(self):
        meta, sub, p, w = fixture(); w['end_s'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'INVALID_TERMINAL'):
            validate_windows([w], [p], meta['sat_ids'], sub['satellite_ids'], .001)

    def test_hash_and_path_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); p = root / 'asset'; p.write_bytes(b'original')
            self.assertEqual(verify_hashes(root, {'asset': digest(p)}), 1)
            with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
                verify_hashes(root, {'asset': '0' * 64})
            for rel in ('../asset', 'C:/asset', '/asset', '..\\asset'):
                with self.subTest(path=rel), self.assertRaises(ValueError):
                    local_path(root, rel)

    def test_frozen_executor_exact_and_unregistered_successor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); p = root / 'src/dynamic_lisl/terminal_executor.py'
            p.parent.mkdir(parents=True); p.write_bytes(b'frozen')
            baseline = {'src/dynamic_lisl/terminal_executor.py': digest(p)}
            self.assertEqual(verify_executor_overlay(root, baseline, {})['classification'], 'EXACT_FROZEN_EXECUTOR')
            p.write_bytes(b'not-authorized')
            with self.assertRaises((ValueError, KeyError)):
                verify_executor_overlay(root, baseline, {})


if __name__ == '__main__':
    unittest.main()
