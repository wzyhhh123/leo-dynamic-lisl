"""Offline J2000 ephemeris reader; no STK or legacy executor dependency."""
import json
import math
from pathlib import Path
import numpy as np
from .common import EPOCH


def time_grid(duration, step):
    if not np.isfinite([duration, step]).all() or duration <= 0 or step <= 0:
        raise ValueError('Positive finite duration and step required')
    t = np.arange(int(math.floor(duration / step)) + 1, dtype=float) * step
    if duration - t[-1] > 1e-9:
        t = np.append(t, duration)
    else:
        t[-1] = duration
    return t


class Ephemeris:
    def __init__(self, times, ids, positions, velocities, metadata):
        self.time_s = np.asarray(times, dtype=float)
        self.sat_ids = np.asarray(ids, dtype=str)
        self.position_km = np.asarray(positions, dtype=float)
        self.velocity_km_s = np.asarray(velocities, dtype=float)
        self.metadata = metadata
        t, ids = self.time_s, self.sat_ids
        if t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
            raise ValueError('Invalid time axis')
        if ids.ndim != 1 or not len(ids) or len(set(ids)) != len(ids) or any(not s for s in ids):
            raise ValueError('Invalid satellite IDs')
        for data in (self.position_km, self.velocity_km_s):
            if data.shape != (len(t), len(ids), 3) or not np.isfinite(data).all():
                raise ValueError('Invalid state shape or nonfinite states')
        expected = dict(schema='dynamic_lisl_ephemeris_v2', frame='J2000', position_unit='km', velocity_unit='km/s', time_unit='s', propagator='SGP4', interpolation='cubic_hermite')
        if any(metadata.get(k) != v for k, v in expected.items()) or metadata.get('epoch_utc') != EPOCH or metadata.get('native_frame') != 'TEMEOfDate' or len(metadata.get('tle_bundle_sha256','')) != 64:
            raise ValueError('Incompatible metadata')

    @classmethod
    def load(cls, path):
        with np.load(Path(path), allow_pickle=False) as z:
            return cls(z['time_s'], z['sat_ids'], z['position_km'], z['velocity_km_s'], json.loads(str(z['metadata_json'].item())))

    def save(self, path):
        with Path(path).open('xb') as f:
            np.savez_compressed(f, time_s=self.time_s, sat_ids=self.sat_ids,
                position_km=self.position_km, velocity_km_s=self.velocity_km_s,
                metadata_json=np.array(json.dumps(self.metadata, ensure_ascii=False, allow_nan=False)))

    def state(self, time_s, sat_ids=None):
        """Return [query time, satellite, xyz]; never extrapolate. Velocity is d(position)/dt."""
        q = np.atleast_1d(np.asarray(time_s, dtype=float))
        if q.ndim != 1 or not np.isfinite(q).all() or np.any(q < self.time_s[0]) or np.any(q > self.time_s[-1]):
            raise ValueError('Query outside ephemeris coverage')
        indices = np.arange(len(self.sat_ids)) if sat_ids is None else np.array([list(self.sat_ids).index(s) for s in sat_ids], dtype=int)
        k = np.clip(np.searchsorted(self.time_s, q, side='right') - 1, 0, len(self.time_s)-2)
        h = (self.time_s[k+1]-self.time_s[k])[:, None, None]
        s = (q-self.time_s[k])[:, None, None]/h
        r0, r1 = self.position_km[k][:, indices], self.position_km[k+1][:, indices]
        v0, v1 = self.velocity_km_s[k][:, indices], self.velocity_km_s[k+1][:, indices]
        r = (2*s**3-3*s**2+1)*r0 + (s**3-2*s**2+s)*h*v0 + (-2*s**3+3*s**2)*r1 + (s**3-s**2)*h*v1
        v = (6*s**2-6*s)*r0/h + (3*s**2-4*s+1)*v0 + (-6*s**2+6*s)*r1/h + (3*s**2-2*s)*v1
        return r, v


