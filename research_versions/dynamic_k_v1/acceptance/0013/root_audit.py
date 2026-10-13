"""Append-only N4-P0D. One root construction; no actions or predictions."""
import hashlib,json,os,platform,sys,time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from datetime import datetime,timezone
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(V/'acceptance/0011'),str(V),str(P/'src')]
import workflow as old
import controlled_cost as previous
from runtime.n4_p0 import causal_view,ForecastInput,make_sanitized_root,encode
vc=old.vc
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='e77bf7624a4ac505e0dc52d77d79f6a2dcb45c240d3494d8fffe1119d3040aae'
ROOT='ba301c6b0d92b96b8490fe28b24322e254377aea01adffd0c368653daa3f01f6'
EXPECTED=vc.load_expected(P,ORIGIN,PARENT)[2]
def write(name,value):
    p=A/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=True,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def bound(p):
    p=Path(p);r=p.relative_to(P).as_posix();info=vc.file_info(p)
    if r in EXPECTED:
        assert EXPECTED[r]==info,'INPUT_BINDING_MISMATCH:'+r
    elif p.name=='record.json' and p.parent.parent==V/'revisions':
        index=int(p.parent.name)
        if index==12:assert info['sha256']==PARENT,'LATEST_RECORD_BINDING_MISMATCH'
        else:
            anchor=vc.read_json(V/'revisions'/('%04d'%(index+1))/'record.json')['parent_record']
            assert anchor==dict(path=r,**info),'PARENT_RECORD_BINDING_MISMATCH'
    else:raise ValueError('UNREGISTERED_INPUT:'+r)
    return dict(path=r,**info)
def read(p):bound(p);return vc.read_json(p)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def pairs(x):return dict(x)
def field_scan(x,path='$',found=None):
    if found is None:found=[]
    if isinstance(x,dict):
        for k,v in x.items():
            q=path+'.'+str(k)
            if any(s in str(k).lower() for s in ('root','checkpoint','state_json','seed','initial_state')):
                found.append(dict(path=q,type=type(v).__name__,scalar=v if type(v) in (str,int,float,bool) else None))
            field_scan(v,q,found)
    elif isinstance(x,list):
        for i,v in enumerate(x):field_scan(v,path+'['+str(i)+']',found)
    return found
def inspect():
    rows=[]
    for p in sorted((V/'acceptance/0011').iterdir()):
        if not p.is_file():continue
        row=bound(p)
        if p.suffix=='.json':
            d=vc.read_json(p);row.update(top_level_keys=list(d) if isinstance(d,dict) else None,
                                        relevant_fields=field_scan(d))
        rows.append(row)
    revisions=[]
    for i in range(1,13):revisions.append(bound(V/'revisions'/('%04d'%i)/'record.json'))
    src=['acceptance/0011/controlled_cost.py','acceptance/0011/failure_diagnostic.py',
         'acceptance/0011/failure_diagnostic_attempt02.py','acceptance/0011/workflow.py',
         'acceptance/0012/run_diagnosis.py','runtime/n4_p0.py','runtime/n1b_fifo.py',
         'runtime/n1b_observer.py','runtime/n1b_evaluator.py','runtime/n1a.py',
         'runtime/n2_controller.py','runtime/n3_baselines.py','tests/test_n3_baselines.py']
    inputs=['outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json',
            'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',
            'configs/hardware_gate_c_simplified_v1.json',
            'data/raw/sgp4_x720/manifest.json','data/raw/sgp4_x720/hashes.json',
            'data/raw/sgp4_x720/constellation.tle']
    r11=read(V/'revisions/0011/record.json')
    write('historical_evidence_inventory.json',dict(acceptance_0011_files=rows,
        revision_0011_all_added_files=r11['changes']['added'],
        revision_chain=revisions,source_bindings=[bound(V/s) for s in src],
        physical_input_bindings=[bound(P/s) for s in inputs],
        origin_sha256=ORIGIN,parent_sha256=PARENT,
        native_checkpoint_file_extensions=[r['path'] for r in r11['changes']['added']
            if Path(r['path']).suffix.lower() in ('.pkl','.pickle','.npz','.bin','.checkpoint')]))
    ref=read(V/'acceptance/0011/conservation_failure_original_attempt02.json')
    state=ref['records'][1];age=pairs(state['age_state'])
    write('original_available_fields.json',dict(expected_root=ref['root_sha256'],
        expected_forecast=ref['forecast_sha256'],age_now=age.get('now'),age_cursor=age.get('cursor'),
        age_field_names=list(age),engine_field_names=list(pairs(state['engine_state'])),
        energy_field_names=list(pairs(state['energy_state'])),
        age_roundoff_count=len(age['roundoff_audit']),
        original_native_checkpoint_saved=False,
        boundary_warning='Captured engine/energy are at t=6; age ledger remains t=3; not one native root'))
    print('HISTORICAL_INSPECTION_SAVED',flush=True)
