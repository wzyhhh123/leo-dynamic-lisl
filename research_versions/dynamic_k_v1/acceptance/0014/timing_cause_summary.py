"""Offline event bias / clip comparison and compact engineering checkpoints."""
import json
from fractions import Fraction as F
from pathlib import Path
A=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def exact(v):return dict(rational=str(v),approx=float(v))
def write(name,value):
    with (A/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def main():
    timing=read(A/'PROPAGATION_EVENT_TIMING_AUDIT.json')['reports']['ADD']
    detail=read(A/'EXACT_ADD_DIAGNOSIS.json');rows=[]
    for g in detail['per_state_commodity_edge']:
        if g['kind']!='I' or not g['signed_clip']['approx']:continue
        key=json.dumps(g['key']);bias=timing['exact_arrival_pulse_bias_by_edge'].get(key,dict(rational='0',approx=0.))
        clip=-F(g['signed_clip']['rational']);pulse=F(bias['rational'])
        rows.append(dict(edge_commodity=g['key'],clip_mass_gain=exact(clip),early_event_arrival_bias=exact(pulse),
            clip_minus_event_bias=exact(clip-pulse)))
    first_edge=[['X0_9','X0_10'],'f_hot'];first=next(r for r in rows if r['edge_commodity']==first_edge)
    write('TIMING_CAUSE_CLASSIFICATION.json',dict(
        scenario_id='P0E_0014_NEW_160_PERSIST_T3_SEED1414',
        root_cause_for_this_new_scenario='EARLY_PROPAGATION_RATE_EVENT_COALESCING_CAUSES_ARRIVAL_OVERRUN_THEN_INFLIGHT_ZERO_CLAMP',
        evidence_level='OBSERVED_CALLS_AND_EXACT_BINARY_RATIONAL_DECOMPOSITION',
        unchanged_core_condition='propagation_agenda[0].time_s <= self.now + 1e-12',
        observed_early_events=len(timing['early_events']),observed_late_events=len(timing['late_events']),
        first_threshold_edge=first,per_edge_bias_and_clip=rows,
        event_bias_replaces_production_state=False,
        original_0011_root_replay_or_exclusive_root_cause_claimed=False,
        classifications=dict(A='Ordinary floating update errors measured separately; not the dominant contribution',
            B='A-(D+N) cancellation changes reported residual slightly; exact signed fsum remains beyond 1e-6',
            C='Different aggregate formulas measured; none cures this failure',
            D='18 scheduled rate events processed before their nominal timestamp, with exact per-edge pulse-bias evidence',
            E='Observed numerical mass gain from I=max(0,total), not an unexplained duplicate transfer; complete expected-transfer net is zero',
            F='D2 local abs tolerance .001 vs P0 global 1e-6; original stricter P0 rejection valid'),
        repair_requires_separate_kernel_authorization=True,repair_implemented=False,tolerance_changed=False))
    core_hold=read(A/'HOLD/branch_result.json');core_add=read(A/'ADD/branch_result.json')
    cases=[]
    for name,stage,time in [('HOLD','CHECKPOINT_6',6.),('HOLD','CHECKPOINT_9',9.),('ADD','STOP_STATE',6.)]:
        snap=read(A/name/(stage+'_SUMMARY.json'))
        if name=='HOLD':
            candidates=[p for p in sorted((A/name).glob('VALIDATION_INPUT_*.json')) if read(p)['simulated_until_s']==time]
            val=read(candidates[-1]);n2=core_hold.get('accepted_n2_result') if time==9. else None
        else:
            vals=sorted((A/name).glob('VALIDATION_INPUT_*.json'));val=read(vals[-1]);n2=None
        age=snap['age_metrics'];valid=name=='HOLD'
        cases.append(dict(action=name,time_s=time,accepted_measurement=valid,
            A=val['offered_bits'],D=val['delivered_bits'],Q=val['queued_bits'],I=val['in_flight_bits'],N=val['N_T_bits'],
            J_0_t_bit_s=val['J_T_bit_s'],R_del=val['R_del_T'],E_0_t_J=val['E_LCT_J'],DeltaE_0_t_J=val['DeltaE_LCT_J'],
            K_time_series=val['K_time_series'],execution_dwell_s=val['five_execution_state_dwell_s'],
            mean_delivered_fluid_delay_s=(n2['n1b_result']['mean_delivered_fluid_delay_s'] if n2 else age['mean_delivered_fluid_delay_s']) if valid else None,
            mean_delay_error_bound_s=n2['n1b_result']['mean_delay_absolute_error_bound_s'] if n2 else None,
            M_D_bit_s=age['delivered_bit_age_integral_bit_s'] if valid else None,
            age_time_s=snap['age_now'],age_cursor=snap['age_cursor'],
            note='ADD is rejected raw observation at t6; age ledger remains t3, final delay unavailable' if not valid else 'ENGINEERING_CHECKPOINT'))
    write('COMPACT_BRANCH_CHECKPOINTS.json',dict(same_intended_horizon=True,full_horizon_pair_comparison_valid=False,
        HOLD_completed_to_s=9.,ADD_stopped_at_s=6.,checkpoints=cases,
        paper_performance_comparison_claimed=False))
    print(json.dumps(dict(first_threshold_edge=first,early_events=len(timing['early_events']),checkpoints=[
        {k:r[k] for k in ('action','time_s','accepted_measurement','A','D','N','J_0_t_bit_s','E_0_t_J','DeltaE_0_t_J','mean_delivered_fluid_delay_s')} for r in cases])),flush=True)
if __name__=='__main__':main()
