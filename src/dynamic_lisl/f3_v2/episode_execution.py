"""Shared episode orchestration on the existing Gate D2 kernel.

Formal callers must first pass the independent registered-matrix authorization
gate. This module does not load/freeze a contract or invent simulation inputs.
"""
from pathlib import Path
import time

from .service_adapter import BatchCadenceAdapter
from .batch_rollout import JointRolloutController
from .evidence import engine_invariants,persist_run_evidence,write_new_json


def execute_episode(engine,validator,schedule,source,proposer,controller,*,
                            output_dir,fixture_id,input_hashes,code_hashes,
                            capacity_tolerance_bit_s, engineering_only, execution_binding=None,
                            before_persistence=None, wall_limit_s=None, epoch_audit_validator=None):
    if type(engineering_only) is not bool:
        raise ValueError('EXPLICIT_EPISODE_SCOPE_REQUIRED')
    if engineering_only and (not isinstance(fixture_id,str) or not fixture_id.startswith('ENGINEERING-')):
        raise ValueError('ENGINEERING_FIXTURE_ID_REQUIRED_NOT_REGISTERED_RUN')
    if not engineering_only and not execution_binding:
        raise ValueError('REGISTERED_EXECUTION_BINDING_REQUIRED')
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False)
    write_new_json(out/('fixture_contract.json' if engineering_only else 'execution_contract.json'),{'scope':'ENGINEERING_ONLY' if engineering_only else 'REGISTERED_F3_V2',
        'fixture_id':fixture_id,'schedule':schedule.__dict__,
        'search_budget':proposer.budget.__dict__,'controller_id':controller.controller_id,
        'scientific_contract_frozen':not engineering_only,'registered_experiment_started':not engineering_only,
        'execution_binding':execution_binding,
        'input_hashes':input_hashes,'code_hashes':code_hashes})
    records=[];audits=[];epoch_validations=[];failure=None;adapter=None
    trace_hash=engine.trace.sha256();started=time.perf_counter()

    def check_wall():
        if wall_limit_s is not None and time.perf_counter()-started>wall_limit_s:
            raise RuntimeError('REGISTERED_EPISODE_OPERATIONAL_WALL_LIMIT')

    def observe(live,root,horizon):
        check_wall()
        index=len(records);before=live.canonical_state_sha256();t=live.now
        start=time.perf_counter();members,audit=source(live,validator)
        source_wall=time.perf_counter()-start;audits.append({'time_s':t,**audit})
        check_wall()
        if before!=live.canonical_state_sha256():raise AssertionError('CANDIDATE_SOURCE_CHANGED_LIVE_ENGINE')
        start=time.perf_counter()
        pool=proposer.propose(live.executor,members,decision_root_sha256=root)
        proposer_wall=time.perf_counter()-start
        write_new_json(out/('epoch_%04d_input.json'%index),{'time_s':t,'root_sha256':root,
            'H_decision_root':before,'horizon_s':horizon,'pool':pool.public_document(),
            'source_audit':audits[-1]})
        if epoch_audit_validator is not None:
            validation = epoch_audit_validator(live, pool, audit)
            epoch_validations.append(validation)
            write_new_json(out/('epoch_%04d_invariants.json'%index), validation)
            if validation['status'] != 'PASS':
                raise AssertionError('EPOCH_CANDIDATE_RESOURCE_INVARIANT_FAILURE')
        start=time.perf_counter()
        decision=(controller.observe(live,pool,horizon_s=horizon)
                  if isinstance(controller,JointRolloutController) else controller.observe(live,pool))
        check_wall()
        after=live.canonical_state_sha256()
        if after!=before:raise AssertionError('CONTROLLER_CHANGED_LIVE_ENGINE')
        if decision.action.batch_id not in {a.batch_id for a in pool.actions}:
            raise AssertionError('CONTROLLER_SELECTED_OUTSIDE_COMMON_POOL')
        row={'time_s':t,'H_decision_root':before,'H_post_observe':after,
            'action':decision.action.to_dict(),'pool_sha256':pool.pool_sha256,
            'controller_metadata':decision.metadata,'wall_s':{'source':source_wall,
                'proposer':proposer_wall,'observe':time.perf_counter()-start}}
        records.append(row);write_new_json(out/('epoch_%04d_decision.json'%index),row)
        return decision.action

    try:
        adapter=BatchCadenceAdapter(engine,schedule,validator)
        result=adapter.run(observe)
        check_wall()
    except Exception as error:
        failure={'type':type(error).__name__,'reason':str(error),'time_s':engine.now,
            'completed_controller_observations':len(records),'do_not_continue':True}
        branch_pool=getattr(controller,'branch_pool',None)
        if branch_pool is not None:
            failure['worker_failure_evidence']=branch_pool.last_failure_evidence
        result=None
    if before_persistence is not None:
        try:before_persistence()
        except Exception as error:
            failure={'type':type(error).__name__,'reason':str(error),'time_s':engine.now,
                'previous_failure':failure,'do_not_continue':True}
    invariant=engine_invariants(engine,expected_trace_sha256=trace_hash,
        complete_threshold_bits=schedule.complete_threshold_bits,drain_limit_s=schedule.simulation_end_s,
        capacity_tolerance_bit_s=capacity_tolerance_bit_s)
    if epoch_audit_validator is not None:
        invariant['items']['epoch_candidate_resource_checks'] = {
            'pass': all(v['status'] == 'PASS' for v in epoch_validations),
            'observations': epoch_validations}
        if not invariant['items']['epoch_candidate_resource_checks']['pass']:
            invariant['status'] = 'FAIL'
    metrics=persist_run_evidence(out/'run_evidence',engine,run_id=fixture_id,
        invariant_report=invariant,decision_records=records,candidate_audits=audits,
        code_hashes=code_hashes,input_hashes=input_hashes,failure=failure,engineering_only=engineering_only,execution_binding=execution_binding)
    report={'status':('ENGINEERING_EPISODE_PASS' if engineering_only else 'REGISTERED_EPISODE_EXECUTION_PASS') if invariant['status']=='PASS' and failure is None else 'FAIL_STOP',
        'fixture_id':fixture_id,'engineering_only':engineering_only,'scientific_outcome':metrics['outcome'],
        'wall_s':time.perf_counter()-started,'failure':failure,
        'checkpoints':adapter.checkpoints if adapter is not None else [],
        'registered_P1_v2_executed':not engineering_only,'P2_started':False,'RL_started':False}
    write_new_json(out/'report.json',report)
    from .evidence import file_sha256
    write_new_json(out/'artifact_hashes.json',{p.relative_to(out).as_posix():file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    return report
