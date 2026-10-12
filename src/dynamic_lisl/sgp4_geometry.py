"""SGP4-driven numerical sphere LOS/range boundary search, with resolution audit."""
import numpy as np
from scipy.optimize import brentq, minimize_scalar
from .ephemeris import time_grid


def margins(positions,max_range_km,earth_radius_km):
    a,b=positions[:,0],positions[:,1];d=b-a;d2=np.sum(d*d,axis=1)
    lam=np.divide(-np.sum(a*d,axis=1),d2,out=np.zeros_like(d2),where=d2>0)
    closest=a+np.clip(lam,0,1)[:,None]*d
    return np.minimum(np.linalg.norm(closest,axis=1)-earth_radius_km,max_range_km-np.sqrt(d2))


def search_windows(state,start_s,stop_s,max_range_km,earth_radius_km=6378.137,scan_step_s=2.0,time_tolerance_s=0.001,grazing_tolerance_km=1e-5):
    """state(times) returns [time,2,xyz] in one common geocentric frame.

    Native TEME is valid for simultaneous pair distances and spherical LOS.
    Find sampled extrema as well as sign changes; retain grazing neighborhoods.
    This is a convergence-tested numerical search, not an analytic certificate.
    """
    args=[start_s,stop_s,max_range_km,earth_radius_km,scan_step_s,time_tolerance_s,grazing_tolerance_km]
    if not np.isfinite(args).all() or not 0<=start_s<stop_s or min(args[2:])<=0:raise ValueError('INVALID_BOUNDARY_PARAMETERS')
    grid=time_grid(stop_s-start_s,scan_step_s)+start_s
    values=margins(state(grid),max_range_km,earth_radius_km)
    def margin(t):return float(margins(state(np.array([t])),max_range_km,earth_radius_km)[0])
    points=dict(zip(grid.tolist(),values.tolist()));grazing=[]
    slopes=np.diff(values)
    # A sampled local extremum seeds a bounded scalar optimization, so a contact
    # shorter than scan_step can still be detected even with both endpoints negative.
    for k in np.where(slopes[:-1]*slopes[1:]<=0)[0]+1:
        if slopes[k-1]==0 and slopes[k]==0:continue
        is_max=slopes[k-1]>=0 and slopes[k]<=0
        sign=-1 if is_max else 1
        opt=minimize_scalar(lambda t:sign*margin(t),bounds=(grid[k-1],grid[k+1]),method='bounded',options={'xatol':time_tolerance_s/10})
        if not opt.success:raise ValueError('BOUNDARY_EXTREMUM_SEARCH_FAILED')
        t=float(opt.x);m=margin(t);points[t]=m
        if abs(m)<=grazing_tolerance_km:grazing.append([max(start_s,t-scan_step_s),min(stop_s,t+scan_step_s)])
    ordered=sorted(points);roots=[]
    for a,b in zip(ordered[:-1],ordered[1:]):
        fa,fb=points[a],points[b]
        if fa==0:roots.append(a)
        if fa*fb<0:roots.append(float(brentq(margin,a,b,xtol=time_tolerance_s/10)))
    if points[ordered[-1]]==0:roots.append(ordered[-1])
    roots=sorted(set(roots));cuts=sorted(set([start_s,stop_s]+roots+[t for interval in grazing for t in interval]))
    intervals=[]
    for a,b in zip(cuts[:-1],cuts[1:]):
        mid=(a+b)/2
        uncertain=any(lo<=mid<=hi for lo,hi in grazing)
        status='unresolved_grazing' if uncertain else ('visible' if margin(mid)>0 else 'invisible')
        if intervals and intervals[-1]['state']==status:intervals[-1]['end_s']=b
        else:intervals.append(dict(start_s=a,end_s=b,state=status))
    return dict(roots_s=roots,intervals=intervals,grazing_regions_s=grazing,scan_step_s=scan_step_s,time_tolerance_s=time_tolerance_s,
        model='SGP4 native TEME-of-date; spherical LOS and range',max_range_km=max_range_km,earth_radius_km=earth_radius_km,
        certification='Numerical scan/extremum/root refinement; no universal continuous guarantee')


def geometry_windows(model,pair,start_s=0,stop_s=None,max_range_km=5000,scan_step_s=2.0):
    if len(pair)!=2 or pair[0]==pair[1]:raise ValueError('DISTINCT_PAIR_REQUIRED')
    stop_s=model.duration_s if stop_s is None else stop_s
    if not 0<=start_s<stop_s<=model.duration_s:raise ValueError('GEOMETRY_OUTSIDE_COVERAGE')
    query=lambda t:model.state(t,pair)[0]
    coarse=search_windows(query,start_s,stop_s,max_range_km,scan_step_s=scan_step_s)
    fine=search_windows(query,start_s,stop_s,max_range_km,scan_step_s=scan_step_s/2)
    roots_a,roots_b=coarse['roots_s'],fine['roots_s']
    same_count=len(roots_a)==len(roots_b)
    error=max((abs(a-b) for a,b in zip(roots_a,roots_b)),default=0.0) if same_count else None
    stable=same_count and error<=0.01 and [x['state'] for x in coarse['intervals']]==[x['state'] for x in fine['intervals']]
    fine.update(pair=pair,resolution_audit=dict(passed=stable,coarse_step_s=scan_step_s,fine_step_s=scan_step_s/2,max_root_shift_s=error),
        limitation='No FOV/terminal/setup model; near-tangent windows unresolved; resolution stability is not a mathematical no-missed-event proof')
    return fine
