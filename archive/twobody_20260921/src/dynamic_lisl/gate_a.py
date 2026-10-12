"""Strict, COM-free Walker-Star geometry validation (Python 3.9+)."""
from dataclasses import dataclass, asdict
import math
import numpy as np

EPOCH = '01 Jan 2026 00:00:00.00'

@dataclass(frozen=True)
class Config:
    planes: int = 18
    sats_per_plane: int = 40
    phase_increment: int = 1
    sigma: int = 1
    seed_raan_deg: float = 0.0
    seed_u_deg: float = 0.0
    sma_km: float = 7578.137
    inclination_deg: float = 85.0
    duration_s: float = 86400.0
    epoch: str = EPOCH
    frame: str = 'J2000'
    distance_unit: str = 'km'
    angle_unit: str = 'deg'
    time_unit: str = 'sec'
    propagator: str = 'TwoBody'
    mu_km3_s2: float = 398600.4415

    def validate(self):
        for v in asdict(self).values():
            if isinstance(v, (int,float)) and not math.isfinite(v):
                raise ValueError('NONFINITE_CONFIG')
        if not isinstance(self.planes,int) or self.planes<2 or not isinstance(self.sats_per_plane,int) or self.sats_per_plane<3:
            raise ValueError('POPULATION_CONFIG')
        if not isinstance(self.phase_increment,int) or not 0<=self.phase_increment<self.planes or self.sigma not in (-1,1):
            raise ValueError('PHASE_CONFIG')
        if self.sma_km<=6378.137 or not 0<self.inclination_deg<180 or self.duration_s<=0 or self.mu_km3_s2<=0:
            raise ValueError('ORBIT_CONFIG')
        if (self.epoch,self.frame,self.distance_unit,self.angle_unit,self.time_unit,self.propagator)!=(EPOCH,'J2000','km','deg','sec','TwoBody'):
            raise ValueError('EPOCH_FRAME_UNIT_PROPAGATOR_CONFIG')

    @property
    def count(self): return self.planes*self.sats_per_plane
    @property
    def spacing(self): return 360/self.sats_per_plane
    @property
    def phase(self): return self.sigma*self.phase_increment*360/self.count


def angular_error(a,b,period=360.0):
    return (a-b+period/2)%period-period/2


def metadata(c):
    return {k:getattr(c,k) for k in ('epoch','frame','distance_unit','angle_unit','time_unit','propagator')}


def analytic_state(c,p,k,t):
    om=math.radians(c.seed_raan_deg+p*180/c.planes)
    inc=math.radians(c.inclination_deg)
    u=math.radians(c.seed_u_deg+p*c.phase+k*c.spacing)+math.sqrt(c.mu_km3_s2/c.sma_km**3)*t
    a=np.array([math.cos(om),math.sin(om),0.0])
    b=np.array([-math.sin(om)*math.cos(inc),math.cos(om)*math.cos(inc),math.sin(inc)])
    return c.sma_km*(math.cos(u)*a+math.sin(u)*b), math.sqrt(c.mu_km3_s2/c.sma_km)*(-math.sin(u)*a+math.cos(u)*b)


def synthetic(c):
    c.validate();rows=[]
    for p in range(c.planes):
        for k in range(c.sats_per_plane):
            r,v=analytic_state(c,p,k,0)
            rows.append(dict(source_name=f'S{p}_{k}',semi_major_axis_km=c.sma_km,eccentricity=0.0,inclination_deg=c.inclination_deg,
                raan_deg=(c.seed_raan_deg+p*180/c.planes)%360,argument_of_latitude_deg=(c.seed_u_deg+p*c.phase+k*c.spacing)%360,
                **metadata(c),r_km=r.tolist(),v_km_s=v.tolist()))
    return rows


