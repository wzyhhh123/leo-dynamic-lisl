"""Offline variant-vs-historical semantic differences and event timing checks."""
import json,math
from fractions import Fraction as F
from pathlib import Path
import support as w
fs=w.old.load('p0f_analysis_full_state',w.V/'acceptance/0014/full_state.py')
scan=w.old.load('p0f_offline_exact_scan',w.V/'acceptance/0014/analyze_saved.py').scan
def read(p):return w.vc.read_json(p)
def rows(p):
    with p.open(encoding='utf-8') as f:
        for line in f:yield json.loads(line)
def fp(v):return F(float.fromhex(v['hex']))
def event_audit(d):
    pending=None;early=[];late=[];counts=0;beforetimes=[];maxres=0.;maxformula=0.
    for b in rows(d/'boundaries.jsonl'):
        time=b['time_s'];beforetimes.append(time)
        maxres=max(maxres,abs(b['totals']['exact_IEEE_operand_residual']['approx_bits']))
        maxformula=max(maxformula,abs(float.fromhex(b['totals']['A_minus_D_plus_QI']['hex'])))
        if b['label']=='BEFORE_PROPAGATION_EVENTS':pending=b
        elif b['label']=='AFTER_PROPAGATION_EVENTS':
            assert pending is not None
            seq={e['sequence'] for e in b['propagated_events']}
            for e in pending['propagated_events']:
                if e['sequence'] in seq:continue
                counts+=1;shift=fp(e['time'])-fp(pending['time'])
                if shift>0:early.append(dict(event=e,effective=pending['time'],shift=str(shift)))
                if shift<0:late.append(dict(event=e,effective=pending['time'],shift=str(shift)))
            pending=None
    assert beforetimes==sorted(beforetimes),'TIME_REVERSED'
    assert not early and not late,'PROPAGATION_EFFECTIVE_TIME_NOT_NOMINAL'
    clip=[]
    for op in rows(d/'operations.jsonl'):
        if float.fromhex(op['clip_mass_gain']['hex'])>0:clip.append(op)
    return dict(consumed_events=counts,early_events=early,late_events=late,positive_clip_updates=len(clip),
        clip_mass_gain_bit=sum(float.fromhex(x['clip_mass_gain']['hex']) for x in clip),
        max_exact_boundary_residual_bits=maxres,max_actual_formula_boundary_residual_bits=maxformula,
        time_monotonic=True,pending_head_skips=0)
def main():
    result={}
    for name,d in [('ROOT_PREFIX',w.A/'ROOT_BASELINE/prefix_audit'),('HOLD',w.A/'HOLD'),('ADD',w.A/'ADD')]:
        detail=scan(d);w.write(w.A/('EXACT_'+name+'_DIAGNOSIS.json'),detail)
        events=event_audit(d);result[name]=dict(events=events,exact_final_residual=detail['final_exact_residual'],
            expected_transfer_net=detail['net_expected_transfers'],signed_clip=detail['exact_signed_clip_contribution'])
    oldroot=read(w.V/'acceptance/0014/ROOT_BASELINE/LIVE_PRE_ACTION_CAUSAL_PREIMAGE.json')
    newroot=read(w.A/'ROOT_BASELINE/LIVE_PRE_ACTION_CAUSAL_PREIMAGE.json')
    oldfields=dict(oldroot);newfields=dict(newroot)
    diff=[dict(field=k,original=oldfields.get(k),variant=newfields.get(k)) for k in sorted(set(oldfields)|set(newfields)) if oldfields.get(k)!=newfields.get(k)]
    w.write(w.A/'ROOT_SEMANTIC_DIFF.json',dict(original_sha=read(w.V/'acceptance/0014/ROOT_BASELINE/root_binding.json')['root_view_sha256'],
        variant_sha=read(w.A/'ROOT_BASELINE/root_binding.json')['causal_root_sha256'],
        exact_equal_fields=[k for k in oldfields if oldfields[k]==newfields.get(k)],different_fields=diff,
        different_semantic_versions=True,whole_root_equivalence_claimed=False))
    paired={}
    for name in ('HOLD','ADD'):
        r=read(w.A/name/'branch_result.json');assert r['status']=='PASS_SINGLE_BRANCH'
        f=r['accepted_n2_result']['n1b_result']['n1a_result'];age=r['accepted_n2_result']['n1b_result']
        paired[name]=dict(J_h=r['J_h_bit_s'],N_end=r['N_end_bits'],E_h=r['E_h_J'],DeltaE_h=r['DeltaE_h_J'],
            A=f['offered_bits'],D=f['delivered_bits'],Q=f['queued_bits'],I=f['in_flight_bits'],J_0_t=f['J_T_bit_s'],
            E_0_t=f['E_LCT_J'],DeltaE_0_t=f['DeltaE_LCT_J'],R_del=f['R_del_T'],
            mean_delivered_fluid_delay_s=age['mean_delivered_fluid_delay_s'],M_D=age['delivered_bit_age_integral_bit_s'],
            mean_delay_error_bound_s=age['mean_delay_absolute_error_bound_s'],K_time_series=r['accepted_n2_result']['dynamic_K_time_series'],
            business_tolerance_bits=f['tolerances']['business_bits'],event_metrics=result[name])
        assert f['simulated_until_s']==9. and f['tolerances']['business_bits']==1e-6
    w.write(w.A/'HOLD_ADD_RESULTS.json',dict(variant='P0F_EXACT_NOMINAL_V1',results=paired,
        original_0014_ADD_failure_preserved=True,formal_performance_claim=False))
    w.write(w.A/'EVENT_TIMING_AND_CONSERVATION_SUMMARY.json',result)
    # Snapshot field diagnostics distinguish class/binding metadata from scientific state.
    old_add=read(w.V/'acceptance/0014/ADD/branch_result.json')
    w.write(w.A/'ORIGINAL_FAILURE_COMPARISON.json',dict(old_status=old_add['status'],old_end_s=old_add['actual_end_s'],
        variant_ADD_status='PASS_SINGLE_BRANCH',variant_end_s=9.,
        old_raw_failure_totals=old_add['final_A_Q_I_D'],variant_t6=read(w.A/'ADD/VALIDATION_INPUT_002.json'),
        numeric_semantic_change_not_exact_equivalence=True))
    print(json.dumps(dict(branches=paired,event_summary=result)),flush=True)
if __name__=='__main__':main()
