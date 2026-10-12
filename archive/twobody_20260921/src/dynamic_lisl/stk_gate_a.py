"""STK adapter for Gate A only. Imports COM lazily; never attaches to old scenes."""
import csv
from dataclasses import asdict
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path
import re
import uuid
import traceback
from .gate_a import Config,audit,audit_ephemeris,metadata,extract_subset,audit_subset

PROJECT=Path(__file__).resolve().parents[2]

def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def reserve_output(path):
    path=Path(path).resolve();allowed=(PROJECT/'outputs').resolve()
    if allowed not in path.parents:raise ValueError('Output must be a new child of dynamic_lisl_v2/outputs')
    path.mkdir(parents=True,exist_ok=False)
    return path

def scalar(result,names):
    for name in names:
        try:return float(result.DataSets.GetDataSetByName(name).GetValues()[0])
        except Exception:continue
    raise RuntimeError('STK_DATASET_MISSING: '+repr(names))

def provider(obj,name,t):
    return obj.DataProviders.GetDataPrvTimeVarFromPath(name).ExecSingle(t)

def rv(obj,t):
    r=provider(obj,'Cartesian Position/J2000',t);v=provider(obj,'Cartesian Velocity/J2000',t)
    return [scalar(r,[axis]) for axis in ('x','y','z')],[scalar(v,[axis]) for axis in ('x','y','z')]

def utc(c,t):
    d=datetime.strptime(c.epoch,'%d %b %Y %H:%M:%S.%f')+timedelta(seconds=t)
    return d.strftime('%d %b %Y %H:%M:%S.%f')

def verify_date(root,observed,expected):
    a=float(root.ConversionUtility.ConvertDate('UTCG','JDate',observed));b=float(root.ConversionUtility.ConvertDate('UTCG','JDate',expected))
    if abs(a-b)>1e-10:raise RuntimeError('EPOCH_OR_INTERVAL_MISMATCH')

def observed_config(root,prop,c):
    units={name:root.UnitPreferences.GetCurrentUnitAbbrv(name) for name in ('Distance','Angle','Time','DateFormat')}
    if units!={'Distance':'km','Angle':'deg','Time':'sec','DateFormat':'UTCG'}:raise RuntimeError('STK_UNIT_MISMATCH: '+str(units))
    verify_date(root,prop.InitialState.Epoch,c.epoch)
    verify_date(root,prop.StartTime,c.epoch);verify_date(root,prop.StopTime,utc(c,c.duration_s))
    return units

