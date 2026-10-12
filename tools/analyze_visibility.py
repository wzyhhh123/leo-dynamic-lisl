"""Pilot visibility intervals, strict TEME Gate A and exact 4/6-plane subsets."""
import argparse,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dynamic_lisl.common import PROJECT,dump,sha,new_output,EPOCH
from dynamic_lisl.sgp4_model import Sgp4Model
from dynamic_lisl.sgp4_geometry import search_windows


def stats(values):
    a=np.asarray(values,float)
    return dict(count=len(a),min=float(a.min()),median=float(np.median(a)),p95=float(np.percentile(a,95)),max=float(a.max())) if len(a) else dict(count=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pilot',type=Path,default=PROJECT/'outputs/geometry_20260921T053240_016088Z')
    a=p.parse_args();pilot=a.pilot.resolve();meta=json.loads((pilot/'metadata.json').read_text());summary=json.loads((pilot/'summary.json').read_text())
    for name,h in summary['output_hashes'].items():
        if sha(pilot/name)!=h:raise ValueError('PILOT_HASH_CHANGED')
    model=Sgp4Model.load(PROJECT/'data/raw/sgp4_x720')
    if sha(PROJECT/'data/raw/sgp4_x720/constellation.tle')!=meta['tle_sha256']:raise ValueError('TLE_PARENT_MISMATCH')
    out=new_output('visibility');dump(out/'status.json',dict(status='RUNNING',pilot=str(pilot)))
    with np.load(pilot/'positions.npz',allow_pickle=False) as z:
        times=z['time_s'];r=z['position_km'];v=z['velocity_km_s'];ids=z['sat_ids']
    if any(meta.get(k)!=v for k,v in dict(position_unit='km',velocity_unit='km/s',distance_unit='km',time_unit='s',propagator='SGP4',gravity='WGS72').items()):raise ValueError('UNITS_PROPAGATOR_GRAVITY')
    if meta['frame']!='TEMEOfDate' or meta['epoch_utc']!=EPOCH or list(ids)!=model.ids:raise ValueError('FRAME_EPOCH_ID')
    rr,vv=model.state(times);repeat_r,repeat_v=Sgp4Model.load(PROJECT/'data/raw/sgp4_x720').state(times)
    repeat=bool(np.array_equal(rr,repeat_r) and np.array_equal(vv,repeat_v) and np.array_equal(rr,r) and np.array_equal(vv,v))
    planes=np.array([x['plane_id'] for x in model.records]);slots=np.array([x['slot_id'] for x in model.records])
    mapping=bool(len(ids)==720 and set(zip(planes,slots))=={(p,s) for p in range(18) for s in range(40)} and all(x['sat_name']==f'X{x["plane_id"]}_{x["slot_id"]+1}' and x['ssc']==10000+x['plane_id']*40+x['slot_id'] for x in model.records))
    er,ev=model.state(0);er,ev=er[0],ev[0];h=np.cross(er,ev);hn=h/np.linalg.norm(h,axis=1)[:,None]
    n=np.cross(np.broadcast_to([0,0,1],h.shape),h);n/=np.linalg.norm(n,axis=1)[:,None]
    ra=np.degrees(np.arctan2(n[:,1],n[:,0]));inc=np.degrees(np.arccos(hn[:,2]));u=np.degrees(np.arctan2(np.sum(er*np.cross(hn,n),axis=1),np.sum(er*n,axis=1)))
    error=lambda x,y:(x-y+180)%360-180
    errors=dict(raan_deg=float(np.max(abs(error(ra,planes*10)))),inclination_deg=float(np.max(abs(inc-85))),phase_deg=float(np.max(abs(error(u,planes*.5+slots*9)))),radius_km=float(np.max(abs(np.linalg.norm(er,axis=1)-7578.137))))
    strict=all(errors[x]<=.001 for x in ('raan_deg','inclination_deg','phase_deg')) and errors['radius_km']<=.025
    dump(out/'gate_a.json',dict(status='PASS' if strict and repeat and mapping else 'TARGET_GEOMETRY_MISMATCH',frame='TEMEOfDate',propagator='SGP4/WGS72',epoch=EPOCH,repeat_generation_exact=repeat,id_plane_mapping=mapping,target_errors=errors,thresholds=dict(angle_deg=.001,radius_km=.025),note='Pilot retained; no J2000/TwoBody cross-validation required or performed'))
    if not repeat or not mapping:raise ValueError('PILOT_CONSISTENCY_FAILED')
    # Every mother pair is searched, including pairs absent from all saved snapshots.
    start,stop=float(times[0]),float(times[-1]);cutoff=meta['max_range_km'];radius=meta['earth_radius_km']+meta['clearance_km']
    windows=[];unstable=[];uncertain=[];total=720*719//2
    with (out/'intervals.jsonl').open('w') as f:
        done=0
        for i in range(720):
            for j in range(i+1,720):
                query=lambda t:model.state(t,[model.ids[i],model.ids[j]])[0]
                coarse=search_windows(query,start,stop,cutoff,radius,scan_step_s=30)
                fine=search_windows(query,start,stop,cutoff,radius,scan_step_s=15)
                roots,roots2=coarse['roots_s'],fine['roots_s']
                stable=len(roots)==len(roots2) and max((abs(x-y) for x,y in zip(roots,roots2)),default=0)<=.01 and [x['state'] for x in coarse['intervals']]==[x['state'] for x in fine['intervals']]
                if not stable:unstable.append([i,j])
                for w in coarse['intervals']:
                    if w['state']=='unresolved_grazing':uncertain.append(dict(pair=[i,j],**w));continue
                    if w['state']!='visible':continue
                    lo,hi=w['start_s'],w['end_s'];q=np.unique(np.r_[lo,(lo+hi)/2,hi,times[(times>lo)&(times<hi)]])
                    pos=query(q);dist=np.linalg.norm(pos[:,1]-pos[:,0],axis=1)
                    row=dict(i=i,j=j,start_s=lo,end_s=hi,observed_duration_s=hi-lo,left_censored=lo==start,right_censored=hi==stop,
                        distance_min_sampled_km=float(dist.min()),distance_max_sampled_km=float(dist.max()),distance_mean_sampled_km=float(dist.mean()),plane_gap=int(abs(planes[i]-planes[j])),resolution_stable=stable)
                    windows.append(row);f.write(json.dumps(row)+'\n')
                done+=1
            if (i+1)%20==0:print(f'Pairs searched: {done}/{total}',flush=True)
    def summarize(rows,selected):
        edge_time=sum(x['observed_duration_s'] for x in rows)
        boundary={k for k in selected if planes[k] in (min(planes[selected]),max(planes[selected]))}
        interior=set(selected)-boundary
        def nodes(group):
            return dict(nodes=len(group),mean_visible_degree_time_weighted=sum(x['observed_duration_s']*((x['i'] in group)+(x['j'] in group)) for x in rows)/((stop-start)*len(group)) if group else None)
        return dict(intervals=len(rows),observed_duration_s=stats([x['observed_duration_s'] for x in rows]),complete_lifetime_s=stats([x['observed_duration_s'] for x in rows if not x['left_censored'] and not x['right_censored']]),censored_intervals=sum(x['left_censored'] or x['right_censored'] for x in rows),distance_sampled_km=stats([x['distance_mean_sampled_km'] for x in rows]),
            plane_gap={str(g):dict(intervals=sum(x['plane_gap']==g for x in rows),visible_pair_seconds=sum(x['observed_duration_s'] for x in rows if x['plane_gap']==g)) for g in sorted(set(x['plane_gap'] for x in rows))},boundary=nodes(boundary),interior=nodes(interior),visible_pair_seconds=edge_time)
    report=dict(parent=summarize(windows,list(range(720))),cutoff_role='diagnostic only; not frozen LCT hardware range',window_s=[start,stop],coarse_scan_s=30,validation_scan_s=15,root_tolerance_s=.001,unstable_pairs=unstable,unresolved_grazing=uncertain,limitation='Numerical intervals, not a universal no-missed-contact proof; interval endpoints can be censored by pilot window; no FOV/terminals')
    for count in (160,240):
        selected=np.flatnonzero(planes<count//40);dest=out/f'subset_{count}';dest.mkdir()
        subrows=[x for x in windows if x['i'] in set(selected) and x['j'] in set(selected)]
        np.savez_compressed(dest/'positions.npz',time_s=times,sat_ids=ids[selected],position_km=r[:,selected],velocity_km_s=v[:,selected])
        dump(dest/'manifest.json',dict(parent_asset=str(pilot),parent_positions_sha256=sha(pilot/'positions.npz'),parent_intervals_sha256=sha(out/'intervals.jsonl'),parent_indices=selected.tolist(),plane_ids=list(range(count//40)),frame='TEMEOfDate',epoch_utc=EPOCH,satellite_ids=ids[selected].tolist(),boundary_plane_ids=[0,count//40-1]))
        with (dest/'intervals.jsonl').open('w') as f:
            for row in subrows:f.write(json.dumps(row)+'\n')
        with np.load(dest/'positions.npz') as z:passed=np.array_equal(z['position_km'],r[:,selected]) and np.array_equal(z['velocity_km_s'],v[:,selected]) and np.array_equal(z['sat_ids'],ids[selected])
        saved=[json.loads(x) for x in (dest/'intervals.jsonl').read_text().splitlines()];passed=passed and saved==subrows
        dump(dest/'audit.json',dict(passed=passed,method='Exact mother states and induced visibility intervals; stable parent IDs, no wrap or repropagation'))
        if not passed:raise ValueError('SUBSET_FAILED')
        report[f'subset_{count}']=summarize(subrows,selected.tolist())
    dump(out/'statistics.json',report)
    for name,h in summary['output_hashes'].items():
        if sha(pilot/name)!=h:raise ValueError('PILOT_MODIFIED')
    dump(out/'status.json',dict(status='PASS_PILOT_INTERVALS' if not unstable and not uncertain else 'RESOLUTION_REVIEW_REQUIRED',strict_gate_a_passed=strict,pilot_unchanged=True,pairs_checked=total))
    dump(out/'hashes.json',{str(x.relative_to(out)):sha(x) for x in out.rglob('*') if x.is_file() and x.name!='hashes.json'})
    print(out,flush=True)

if __name__=='__main__':main()
