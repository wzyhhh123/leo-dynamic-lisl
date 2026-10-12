"""Failure-first immutable evidence persistence and censor-safe paired analysis."""
from pathlib import Path
import hashlib
import json
import math
from ..outage_metrics import derive_separated_outage_metrics


def file_sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def write_new_json(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(audit_json(value),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def audit_json(value):
    """Preserve invalid numeric evidence explicitly, without clamping state."""
    if isinstance(value,float) and not math.isfinite(value):
        return {'invalid_nonfinite_float':repr(value)}
    if isinstance(value,dict):return {k:audit_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [audit_json(v) for v in value]
    return value


def engine_invariants(engine,*,expected_trace_sha256,complete_threshold_bits,drain_limit_s,capacity_tolerance_bit_s):
    if not (math.isfinite(complete_threshold_bits) and complete_threshold_bits>0 and
            math.isfinite(drain_limit_s) and drain_limit_s>0 and
            math.isfinite(capacity_tolerance_bit_s) and capacity_tolerance_bit_s>=0):
        raise ValueError('EXPLICIT_FINITE_EVIDENCE_LIMITS_REQUIRED')
    errors={f:engine.arrived[f]-engine.delivered[f]-engine.queues.total(f)-engine.in_flight.total(f) for f in engine.by_id}
    limits={f:engine.abs_tol+engine.rel_tol*max(1.,abs(engine.arrived[f])) for f in engine.by_id}
    residual=engine.queues.total()+engine.in_flight.total()
    status='COMPLETE' if engine.now>=engine.trace.arrival_horizon_s and residual<=complete_threshold_bits else (
        'CENSORED_AT_DRAIN_LIMIT' if engine.now==drain_limit_s else 'PARTIAL')
    observed={
        'traffic_identity':{'pass':engine.trace.sha256()==expected_trace_sha256,'observed':engine.trace.sha256(),'expected':expected_trace_sha256},
        'work_conservation':{'pass':all(abs(errors[f])<=limits[f] for f in errors),'observed':errors,'frozen_tolerance':limits},
        'queue_nonnegative':{'pass':all(q>=0 for q in engine.queues.bits.values()),'observed_min':min(engine.queues.bits.values(),default=0),'limit':0},
        'inflight_nonnegative':{'pass':all(q>=0 for q in engine.in_flight.bits.values()),'observed_min':min(engine.in_flight.bits.values(),default=0),'limit':0},
        'capacity':{'pass':engine.max_capacity_violation<=capacity_tolerance_bit_s,'observed_max':engine.max_capacity_violation,'frozen_limit':capacity_tolerance_bit_s},
        'drain_status':{'pass':status in ('COMPLETE','CENSORED_AT_DRAIN_LIMIT'),'observed':status,'residual_backlog_bits':residual,
                        'complete_threshold_bits':complete_threshold_bits,'drain_limit_s':drain_limit_s},
        'no_decision_at_cutoff':{'pass':all(row['time_s']<drain_limit_s for row in engine.batch_results),
                                  'observed_times':[r['time_s'] for r in engine.batch_results],'exclusive_limit_s':drain_limit_s}}
    try:
        engine.executor.assert_invariants()
        observed['terminal_invariants']={'pass':True}
    except AssertionError as error:
        # A physical invariant failure is evidence, not permission to omit the
        # report by raising before persistence. Caller must stop on FAIL.
        observed['terminal_invariants']={'pass':False,'error':str(error)}
    observed['finite_state']={'pass':all(math.isfinite(x) for x in
        [engine.now,residual,engine.max_capacity_violation,*engine.arrived.values(),
         *engine.delivered.values(),*engine.objective_by_commodity.values(),
         *engine.queues.bits.values(),*engine.in_flight.bits.values()])}
    return {'status':'PASS' if all(r['pass'] for r in observed.values()) else 'FAIL',
            'items':observed,'scientific_outcome':status,'first_failure_time_s':engine.now if not all(r['pass'] for r in observed.values()) else None}


def persist_run_evidence(output_dir,engine,*,run_id,invariant_report,decision_records,candidate_audits,
                         code_hashes,input_hashes,failure=None,engineering_only,execution_binding=None):
    if engineering_only is not True and (engineering_only is not False or not isinstance(execution_binding,dict) or
        set(execution_binding)!={'execution_manifest_canonical_sha256','registered_run_configuration_sha256'} or
        any(not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h)
            for h in execution_binding.values())):
        raise ValueError('FORMAL_EVIDENCE_REQUIRES_EXPLICIT_EXECUTION_BINDING')
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False)
    outcome=invariant_report['scientific_outcome'] if invariant_report['status']=='PASS' and failure is None else 'EXECUTION_BLOCKED'
    # Persist the original validation/failure first, before deriving metrics.
    write_new_json(out/'invariant_report.json',invariant_report)
    write_new_json(out/'failure_summary.json',{'failure':failure,'status':outcome})
    total_arrived=math.fsum(engine.arrived.values());delivered=math.fsum(engine.delivered.values())
    j=math.fsum(engine.objective_by_commodity.values());residual=engine.queues.total()+engine.in_flight.total()
    separated=derive_separated_outage_metrics({'metrics':{'evaluation_end_s':engine.now,'outage_duration_s':engine.outage_duration_s},
        'route_state_events':engine.route_state_events,'transition_episodes':engine.transition_episodes,'terminal_event_sequence':engine.terminal_event_sequence})
    metrics={'run_id':run_id,'outcome':outcome,'evaluation_end_s':engine.now,'J_bit_s':j,
             'completion_time_s':engine.now if outcome=='COMPLETE' else None,
             'J_is_complete':outcome=='COMPLETE','mean_bit_delay_s':j/total_arrived if outcome=='COMPLETE' and total_arrived>0 else None,
             'arrived_bits':total_arrived,'raw_delivered_bits':delivered,'delivery_ratio':delivered/total_arrived if total_arrived else None,
             'residual_backlog_bits':residual,'peak_queue_bits':engine.max_queue,'queue_area_bit_s':engine.queue_area,
             'switch_count':engine.switch_count,'batch_count':engine.batch_count,'BBM_count':engine.BBM_count,'MBB_count':engine.MBB_count,
             'separated_outages':separated,'engineering_only':engineering_only}
    # All evidence comes before a caller raises/stops; never overwrite an attempt.
    write_new_json(out/'final_state_evidence.json',engine.canonical_state())
    write_new_json(out/'metrics.json',metrics)
    write_new_json(out/'action_timeline.json',decision_records)
    write_new_json(out/'transition_timeline.json',engine.terminal_event_sequence)
    write_new_json(out/'candidate_source_audit.json',candidate_audits)
    write_new_json(out/'timeseries.json',engine.timeline)
    provenance={'inputs':input_hashes,'code':code_hashes}
    if execution_binding is not None:provenance['execution_binding']=execution_binding
    write_new_json(out/'input_code_hashes.json',provenance)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    return metrics


def paired_contrast(left,right):
    if 'EXECUTION_BLOCKED' in (left['outcome'],right['outcome']):
        return {'status':'NOT_EVALUABLE_EXECUTION_FAILURE','left_status':left['outcome'],'right_status':right['outcome']}
    if left['outcome']!='COMPLETE' or right['outcome']!='COMPLETE':
        return {'status':'NOT_RANKED_CENSORED','left_status':left['outcome'],'right_status':right['outcome'],
                'left_residual_bits':left['residual_backlog_bits'],'right_residual_bits':right['residual_backlog_bits'],
                'left_delivery_ratio':left['delivery_ratio'],'right_delivery_ratio':right['delivery_ratio'],
                'left_completion_time_s':left.get('completion_time_s'),'right_completion_time_s':right.get('completion_time_s')}
    delta=left['J_bit_s']-right['J_bit_s']
    return {'status':'COMPLETE_PAIR','delta_J_left_minus_right':delta,
            'relative_J_left_vs_right':delta/right['J_bit_s'] if right['J_bit_s']!=0 else None}
