"""Clean-process P0E reconstruction. Only two forecast branches authorized."""
import os,sys,json,hashlib,time,traceback,platform
from pathlib import Path
from dataclasses import asdict
from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import patch
from fractions import Fraction as F
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(A),str(V/'acceptance/0011'),str(V),str(P/'src')]
import workflow as old
import controlled_cost as builder
import full_state as fs
from runtime.n4_p0 import make_sanitized_root,ForecastInput,causal_view,encode,PilotCost
from runtime.n2_actions import Hold,Add,Setup
from runtime.n2_controller import AtomicTopologyController
from runtime import n1a
vc=old.vc
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='ae00610b223f9f5172f5290ade4a382bb2d54e38a79d6b473c41247f7a6ec61a'
SCENE='P0E_0014_NEW_160_PERSIST_T3_SEED1414'
audmod=old.load('p0e_bound_readonly_auditor',V/'acceptance/0012/event_auditor.py')
def write(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False);f.write('\n')
def info(path):
    p=Path(path);return dict(path=str(p),byte_count=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def verify_recipe():
    d=vc.read_json(A/'replay_recipe.json')
    assert os.environ.get('PYTHONHASHSEED')==d['environment']['PYTHONHASHSEED'],'PROCESS_HASH_SEED_MISMATCH'
    assert sys.version==d['environment']['python_version'],'PYTHON_VERSION_MISMATCH'
    assert sys.executable.lower()==d['environment']['python_executable'].lower(),'PYTHON_EXECUTABLE_MISMATCH'
    for row in d['bound_files']:
        assert info(row['path'])==row,'REPLAY_FILE_BINDING_MISMATCH:'+row['path']
    vc.load_expected(P,ORIGIN,PARENT)
    builder.stage_manifest('c23f188ebc7bfcea9b04d53749d9111b48872ac46ac3eec84669263378de5ec7')
    return d
def build(directory,*,audit_prefix):
    verify_recipe();auditors=[];original=AtomicTopologyController.advance_to
    def advance(obj,t):
        assert t==3. and obj.engine.now==0.,'RECIPE_UNEXPECTED_INITIAL_ADVANCE'
        directory.mkdir(parents=True,exist_ok=True)
        audit=audmod.Auditor(obj.engine,obj.evaluator.age,directory);auditors.append(audit)
        try:
            with audit.context():audit.boundary('RECIPE_INITIAL_t0');out=original(obj,t);audit.boundary('RECIPE_PRE_ACTION_t3')
            return out
        finally:audit.close()
    if audit_prefix:
        with patch.object(AtomicTopologyController,'advance_to',advance):live,rows=builder.real_fixture()
    else:live,rows=builder.real_fixture()
    if auditors:write(directory/'summary.json',auditors[0].summary())
    fc=ForecastInput.from_current(causal_view(live).observation,T_s=30.,H_s=6.,mode='PERSIST')
    root=make_sanitized_root(live,fc,binding=old.guard())
    assert root.forecast.horizon_s==6. and root.forecast.end_s==9.
    return live,root,rows
def snapshot(directory,name,obj):
    view=causal_view(obj);state=fs.capture(obj)
    write(directory/(name+'_FULL_STATE.json'),state)
    with (directory/(name+'_CAUSAL_PREIMAGE.json')).open('xb') as f:f.write(view.state_json.encode('utf-8'))
    result=dict(stage=name,time_s=obj.engine.now,complete_typed_state_sha256=fs.sha(state),
        causal_state_sha256=view.state_sha256,age_cursor=obj.evaluator.age.cursor,
        age_now=str(obj.evaluator.age.now),age_audit_entries=len(obj.evaluator.age.roundoff_audit),
        energy_now=obj.evaluator.base.ledger.now,energy_cursor=obj.evaluator.base.ledger.cursor,
        terminal_log_entries=len(obj.engine.executor.log),observation_count=len(obj.engine.age_observations),
        energy_metrics=obj.evaluator.base.ledger.metrics(),age_metrics=obj.evaluator.age.metrics(),
        source='EXECUTABLE_RECONSTRUCTION_NOT_JSON_CHECKPOINT_DECODER')
    write(directory/(name+'_SUMMARY.json'),result)
    return state,result
def baseline():
    d=A/'ROOT_BASELINE';d.mkdir(exist_ok=False)
    live,root,rows=build(d/'prefix_audit',audit_prefix=True)
    _,lv=snapshot(d,'LIVE_PRE_ACTION',live);_,rt=snapshot(d,'SANITIZED_PRE_ACTION',root.atomic)
    write(d/'ROOT_FULL_STATE.json',fs.capture(root))
    write(d/'root_binding.json',dict(scenario_id=SCENE,original_0011_replay=False,
        live=lv,sanitized=rt,root_view_sha256=root.view.state_sha256,
        forecast=asdict(root.forecast),forecast_sha256=root.forecast.sha256,
        prefix_sha256=root.prefix_sha256,root_full_state_sha256=fs.sha(fs.capture(root)),
        true_trace_sha256=live.engine.trace.sha256(),catalog_rows_loaded=len(rows),catalog_enumerated=False,
        recipe_binding=info(A/'replay_recipe.json'),worker_binding=info(Path(__file__)),
        environment=dict(python=sys.version,hash_seed=os.environ.get('PYTHONHASHSEED'),platform=platform.platform()),
        add_action=asdict(Add(('X0_10','D2'),('X1_10','D1'),Setup(.5,.5,.5))),
        state_format=fs.SCHEMA,simulation_actions_submitted=0))
    print('BASELINE_ROOT_SAVED',flush=True)
def validate_reconstruction(live,root,directory):
    expected=vc.read_json(A/'ROOT_BASELINE/root_binding.json')
    current=dict(LIVE_PRE_ACTION=fs.capture(live),SANITIZED_PRE_ACTION=fs.capture(root.atomic),ROOT=fs.capture(root))
    reports={};ok=True
    for key,value in current.items():
        p=A/'ROOT_BASELINE'/('ROOT_FULL_STATE.json' if key=='ROOT' else key+'_FULL_STATE.json')
        before=vc.read_json(p);difference=fs.first_diff(before,value)
        reports[key]=dict(exact_every_field_equal=difference is None,first_difference=difference,
            expected_sha256=fs.sha(before),actual_sha256=fs.sha(value))
        ok=ok and difference is None
    equal_hashes=dict(live_causal=causal_view(live).state_sha256==expected['live']['causal_state_sha256'],
        sanitized_causal=causal_view(root.atomic).state_sha256==expected['sanitized']['causal_state_sha256'],
        root_view=root.view.state_sha256==expected['root_view_sha256'],
        forecast=root.forecast.sha256==expected['forecast_sha256'],prefix=root.prefix_sha256==expected['prefix_sha256'])
    ok=ok and all(equal_hashes.values())
    write(directory/'reconstruction_validation.json',dict(status='ROOT_RECONSTRUCTION_PASS' if ok else 'STOP_RECONSTRUCTION_MISMATCH',
        scenario_id=SCENE,complete_state_comparisons=reports,hash_bindings=equal_hashes,
        clean_process=True,pid=os.getpid(),hash_seed=os.environ['PYTHONHASHSEED'],prediction_executed=False))
    assert ok,'STOP_RECONSTRUCTION_MISMATCH'
    return expected
def rebuild():
    d=A/'CLEAN_REBUILD';d.mkdir(exist_ok=False)
    live,root,_=build(d,audit_prefix=False);validate_reconstruction(live,root,d)
    snapshot(d,'LIVE_PRE_ACTION',live);snapshot(d,'SANITIZED_PRE_ACTION',root.atomic)
    write(d/'ROOT_FULL_STATE.json',fs.capture(root));print('ROOT_RECONSTRUCTION_PASS',flush=True)
def branch(kind):
    gate=vc.read_json(A/'CLEAN_REBUILD/reconstruction_validation.json')
    assert gate['status']=='ROOT_RECONSTRUCTION_PASS','RECONSTRUCTION_PREREQUISITE'
    d=A/kind;d.mkdir(exist_ok=False)
    live,root,_=build(d,audit_prefix=False);validate_reconstruction(live,root,d)
    action=Hold() if kind=='HOLD' else Add(('X0_10','D2'),('X1_10','D1'),Setup(.5,.5,.5))
    c=root.atomic.clone();before_root=fs.sha(fs.capture(root))
    snapshot(d,'PRE_ACTION',c);initial=c.evaluator.base.measure()
    # Explicit original N2 validator probes only the single requested action.
    plan=c.validator.validate(c.engine.executor,action)
    write(d/'action_legality.json',dict(accepted=plan['accepted'],reason=plan['reason'],mode=plan.get('mode'),
        requested_action=asdict(action),full_catalog_enumeration=False))
    assert plan['accepted'],'SPECIFIED_ACTION_NOT_LEGAL'
    audit=audmod.Auditor(c.engine,c.evaluator.age,d);validation=n1a.validate_measurement
    checks=[]
    def validate(value):
        checks.append(dict(time_s=value['simulated_until_s'],A=value['offered_bits'],D=value['delivered_bits'],
            Q=value['queued_bits'],I=value['in_flight_bits'],N=value['N_T_bits'],
            residual_A_minus_D_N=value['offered_bits']-value['delivered_bits']-value['N_T_bits'],
            residual_actual_assertion=value['offered_bits']-(value['delivered_bits']+value['N_T_bits']),
            tolerance=value['tolerances']['business_bits']))
        # File is flushed and closed BEFORE the unchanged validator executes.
        write(d/('VALIDATION_INPUT_'+str(len(checks)).zfill(3)+'.json'),value)
        return validation(value)
    error=None;receipt=None;measured=None;completed=[]
    try:
        with audit.context(),patch.object(n1a,'validate_measurement',validate):
            audit.boundary('PRE_ACTION_t3')
            receipt=c.submit(action);write(d/'receipt.json',receipt)
            audit.boundary('POST_ACTION_t3');snapshot(d,'POST_ACTION',c)
            for cut in (6.,9.):
                measured=c.advance_to(cut);completed.append(cut)
                audit.boundary('PREDICTION_CHECKPOINT_'+str(cut))
                snapshot(d,'CHECKPOINT_'+str(int(cut)),c)
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(),
            actual_time_s=c.engine.now,age_time_s=str(c.evaluator.age.now),energy_time_s=c.evaluator.base.ledger.now)
        write(d/'STOP_EXCEPTION.json',error)
        # Capture unchanged rejection state; do not consume or advance a stale age ledger.
        audit.boundary('UNCHANGED_EXCEPTION_STATE');snapshot(d,'STOP_STATE',c)
    finally:audit.close()
    write(d/'audit_summary.json',audit.summary())
    write(d/'validation_residual_timeline.json',checks)
    assert before_root==fs.sha(fs.capture(root)),'BRANCH_MUTATED_ROOT'
    outcome=dict(scenario_id=SCENE,original_0011_replay=False,action=kind,
        status='COMPLETED_SINGLE_BRANCH' if error is None else 'STOP_'+error['message'],
        prediction_start_s=3.,requested_horizon_s=6.,requested_end_s=9.,actual_end_s=c.engine.now,
        completed_checkpoints=completed,error=error,root_unchanged=True,recipe_root_sha256=root.view.state_sha256,
        forecast_sha256=root.forecast.sha256,final_energy=c.evaluator.base.ledger.metrics(),
        age_now=str(c.evaluator.age.now),age_cursor=c.evaluator.age.cursor,
        partial_age_state_not_accepted_as_final=error is not None,
        final_A_Q_I_D=audit.current_totals(),N4_P0_engineering_pass=False,scientific_gate_pass=False)
    if error is None:
        final=measured['n1b_result']['n1a_result'];j=final['J_T_bit_s']-initial['J_T_bit_s']
        energy=final['E_LCT_J']-initial['E_LCT_J'];delta=energy-1600.*6.
        outcome.update(J_h_bit_s=j,N_end_bits=final['N_T_bits'],E_h_J=energy,DeltaE_h_J=delta,
            cost_bit_s=j+6.*final['N_T_bits']+1000.*delta,accepted_n2_result=measured)
    write(d/'branch_result.json',outcome)
    print(json.dumps(dict(branch=kind,status=outcome['status'],end_s=c.engine.now)),flush=True)
if __name__=='__main__':
    command=sys.argv[1]
    {'baseline':baseline,'rebuild':rebuild,'HOLD':lambda:branch('HOLD'),'ADD':lambda:branch('ADD')}[command]()