def audit(rows,c):
    c.validate();errors=[];assigned=[];seen=set();slots=set();groups={p:[] for p in range(c.planes)}
    def fail(code,who=''): errors.append(dict(code=code,source=who))
    if len(rows)!=c.count:fail('COUNT')
    numeric=('semi_major_axis_km','eccentricity','inclination_deg','raan_deg','argument_of_latitude_deg')
    for row in rows:
        name=row.get('source_name','')
        if not name or name in seen:fail('DUPLICATE_ID',name)
        seen.add(name)
        if any(row.get(k)!=v for k,v in metadata(c).items()):fail('METADATA',name)
        try:
            if not all(math.isfinite(float(row[k])) for k in numeric):raise ValueError()
        except (KeyError,ValueError,TypeError):fail('NONFINITE_OR_MISSING',name);continue
        raan=float(row['raan_deg']);u=float(row['argument_of_latitude_deg'])
        candidates=[p for p in range(c.planes) if abs(angular_error(raan,c.seed_raan_deg+p*180/c.planes))<=1e-4]
        if len(candidates)!=1:fail('RAAN_TARGET',name);continue
        p=candidates[0];phase=c.seed_u_deg+p*c.phase
        if abs(angular_error(u,phase,c.spacing))>1e-3:fail('GLOBAL_PHASE',name)
        k=int(round(((u-phase)%360)/c.spacing))%c.sats_per_plane
        if (p,k) in slots:fail('DUPLICATE_SLOT',name)
        slots.add((p,k));groups[p].append(u)
        if abs(float(row['semi_major_axis_km'])-c.sma_km)>1e-3:fail('SMA',name)
        if abs(float(row['eccentricity']))>1e-9:fail('ECCENTRICITY',name)
        if abs(float(row['inclination_deg'])-c.inclination_deg)>1e-6:fail('INCLINATION',name)
        expected_id=f'X{p}_{k+1}'
        if 'sat_name' in row and row['sat_name']!=expected_id:fail('ASSIGNED_ID',name)
        a=dict(row,plane_id=p,slot_id=k,sat_name=expected_id);assigned.append(a)
        try:
            r=np.asarray(row['r_km'],float);v=np.asarray(row['v_km_s'],float)
            if r.shape!=(3,) or v.shape!=(3,) or not np.isfinite(r).all() or not np.isfinite(v).all():raise ValueError()
            er,ev=analytic_state(c,p,k,0)
            if np.linalg.norm(r-er)>0.001:fail('INITIAL_POSITION',name)
            if np.linalg.norm(v-ev)>1e-6:fail('INITIAL_VELOCITY',name)
        except (KeyError,TypeError,ValueError):fail('CARTESIAN_DATA',name)
    for p,us in groups.items():
        if len(us)!=c.sats_per_plane:fail('PLANE_COUNT',str(p));continue
        us=sorted(u%360 for u in us)
        gaps=[(us[(i+1)%len(us)]-us[i])%360 for i in range(len(us))]
        if max(abs(g-c.spacing) for g in gaps)>1e-4:fail('INTRA_SPACING',str(p))
    return dict(passed=not errors,errors=errors,count=len(rows),expected_count=c.count,
        expected_raan_spacing_deg=180/c.planes,expected_signed_phase_deg=c.phase,config=asdict(c)),sorted(assigned,key=lambda r:(r['plane_id'],r['slot_id']))


def audit_ephemeris(samples,assigned,c,times):
    errors=[];lookup={r['sat_name']:r for r in assigned};seen=set();maxr=maxv=maxenergy=maxh=0.0
    for s in samples:
        key=(s.get('sat_name'),s.get('t_s'))
        if key in seen:errors.append('DUPLICATE_SAMPLE')
        seen.add(key)
        if key[0] not in lookup or key[1] not in times:errors.append('SAMPLE_ID_TIME');continue
        a=lookup[key[0]]
        try:
            r=np.asarray(s['r_km'],float);v=np.asarray(s['v_km_s'],float)
            if r.shape!=(3,) or v.shape!=(3,) or not np.isfinite(r).all() or not np.isfinite(v).all():raise ValueError()
            er,ev=analytic_state(c,a['plane_id'],a['slot_id'],float(key[1]))
            re=float(np.linalg.norm(r-er));ve=float(np.linalg.norm(v-ev));maxr=max(maxr,re);maxv=max(maxv,ve)
            e=float(np.dot(v,v)/2-c.mu_km3_s2/np.linalg.norm(r));e0=-c.mu_km3_s2/(2*c.sma_km)
            de=abs(e/e0-1);dh=abs(np.linalg.norm(np.cross(r,v))/math.sqrt(c.mu_km3_s2*c.sma_km)-1)
            maxenergy=max(maxenergy,de);maxh=max(maxh,float(dh))
            if re>0.001 or ve>1e-6 or de>1e-8 or dh>1e-8:errors.append('EPHEMERIS')
            if any(s.get(k)!=val for k,val in metadata(c).items()):errors.append('SAMPLE_METADATA')
        except (ValueError,TypeError,KeyError,ZeroDivisionError):errors.append('INVALID_SAMPLE')
    if seen!={(name,t) for name in lookup for t in times}:errors.append('SAMPLE_COVERAGE')
    return dict(passed=not errors,errors=sorted(set(errors)),samples=len(samples),sample_times_s=times,max_position_error_km=maxr,
        max_velocity_error_km_s=maxv,max_relative_energy_error=maxenergy,max_relative_h_error=maxh,
        coverage='Sparse sampled TwoBody cross-check; not a continuous visibility certificate')


def extract_subset(rows,samples,planes):
    ids=set(planes)
    if not ids or sorted(ids)!=list(range(min(ids),max(ids)+1)):raise ValueError('NONCONTIGUOUS_PLANES')
    available={r['plane_id'] for r in rows}
    if not ids<=available:raise ValueError('MISSING_PLANE')
    selected=[dict(r,boundary_plane=r['plane_id'] in (min(ids),max(ids))) for r in rows if r['plane_id'] in ids]
    names={r['sat_name'] for r in selected}
    return selected,[dict(s) for s in samples if s['sat_name'] in names]


def audit_subset(rows,samples,parent_rows,parent_samples,planes):
    expected_r,expected_s=extract_subset(parent_rows,parent_samples,planes)
    return dict(passed=rows==expected_r and samples==expected_s,plane_ids=planes,count=len(rows),method='Exact copied rows; no repropagation')
