"""Read an accepted Gate A STK scene into an independent ephemeris dataset."""
import json
from datetime import datetime, timezone
from pathlib import Path
import traceback
import numpy as np
from .gate_a import Config, audit
from .ephemeris import Ephemeris, circular_states, time_grid, audit_interpolation, geometry_windows
from .stk_gate_a import PROJECT, dump, sha, reserve_output, observed_config, verify_date, rv


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify_source(folder):
    folder = Path(folder).resolve()
    status = read_json(folder/'gate_status.json')
    if status['overall'] != 'PASS_SAMPLED_GEOMETRY': raise ValueError('Source Gate A did not pass')
    config = Config(**read_json(folder/'constellation_config.json')['requested'])
    rows = read_json(folder/'constellation_manifest.json')
    report, assigned = audit(rows, config)
    if not report['passed'] or assigned != rows: raise ValueError('Source manifest failed independent audit')
    provenance = read_json(folder/'provenance.json')['output_hashes']
    for required in ('scenario.sc','constellation_config.json','constellation_manifest.json','gate_status.json'):
        if required not in provenance: raise ValueError('Missing source hash: '+required)
    for name, expected in provenance.items():
        p = (folder/name).resolve()
        if folder not in p.parents or sha(p) != expected: raise ValueError('Source hash mismatch: '+name)
    return config, rows, provenance


