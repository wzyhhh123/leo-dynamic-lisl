"""Only the bound failing prefix, paired reading paths and finite controls."""
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
from fractions import Fraction as F
import json,math,traceback
from unittest.mock import patch
import audit_workflow as w
import controlled_cost as previous
from equivalence import bind_live
from runtime.n4_p0r_handle_reader import HandleReaderLease
from runtime.n4_p0 import (ForecastInput,make_sanitized_root,causal_view,encode,data_hash)
from runtime.n2_actions import Add,Hold
from runtime import n1a
from event_auditor import Auditor,fp,exact,exact_total

def reference_fifo(branch):
    # A separate ledger copy consumes already-recorded observations. The live
    # N1b ledger is not advanced after its N1a prerequisite rejects; no engine
    # advance or suppressed validation occurs on this offline reference path.
    age=branch.evaluator.age.clone();before=data_hash(vars(branch.evaluator.age))
    try:
        age.consume(branch.engine);status='PASS_OFFLINE_REFERENCE_ONLY';error=None
        per={}
        for c in age.commodities:
            k=c.commodity_id;q=sum((x.total() for (node,f),x in age.queue.items() if f==k),F())
            i=sum((s.mass() for (edge,f),rows in age.flight.items() if f==k for s in rows),F())
            per[k]=dict(A=exact(age.arrived[k]),D=exact(age.delivered[k]),Q=exact(q),I=exact(i),
                exact_conservation=exact(age.arrived[k]-age.delivered[k]-q-i))
        result=dict(status=status,time=str(age.now),cursor=age.cursor,per_commodity=per,
            queue_cohort_count=sum(len(x.rows) for x in age.queue.values()),flight_cohort_count=sum(len(v) for v in age.flight.values()),
            metrics=age.metrics(),live_ledger_time=str(branch.evaluator.age.now),live_ledger_cursor=branch.evaluator.age.cursor,
            source='offline copy only; metrics are not accepted N1b/P0 results')
    except Exception as error:result=dict(status='OFFLINE_REFERENCE_REJECTED',error=str(error),traceback=traceback.format_exc())
    assert before==data_hash(vars(branch.evaluator.age));return result

def run_case(live,guard,mode,action,label,reference=None):
    fc=ForecastInput.from_current(causal_view(live).observation,T_s=30.,H_s=6.,mode=mode)
    root=make_sanitized_root(live,fc,binding=guard)
    if reference:
        assert root.view.state_sha256==reference['root_sha256'],'ROOT_BINDING_MISMATCH'
        assert fc.sha256==reference['forecast_sha256'],'FORECAST_BINDING_MISMATCH'
    w.write(label+'/root_forecast_action.json',dict(root_view=asdict(root.view),forecast=asdict(fc),forecast_sha256=fc.sha256,
        historical_prefix_sha256=root.prefix_sha256,action=asdict(action),root_sha256=root.view.state_sha256,
        initial_state_reconstitution='Exact 0011 bound constructor; hash-verified; no serialized checkpoint claimed'))
    root.verify_isolation();before=causal_view(root.atomic);branch=root.atomic.clone();branch._verify();branch.evaluator.base.measure()
    directory=w.A/label;auditor=Auditor(branch.engine,branch.evaluator.age,directory);rejected=[]
    original_validate=n1a.validate_measurement
    def validate(value):
        try:return original_validate(value)
        except Exception as error:rejected.append(dict(error=str(error),measurement=deepcopy(value)));raise
    error=None;receipt=None;result=None
    try:
        with auditor.context(),patch.object(n1a,'validate_measurement',validate):
            auditor.boundary('INITIAL_t3')
            receipt=branch.submit(action);assert receipt['accepted']
            auditor.boundary('AFTER_ATOMIC_ACTION_t3')
            try:result=branch.advance_to(6.)
            except Exception as exc:error=str(exc)
            auditor.boundary('AT_STOP_t6')
    finally:auditor.close()
    assert before==causal_view(root.atomic),'DIAGNOSTIC_MUTATED_ROOT'
    raw_state=encode(branch.engine.business_state() | dict(delay=None,router=None))
    current=dict(error=error,records=([] if not rejected else [dict(kind='UNCHANGED_MEASUREMENT_REJECTED',error=error,
        measurement=rejected[-1]['measurement'],conservation_residual_bits=rejected[-1]['measurement']['offered_bits']-rejected[-1]['measurement']['delivered_bits']-rejected[-1]['measurement']['N_T_bits'])])+
        [dict(kind='BRANCH_STATE_AT_EXCEPTION' if error else 'BRANCH_STATE_AT_CONTROL_END',requested_time_s=6.,actual_time_s=branch.engine.now,
            error=error,engine_state=raw_state,age_state=encode(vars(branch.evaluator.age)),
            age_observations=encode(branch.engine.age_observations),energy_state=encode(vars(branch.evaluator.base.ledger)),
            physical_input_sha256=branch.physical_sha256)],root_sha256=root.view.state_sha256,forecast_sha256=fc.sha256)
    if reference:
        assert error==reference['error']=='BUSINESS_CONSERVATION_MISMATCH'
        assert current['records']==reference['records'],'ALL_0011_FAILED_STATE_FIELDS_MISMATCH'
    w.write(label+'/reproduction.json',current)
    w.write(label+'/event_summary.json',auditor.summary());w.write(label+'/fifo_reference.json',reference_fifo(branch))
    if result:w.write(label+'/accepted_prefix_result.json',result)
    print(label,'error',error,'operations',auditor.seq,'boundaries',auditor.boundary_seq,flush=True)
    return current,auditor.summary()