def run_stk(c,output,earth_cb,visible=False):
    c.validate();out=reserve_output(output)
    stages={k:'NOT_RUN' for k in ('A1_runtime','A2_geometry','A3_sampled_ephemeris','A4_subsets')}
    state=dict(overall='RUNNING',stages=stages,scope='Gate A only; B-G not implemented')
    dump(out/'gate_status.json',state)
    app=None;owns_blank=False
    try:
        earth_cb=Path(earth_cb)
        raw=earth_cb.read_text(encoding='utf-8-sig');match=re.search(r'^\s*Gm\s+([\d.Ee+-]+)\s*$',raw,re.M)
        if not match:raise RuntimeError('GM_NOT_FOUND')
        mu=float(match.group(1))/1e9
        if abs(mu-c.mu_km3_s2)>1e-8:raise RuntimeError('EARTH_GM_CONFIG_MISMATCH')
        from comtypes.client import CreateObject
        from comtypes.gen import STKObjects,STKUtil
        app=CreateObject('STK11.Application')
        root=app.Personality2
        if bool(root.CurrentScenario):raise RuntimeError('REFUSE_NONEMPTY_STK_INSTANCE')
        owns_blank=True;app.Visible=visible;app.UserControl=False
        for dim,unit in [('Distance','km'),('Angle','deg'),('Time','sec'),('DateFormat','UTCG')]:root.UnitPreferences.SetCurrentUnit(dim,unit)
        root.NewScenario('GateA_'+uuid.uuid4().hex[:10])
        scene=root.CurrentScenario;scenario=scene.QueryInterface(STKObjects.IAgScenario)
        scenario.StartTime=c.epoch;scenario.StopTime=utc(c,c.duration_s);scenario.Epoch=c.epoch
        seed=scene.Children.New(STKObjects.eSatellite,'GateASeed')
        sat=seed.QueryInterface(STKObjects.IAgSatellite)
        sat.SetPropagatorType(STKObjects.ePropagatorTwoBody)
        prop=sat.Propagator.QueryInterface(STKObjects.IAgVePropagatorTwoBody)
        prop.Step=60.0
        prop.StopTime=utc(c,c.duration_s)
        prop.StartTime=c.epoch
        prop.Step=60.0;prop.InitialState.OrbitEpoch.SetExplicitTime(c.epoch)
        prop.InitialState.Representation.AssignClassical(STKUtil.eCoordinateSystemJ2000,c.sma_km,0.,c.inclination_deg,0.,c.seed_raan_deg,c.seed_u_deg)
        dump(out/'propagation_readback.json',dict(start=str(prop.StartTime),stop=str(prop.StopTime),epoch=str(prop.InitialState.Epoch),step=prop.Step,scenario_start=str(scenario.StartTime),scenario_stop=str(scenario.StopTime)))
        prop.Propagate();units=observed_config(root,prop,c)
        actual=dict(units=units,epoch_readback=str(prop.InitialState.Epoch),propagator_enum=int(sat.PropagatorType),
            stk_version=str(root.ExecuteCommand('GetSTKVersion /').Item(0)),frame_provider='J2000',earth_cb_path=str(earth_cb.resolve()),earth_cb_sha256=sha(earth_cb),mu_km3_s2=mu)
        dump(out/'constellation_config.json',dict(requested=asdict(c),observed=actual))
        # Command F is nonnegative. sigma is an audit expectation, never inferred from results.
        command=f'Walker */Satellite/GateASeed Type Star NumPlanes {c.planes} NumSatsPerPlane {c.sats_per_plane} InterPlanePhaseIncrement {c.phase_increment} ColorByPlane Yes'
        root.ExecuteCommand(command);seed.Unload()
        collection=scene.Children.GetElements(STKObjects.eSatellite)
        if collection.Count!=c.count:raise RuntimeError('WALKER_COUNT_MISMATCH')
        objects={};rows=[]
        for i in range(collection.Count):
            obj=collection.Item(i);objects[obj.InstanceName]=obj
            satellite=obj.QueryInterface(STKObjects.IAgSatellite)
            if satellite.PropagatorType!=STKObjects.ePropagatorTwoBody:raise RuntimeError('PROPAGATOR_MISMATCH')
            child_prop=satellite.Propagator.QueryInterface(STKObjects.IAgVePropagatorTwoBody)
            observed_config(root,child_prop,c)
            el=provider(obj,'Classical Elements/J2000',c.epoch);r,v=rv(obj,c.epoch)
            rows.append(dict(source_name=obj.InstanceName,semi_major_axis_km=scalar(el,['Semi-major Axis','Semimajor Axis','SemiMajor Axis']),
                eccentricity=scalar(el,['Eccentricity']),inclination_deg=scalar(el,['Inclination']),raan_deg=scalar(el,['RAAN']),
                argument_of_latitude_deg=(scalar(el,['Arg of Perigee','Argument of Perigee'])+scalar(el,['True Anomaly']))%360,
                **metadata(c),r_km=r,v_km_s=v))
        stages['A1_runtime']='PASS'
        report,assigned=audit(rows,c);dump(out/'constellation_audit.json',report)
        dump(out/'constellation_manifest.json',assigned)
        with (out/'constellation_manifest.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(assigned[0]) if assigned else list(rows[0]));writer.writeheader();writer.writerows(assigned)
        if not report['passed']:stages['A2_geometry']='FAIL';raise RuntimeError('GEOMETRY_AUDIT_FAILED: see constellation_audit.json')
        stages['A2_geometry']='PASS'
        times=sorted({0.,17.3,60.,600.,c.duration_s})
        times=[t for t in times if t<=c.duration_s];samples=[]
        for a in assigned:
            obj=objects[a['source_name']]
            for t in times:
                r,v=rv(obj,utc(c,t));samples.append(dict(sat_name=a['sat_name'],t_s=t,r_km=r,v_km_s=v,**metadata(c)))
        ep=audit_ephemeris(samples,assigned,c,times);dump(out/'ephemeris_samples.json',samples);dump(out/'ephemeris_audit.json',ep)
        if not ep['passed']:stages['A3_sampled_ephemeris']='FAIL';raise RuntimeError('EPHEMERIS_AUDIT_FAILED')
        stages['A3_sampled_ephemeris']='PASS'
        if c.planes==18 and c.sats_per_plane==40:
            for n in (4,6):
                sub,ss=extract_subset(assigned,samples,list(range(n)));dest=out/f'subset_{n*40}';dest.mkdir()
                dump(dest/'manifest.json',sub);dump(dest/'ephemeris_samples.json',ss)
                check=audit_subset(sub,ss,assigned,samples,list(range(n)));check['parent_manifest_sha256']=sha(out/'constellation_manifest.json');check['parent_ephemeris_sha256']=sha(out/'ephemeris_samples.json')
                dump(dest/'audit.json',check)
                if not check['passed']:raise RuntimeError('SUBSET_MISMATCH')
            stages['A4_subsets']='PASS'
        else:stages['A4_subsets']='NOT_APPLICABLE_SMOKE'
        root.SaveAs(str(out/'scenario.sc'))
        state['overall']='PASS_SAMPLED_GEOMETRY'
        state['limitation']='Sparse sampled ephemeris, not continuous LOS/FOV/lifetime or Gate B-G validation'
        return out
    except Exception as exc:
        state['overall']='FAIL';state['error']=repr(exc)
        dump(out/'failure.json',dict(error=repr(exc),stages=stages,traceback=traceback.format_exc()))
        raise
    finally:
        if app is not None and owns_blank:
            try:app.Quit()
            except Exception as exc:state['cleanup_warning']=repr(exc)
        dump(out/'gate_status.json',state)
        dump(out/'provenance.json',dict(source_hashes={str(p.relative_to(PROJECT)):sha(p) for folder in ('src','tools','tests') for p in (PROJECT/folder).rglob('*.py')},
            output_hashes={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='provenance.json'}))