def export(source, step_s=30.0, duration_s=None, limit=None, visible=False):
    source = Path(source).resolve()
    config, all_rows, source_hashes = verify_source(source)
    duration_s = config.duration_s if duration_s is None else duration_s
    if not np.isfinite(duration_s) or not 0 < duration_s <= config.duration_s: raise ValueError('Invalid requested duration')
    if limit is not None and not 1 <= limit <= len(all_rows): raise ValueError('Invalid satellite limit')
    rows = all_rows if limit is None else all_rows[:limit]
    times = time_grid(duration_s,step_s)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out = reserve_output(PROJECT/'outputs'/('ephemeris_'+stamp))
    status = dict(overall='RUNNING',source=str(source),satellites=len(rows),time_points=len(times),step_s=step_s,duration_s=duration_s)
    dump(out/'status.json',status)
    app = None; owns_blank = False
    try:
        from comtypes.client import CreateObject
        from comtypes.gen import STKObjects
        print('Opening a separate STK instance...',flush=True)
        app = CreateObject('STK11.Application'); root = app.Personality2
        if bool(root.CurrentScenario): raise RuntimeError('REFUSE_NONEMPTY_STK_INSTANCE')
        owns_blank = True; app.Visible = visible; app.UserControl = False
        root.LoadScenario(str(source/'scenario.sc'))
        for dim,unit in [('Distance','km'),('Angle','deg'),('Time','sec'),('DateFormat','UTCG')]:
            root.UnitPreferences.SetCurrentUnit(dim,unit)
        scene = root.CurrentScenario.QueryInterface(STKObjects.IAgScenario)
        verify_date(root,scene.Epoch,config.epoch)
        objects = []
        for row in rows:
            obj = root.GetObjectFromPath('*/Satellite/'+row['source_name'])
            sat = obj.QueryInterface(STKObjects.IAgSatellite)
            if sat.PropagatorType != STKObjects.ePropagatorTwoBody: raise ValueError('Source is not TwoBody')
            observed_config(root,sat.Propagator.QueryInterface(STKObjects.IAgVePropagatorTwoBody),config)
            objects.append(obj)
        # Epoch was checked above; EpSec is now unambiguously relative to the contract epoch.
        root.UnitPreferences.SetCurrentUnit('DateFormat','EpSec')
        r = np.empty((len(times),len(rows),3)); v = np.empty_like(r)
        max_r = max_v = 0.0
        for j,(obj,row) in enumerate(zip(objects,rows)):
            for path,destination in [('Cartesian Position/J2000',r),('Cartesian Velocity/J2000',v)]:
                result = obj.DataProviders.GetDataPrvTimeVarFromPath(path).Exec(0.0,float(duration_s),float(step_s))
                tt = np.asarray(result.DataSets.GetDataSetByName('Time').GetValues(),float)
                data = np.column_stack([result.DataSets.GetDataSetByName(axis).GetValues() for axis in ('x','y','z')]).astype(float)
                # STK versions differ on whether a non-grid stop time is appended.
                if len(tt)==len(times)-1 and np.allclose(tt,times[:-1],rtol=0,atol=1e-7):
                    final = obj.DataProviders.GetDataPrvTimeVarFromPath(path).ExecSingle(float(duration_s))
                    data = np.vstack([data,[float(final.DataSets.GetDataSetByName(axis).GetValues()[0]) for axis in ('x','y','z')]])
                    tt = np.append(tt,duration_s)
                if len(tt)!=len(times) or not np.allclose(tt,times,rtol=0,atol=1e-7): raise ValueError('STK time axis mismatch')
                destination[:,j,:] = data
            er,ev = circular_states(config,[row],times)
            max_r = max(max_r,float(np.linalg.norm(r[:,j]-er[:,0],axis=-1).max()))
            max_v = max(max_v,float(np.linalg.norm(v[:,j]-ev[:,0],axis=-1).max()))
            if (j+1)%60==0 or j+1==len(rows): print('Exported %d/%d satellites'%(j+1,len(rows)),flush=True)
        grid_check = dict(passed=max_r<=0.001 and max_v<=1e-6,samples=len(times)*len(rows),max_position_error_m=max_r*1000,max_velocity_error_m_s=max_v*1000)
        dump(out/'grid_audit.json',grid_check)
        if not grid_check['passed']: raise ValueError('STK grid versus analytic reference failed')
        meta = dict(schema='dynamic_lisl_ephemeris_v1',frame='J2000',position_unit='km',velocity_unit='km/s',time_unit='s',propagator='TwoBody',interpolation='cubic_hermite',epoch_utc=config.epoch,
            source_gate_dir=str(source),source_manifest_sha256=sha(source/'constellation_manifest.json'),source_scene_sha256=sha(source/'scenario.sc'),
            source_names=[row['source_name'] for row in rows],config=read_json(source/'constellation_config.json')['requested'],rows=[dict(sat_name=x['sat_name'],plane_id=x['plane_id'],slot_id=x['slot_id']) for x in rows])
        ep = Ephemeris(times,[x['sat_name'] for x in rows],r,v,meta)
        print('Checking interpolation at three off-grid points per interval...',flush=True)
        interpolation = audit_interpolation(ep,config,rows,velocity_tol_km_s=1e-5)
        dump(out/'interpolation_audit.json',interpolation)
        if not interpolation['passed']: raise ValueError('Interpolation tolerance exceeded; rerun with a smaller --step-s')
        # Fresh STK calls at off-grid times cross-check the interpolator without using its analytic reference.
        rng = np.random.default_rng(20260918); heldout = []
        for j in np.unique(np.linspace(0,len(rows)-1,min(12,len(rows)),dtype=int)):
            for t in rng.uniform(0,duration_s,3):
                sr,sv = rv(objects[j],float(t)); ir,iv = ep.state(float(t),[rows[j]['sat_name']])
                heldout.append(dict(sat_name=rows[j]['sat_name'],time_s=float(t),position_error_m=float(np.linalg.norm(ir[0,0]-sr)*1000),velocity_error_m_s=float(np.linalg.norm(iv[0,0]-sv)*1000)))
        heldout_report = dict(passed=all(x['position_error_m']<=1 and x['velocity_error_m_s']<=0.01 for x in heldout),seed=20260918,samples=heldout)
        dump(out/'stk_off_grid_audit.json',heldout_report)
        if not heldout_report['passed']: raise ValueError('Fresh STK off-grid check failed')
        ep.save(out/'ephemeris.npz')
        reloaded = Ephemeris.load(out/'ephemeris.npz')
        rr,vv = reloaded.state([times[0],times[-1]])
        if not np.array_equal(rr,r[[0,-1]]) or not np.array_equal(vv,v[[0,-1]]): raise ValueError('NPZ roundtrip failed')
        # Small geometry demonstration only, never an all-pair candidate graph or network result.
        examples = []
        if len(rows)>1:
            for j in sorted(set([1,len(rows)//2,len(rows)-1])):
                examples.append(geometry_windows(config,rows[0],rows[j],0,duration_s,5000))
        dump(out/'geometry_boundary_examples.json',dict(scope='Demonstration pairs; 5000 km range and spherical Earth are explicit diagnostic assumptions',pairs=examples))
        verify_source(source)  # Confirm reading did not alter the frozen source.
        status['overall']='PASS_EXPORTED_EPHEMERIS'
        status['limitation']='Interpolation checks are sampled; geometry examples exclude FOV, pointing, setup, network and continuous ellipsoidal LOS'
        print('Saved:',out/'ephemeris.npz',flush=True)
        return out
    except Exception as exc:
        status['overall']='FAIL'; status['error']=repr(exc)
        dump(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc()))
        raise
    finally:
        if app is not None and owns_blank:
            try: app.Quit()
            except Exception as exc: status['cleanup_warning']=repr(exc)
        dump(out/'status.json',status)
        dump(out/'provenance.json',dict(source_output_hashes=source_hashes,source_code_hashes={str(p.relative_to(PROJECT)):sha(p) for folder in ('src','tools','tests') for p in (PROJECT/folder).rglob('*.py')},output_hashes={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='provenance.json'}))
