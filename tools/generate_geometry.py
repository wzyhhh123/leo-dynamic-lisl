"""Frozen TLE -> SGP4 states -> 3D distances and sphere-LOS candidate edges."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from dynamic_lisl.common import PROJECT, EPOCH, dump, sha, new_output
from dynamic_lisl.sgp4_model import Sgp4Model
from dynamic_lisl.ephemeris import time_grid


def candidate_edges(position, max_range_km, earth_radius_km, clearance_km=0):
    """Each undirected pair appears once (i<j). Tangency is blocked."""
    position = np.asarray(position, dtype=float)
    if position.ndim != 2 or position.shape[1] != 3 or not np.isfinite(position).all():
        raise ValueError('Positions must be finite [satellite, 3]')
    if not np.isfinite([max_range_km, earth_radius_km, clearance_km]).all() or min(max_range_km, earth_radius_km) <= 0 or clearance_km < 0:
        raise ValueError('Invalid range/radius/clearance')
    radius = earth_radius_km + clearance_km
    if np.any(np.linalg.norm(position, axis=1) <= radius):
        raise ValueError('Satellite inside exclusion sphere')
    i, j = np.triu_indices(len(position), 1)
    a = position[i]
    d = position[j] - a
    d2 = np.einsum('ij,ij->i', d, d)
    fraction = np.divide(-np.einsum('ij,ij->i', a, d), d2, out=np.zeros_like(d2), where=d2 > 0)
    closest = a + np.clip(fraction, 0, 1)[:, None] * d
    distance = np.sqrt(d2)
    keep = (d2 > 0) & (distance <= max_range_km) & (np.linalg.norm(closest, axis=1) > radius)
    return np.column_stack((i[keep], j[keep])).astype(np.int32), distance[keep]


def generate(args):
    bundle = args.tle_dir.resolve()
    model = Sgp4Model.load(bundle)
    if not np.isfinite([args.start_s,args.duration_s,args.step_s]).all() or args.start_s < 0 or args.duration_s <= 0 or args.start_s + args.duration_s > model.duration_s:
        raise ValueError('Requested interval must lie within frozen TLE window [0,86400] s')
    times = time_grid(args.duration_s, args.step_s) + args.start_s
    # Validate geometry parameters before creating output.
    candidate_edges(np.array([[20000.,0,0]]),args.max_range_km,args.earth_radius_km,args.clearance_km)
    out = new_output('geometry')
    status = dict(status='RUNNING')
    dump(out/'summary.json',status)
    try:
        r,v = model.state(times)
        metadata = dict(schema='sgp4_geometry_snapshots_v1',epoch_utc=EPOCH,frame='TEMEOfDate',propagator='SGP4',gravity='WGS72',synthetic_tle=True,
            position_unit='km',velocity_unit='km/s',distance_unit='km',time_unit='s',satellite_count=len(model.ids),time_points=len(times),
            start_s=float(times[0]),stop_s=float(times[-1]),step_s=args.step_s,max_range_km=args.max_range_km,
            earth_model='opaque sphere',earth_radius_km=args.earth_radius_km,clearance_km=args.clearance_km,
            tle_sha256=sha(bundle/'constellation.tle'),manifest_sha256=sha(bundle/'manifest.json'),
            candidate_rule='all unordered pairs: 0 < Euclidean distance <= max_range; segment distance to Earth center > radius + clearance',
            limitation='Snapshot geometric candidates only: no FOV, terminals, setup, active-link capacity or continuous lifetime; 5000km default is diagnostic, not frozen hardware spec')
        np.savez_compressed(out/'positions.npz',time_s=times,sat_ids=np.array(model.ids),position_km=r,velocity_km_s=v,metadata_json=np.array(json.dumps(metadata)))
        planes=np.array([row['plane_id'] for row in model.records])
        counts=[]; inter_counts=[]
        with (out/'candidates.jsonl').open('w',encoding='utf-8') as f:
            for k,t in enumerate(times):
                pairs,distances=candidate_edges(r[k],args.max_range_km,args.earth_radius_km,args.clearance_km)
                inter=planes[pairs[:,0]] != planes[pairs[:,1]]
                # Node indices refer to sat_ids in positions.npz / metadata.json.
                f.write(json.dumps(dict(time_s=float(t),edges=[[int(a),int(b),float(d),bool(cross)] for (a,b),d,cross in zip(pairs,distances,inter)]),separators=(',',':'))+'\n')
                counts.append(len(pairs));inter_counts.append(int(inter.sum()))
                if (k+1)%100==0 or k+1==len(times):print('Generated %d/%d snapshots'%(k+1,len(times)),flush=True)
        metadata.update(sat_ids=model.ids,plane_ids=planes.tolist(),edge_columns=['source_index','target_index','distance_km','inter_plane'])
        dump(out/'metadata.json',metadata)
        status=dict(status='PASS_SNAPSHOT_GEOMETRY',satellites=len(model.ids),time_points=len(times),candidate_count_min=min(counts),candidate_count_max=max(counts),candidate_counts=counts,inter_plane_counts=inter_counts,
            output_hashes={name:sha(out/name) for name in ('positions.npz','candidates.jsonl','metadata.json')},
            code_hashes={str(p.relative_to(PROJECT)):sha(p) for p in (Path(__file__),PROJECT/'src/dynamic_lisl/sgp4_model.py')})
        print('Output:',out,flush=True)
        return out
    except Exception as exc:
        status=dict(status='FAIL',error=repr(exc));raise
    finally:
        dump(out/'summary.json',status)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tle-dir',type=Path,default=PROJECT/'data/raw/sgp4_x720')
    p.add_argument('--start-s',type=float,default=0)
    p.add_argument('--duration-s',type=float,default=600)
    p.add_argument('--step-s',type=float,default=30)
    p.add_argument('--max-range-km',type=float,default=5000)
    p.add_argument('--earth-radius-km',type=float,default=6378.137)
    p.add_argument('--clearance-km',type=float,default=0)
    generate(p.parse_args())

if __name__=='__main__':main()
