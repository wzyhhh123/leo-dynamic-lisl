"""Offline J2000 ephemeris reader; no STK or legacy executor dependency."""
import json
import math
from pathlib import Path
import numpy as np
from .gate_a import Config, analytic_state


def time_grid(duration, step):
    if not np.isfinite([duration, step]).all() or duration <= 0 or step <= 0:
        raise ValueError('Positive finite duration and step required')
    t = np.arange(int(math.floor(duration / step)) + 1, dtype=float) * step
    if duration - t[-1] > 1e-9:
        t = np.append(t, duration)
    else:
        t[-1] = duration
    return t


def circular_states(config, rows, times):
    """Independent exact circular TwoBody reference, specific to the Gate A contract."""
    times = np.atleast_1d(np.asarray(times, float))
    r0, v0 = zip(*(analytic_state(config, r['plane_id'], r['slot_id'], 0) for r in rows))
    r0, v0 = np.asarray(r0), np.asarray(v0)
    n = math.sqrt(config.mu_km3_s2 / config.sma_km**3)
    a = (n * times)[:, None, None]
    return np.cos(a)*r0 + np.sin(a)*v0/n, -n*np.sin(a)*r0 + np.cos(a)*v0


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
        expected = dict(schema='dynamic_lisl_ephemeris_v1', frame='J2000', position_unit='km', velocity_unit='km/s', time_unit='s', propagator='TwoBody', interpolation='cubic_hermite')
        if any(metadata.get(k) != v for k, v in expected.items()) or not metadata.get('epoch_utc'):
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


def audit_interpolation(ephemeris, config, rows, position_tol_km=0.001, velocity_tol_km_s=1e-6):
    """Check every satellite in every interval at three off-grid fractions."""
    max_r = max_v = 0.0
    intervals = np.diff(ephemeris.time_s)
    fractions = (0.2113248654051871, 0.5, 0.7886751345948129)
    for start in range(0, len(intervals), 128):
        for fraction in fractions:
            q = ephemeris.time_s[start:start+128][ : len(intervals[start:start+128])] + fraction*intervals[start:start+128]
            r, v = ephemeris.state(q)
            er, ev = circular_states(config, rows, q)
            max_r = max(max_r, float(np.linalg.norm(r-er, axis=-1).max()))
            max_v = max(max_v, float(np.linalg.norm(v-ev, axis=-1).max()))
    return dict(passed=max_r <= position_tol_km and max_v <= velocity_tol_km_s,
        max_position_error_m=1000*max_r, max_velocity_error_m_s=1000*max_v,
        position_tolerance_m=1000*position_tol_km, velocity_tolerance_m_s=1000*velocity_tol_km_s,
        off_grid_samples=len(intervals)*len(rows)*3, fractions=list(fractions),
        scope='Sampled error check against exact circular TwoBody; not a universal interpolation bound')


def geometry_windows(config, row_i, row_j, start_s, stop_s, max_range_km, earth_radius_km=6378.137, tolerance_s=0.01, coarse_step_s=60):
    """Conservative sphere-LOS + range windows using exact circular states.

    Bounds use |d margin/dt| <= |vi|+|vj|. Ambiguous leaves are retained;
    equal endpoint signs do not hide brief contacts or tangencies.
    No terminal FOV, pointing, acquisition, atmosphere or Earth ellipsoid model.
    """
    config.validate()
    if row_i['sat_name'] == row_j['sat_name']:
        raise ValueError('Distinct satellites required')
    if not np.isfinite([start_s,stop_s,max_range_km,earth_radius_km,tolerance_s,coarse_step_s]).all() or not 0 <= start_s < stop_s <= config.duration_s or min(max_range_km,earth_radius_km,tolerance_s,coarse_step_s) <= 0:
        raise ValueError('Invalid geometry interval or constraint')
    def margin(t):
        a = analytic_state(config,row_i['plane_id'],row_i['slot_id'],t)[0]
        b = analytic_state(config,row_j['plane_id'],row_j['slot_id'],t)[0]
        d = b-a; d2 = float(np.dot(d,d))
        lam = np.clip(-np.dot(a,d)/d2,0,1) if d2 > 0 else 0.0
        return min(float(np.linalg.norm(a+lam*d))-earth_radius_km, max_range_km-math.sqrt(d2))
    bound = 2*math.sqrt(config.mu_km3_s2/config.sma_km)
    pieces = []; evaluations = 0
    def visit(a,b):
        nonlocal evaluations
        m = margin((a+b)/2); evaluations += 1
        uncertainty = bound*(b-a)/2 + 1e-8
        if m > uncertainty: label = 'visible'
        elif m < -uncertainty: label = 'invisible'
        elif b-a <= tolerance_s: label = 'unresolved_boundary'
        else:
            mid = (a+b)/2; visit(a,mid); visit(mid,b); return
        pieces.append(dict(start_s=a,end_s=b,state=label))
    grid = time_grid(stop_s-start_s,coarse_step_s)+start_s
    for a,b in zip(grid[:-1],grid[1:]): visit(float(a),float(b))
    merged = []
    for item in pieces:
        if merged and merged[-1]['state']==item['state'] and item['state']!='unresolved_boundary':
            merged[-1]['end_s']=item['end_s']
        else: merged.append(dict(item))
    return dict(pair=[row_i['sat_name'],row_j['sat_name']],model='exact circular TwoBody; opaque sphere LOS plus range only',
        earth_radius_km=earth_radius_km,max_range_km=max_range_km,tolerance_s=tolerance_s,
        lipschitz_bound_km_s=bound,evaluations=evaluations,intervals=merged,
        unresolved_leaf_count=sum(p['state']=='unresolved_boundary' for p in pieces),
        limitation='Unresolved leaves are not usable windows; no full LISL lifetime or FOV certification')