def construct():
    # Exclusive marker makes rerunning this command fail BEFORE another root.
    write('NEW_DIAGNOSTIC_ATTEMPT.json',dict(identity='0013_NEW_DIAGNOSTIC_ATTEMPT_01',
        started_utc=datetime.now(timezone.utc).isoformat(),allowed_root_constructions=1,
        expected_sha256=ROOT,actions_authorized=False,predictions_authorized=False,
        python=sys.version,executable=sys.executable,platform=platform.platform(),
        pythonhashseed=os.environ.get('PYTHONHASHSEED'),
        hash_randomization=sys.flags.hash_randomization,process_hash_probe=hash(('X0_1','f_bg')),
        original_0011_replay_claimed=False))
    previous.stage_manifest('c23f188ebc7bfcea9b04d53749d9111b48872ac46ac3eec84669263378de5ec7')
    start=time.perf_counter();live,rows=previous.real_fixture();g=old.guard()
    # Exactly the original attempt02 read-only view call order, no score_action.
    before=causal_view(live)
    fc=ForecastInput.from_current(causal_view(live).observation,T_s=30.,H_s=6.,mode='PERSIST')
    root=make_sanitized_root(live,fc,binding=g)
    with (A/'actual_root_hash_preimage.json').open('xb') as f:f.write(root.view.state_json.encode('utf-8'))
    assert hashlib.sha256((A/'actual_root_hash_preimage.json').read_bytes()).hexdigest()==root.view.state_sha256
    e=live.engine
    bindings=read(A/'historical_evidence_inventory.json') if False else vc.read_json(A/'historical_evidence_inventory.json')
    write('actual_root_summary.json',dict(identity='NEW_DIAGNOSTIC_ATTEMPT',
        expected_sha256=ROOT,actual_sha256=root.view.state_sha256,
        preimage=vc.binding(P,(A/'actual_root_hash_preimage.json').relative_to(P).as_posix()),
        forecast=asdict(fc),forecast_sha256=fc.sha256,historical_prefix_sha256=root.prefix_sha256,
        true_trace_sha256=e.trace.sha256(),true_trace=encode(e.trace),
        current_observation=encode(root.view.observation),
        live_engine_state=encode(e.business_state() | dict(delay=None,router=None)),
        age_observations=encode(e.age_observations),age_state=encode(vars(live.evaluator.age)),
        energy_state=encode(vars(live.evaluator.base.ledger)),
        executor_native_python_fields=encode(vars(e.executor)),
        atomic_receipts=encode(live.receipts),physical_sha256=live.physical_sha256,
        catalog_rows_loaded=len(rows),catalog_action_enumeration_performed=False,
        bindings=bindings['source_bindings']+bindings['physical_input_bindings'],
        before_sha256=before.state_sha256,root_build_wall_s=time.perf_counter()-start,
        simulated_until_s=e.now,add_submissions=0,prediction_branches=0,
        native_checkpoint_saved=False))
    # Save the observed evidence and only then perform the strict comparison.
    try:
        assert root.view.state_sha256==ROOT,'ROOT_BINDING_MISMATCH'
        outcome='ROOT_RECONSTRUCTION_PASS'
    except AssertionError as err:outcome='STOP_ROOT_BINDING_MISMATCH'
    write('root_comparison_stop.json',dict(status=outcome,expected_sha256=ROOT,
        actual_sha256=root.view.state_sha256,strict_equality=root.view.state_sha256==ROOT,
        evidence_saved_before_comparison=True,root_constructions=1,add_submissions=0,
        prediction_branches=0,original_failure_reproduced=False,
        N4_P0_engineering_pass=False,business_conservation_root_cause='UNRESOLVED'))
    print(canonical(dict(status=outcome,actual_sha256=root.view.state_sha256,simulated_until_s=e.now)),flush=True)
def compare():
    ref=read(V/'acceptance/0011/conservation_failure_original_attempt02.json')
    other=read(V/'acceptance/0011/conservation_failure_handle_attempt02.json')
    new=vc.read_json(A/'actual_root_summary.json');old_age=pairs(ref['records'][1]['age_state']);new_age=pairs(new['age_state'])
    differences=[];equal=[]
    for k in sorted(set(old_age)|set(new_age)):
        if old_age.get(k)==new_age.get(k):equal.append(k);continue
        a,b=old_age.get(k),new_age.get(k);first=None
        if isinstance(a,list) and isinstance(b,list):
            for i,(x,y) in enumerate(zip(a,b)):
                if x!=y:first=dict(index=i,original=x,current=y);break
        differences.append(dict(path='$.age.'+k,original_type=type(a).__name__,current_type=type(b).__name__,
            original_length=len(a) if hasattr(a,'__len__') else None,
            current_length=len(b) if hasattr(b,'__len__') else None,first_difference=first,
            exact_multiset_equal=(Counter(map(canonical,a))==Counter(map(canonical,b))
                                  if isinstance(a,list) and isinstance(b,list) else None)))
    old_obs=ref['records'][1]['age_observations'];new_obs=new['age_observations']
    prefix=old_obs[:len(new_obs)]
    write('ROOT_RECONSTRUCTION_DIFF.json',dict(
        expected_sha256=ROOT,actual_sha256=new['actual_sha256'],
        status=vc.read_json(A/'root_comparison_stop.json')['status'],
        original_and_handle_saved_records_exactly_equal=ref['records']==other['records'],
        original_age_now=old_age['now'],current_age_now=new_age['now'],
        age_fields_exactly_equal=equal,age_field_differences=differences,
        original_observations_prefix_length=len(prefix),new_observation_count=len(new_obs),
        observations_t0_t3_prefix_exactly_equal=prefix==new_obs,
        first_observation_difference=next((dict(index=i,original=x,current=y) for i,(x,y) in enumerate(zip(prefix,new_obs)) if x!=y),None),
        original_full_hash_preimage='NOT_SAVED_IN_INSPECTED_0011_EVIDENCE',
        original_native_root_recoverability='ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE',
        missing_original_t3_fields=['terminal_snapshot','terminal_events','terminal_history','energy','receipts',
            'whole_native_engine','whole_causal_view_state_json'],
        equal_fields_do_not_establish_full_root_equivalence=True,
        future_forecast_not_run=True,conservation_root_cause='UNRESOLVED'))
    print(canonical(dict(age_equal_fields=equal,age_differences=[{k:v for k,v in d.items() if k!='first_difference'} for d in differences],observations_prefix_equal=prefix==new_obs)),flush=True)
if __name__=='__main__':{'inspect':inspect,'construct':construct,'compare':compare}[sys.argv[1]]()