def main():
    previous.stage_manifest('c23f188ebc7bfcea9b04d53749d9111b48872ac46ac3eec84669263378de5ec7')
    ref=w.read_old('conservation_failure_original_attempt02.json');ref2=w.read_old('conservation_failure_handle_attempt02.json')
    assert ref['records']==ref2['records'] and ref['root_sha256']==ref2['root_sha256']
    live,_=previous.real_fixture();g=w.upstream.guard();action=Add(('X0_10','D2'),('X1_10','D1'),previous.SETUP)
    a,sa=run_case(live,g,'PERSIST',action,'persist_add_original',ref)
    with HandleReaderLease(w.upstream.old.dependencies()+[g],w.vc) as lease:
        live_opt=bind_live(live.clone(),lease);p0=lease.guard(g)
        b,sb=run_case(live_opt,p0,'PERSIST',action,'persist_add_handle',ref2)
        assert a==b and sa==sb,'PAIRED_AUDIT_NOT_EXACT'
        run_case(live_opt,p0,'PERSIST',Hold(),'persist_hold_control')
        run_case(live_opt,p0,'ZERO',action,'zero_add_control')
        # Minimal exact-time one-hop, finite test; no new real geometry scenario.
        f=w.upstream.setup(lease);c=f.synthetic(T=30.,connected=True,rate=4.,capacity=8.,
            segments=[previous.TrafficSegment(0.,20.,{'f':4.})]);c.advance_to(3.)
        run_case(c,p0,'PERSIST',Hold(),'analytic_control')
    w.write('reproduction_comparison.json',dict(status='PASS_EXACT_BOUND_0011_REPRODUCTION',
        root_sha256=a['root_sha256'],forecast_sha256=a['forecast_sha256'],
        all_failed_business_energy_FIFO_fields_equal=True,all_readonly_event_audit_fields_equal=True,
        failure_time_s=6.,original_error=a['error'],handle_error=b['error'],
        root_restoration_mode='bound deterministic reconstruction with original root and forecast SHA; 0011 did not persist native pickle checkpoint',
        simulations=5,full_catalog_enumerations=0,main_pilot_runs=0,kernel_changed=False,tolerance_changed=False))
if __name__=='__main__':main()
