"""Compare saved JSON only. No engine/root construction or field writeback."""
import json,math,hashlib
from collections import Counter
from fractions import Fraction as F
import root_audit as w
def decode(x):
    if isinstance(x,dict) and 'fields' in x:return dict(x['fields'])
    return dict(x)
def main():
    old=w.read(w.V/'acceptance/0011/conservation_failure_original_attempt02.json')
    new=w.vc.read_json(w.A/'actual_root_summary.json')
    prior=w.vc.read_json(w.A/'ROOT_RECONSTRUCTION_DIFF.json')
    w.write('age_mixed_stage_comparison_attempt01.json',prior)
    a=decode(old['records'][1]['age_state']);b=decode(new['age_state'])
    logs_a=a['roundoff_audit'];logs_b=b['roundoff_audit'];k=len(logs_b)
    prefix=logs_a[:k];tail=logs_a[k:]
    tail_bound=sum((abs(F(dict(v)['difference_bits'])) for v in tail),F())
    count_a=Counter(map(w.canonical,prefix));count_b=Counter(map(w.canonical,logs_b))
    first=next((dict(index=i,original=x,current=y,time_rational=dict(x)['time'],
                    time_s=float(F(dict(x)['time']))) for i,(x,y) in enumerate(zip(prefix,logs_b)) if x!=y),None)
    obs=old['records'][1]['age_observations'];newobs=new['age_observations']
    scalar=next(dict(x)['after'] for x in reversed(obs[:len(newobs)]) if dict(x)['kind']=='INTERVAL')
    engine=decode(new['live_engine_state']);q=decode(engine['queues'])['bits'];i=decode(engine['in_flight'])['bits']
    actual_scalar=[['A',engine['arrived']],['D',engine['delivered']],['I',i],['Q',q]]
    scalar_equal=dict(scalar)==dict(actual_scalar)
    totals={name:math.fsum(float(v) for _,v in rows) for name,rows in actual_scalar}
    old_engine=decode(old['records'][1]['engine_state']);old_energy=decode(old['records'][1]['energy_state']);new_energy=decode(new['energy_state'])
    def through3(xs,timekey):return [x for x in xs if dict(x).get(timekey,float('inf'))<=3.]
    checks={}
    for key in ('timeline','route_changes','route_state_events','graph_event_sequence','terminal_event_sequence'):
        try:
            past=through3(old_engine[key],'time_s');present=through3(engine[key],'time_s')
            # Do not accept vacuous filtering on an unknown timestamp schema.
            checks[key]=dict(status='UNVERIFIABLE_TIMESTAMP_SCHEMA' if not past and old_engine[key] else 'COMPARED',
                original_filtered_count=len(past),new_filtered_count=len(present),exact_equal=past==present)
        except (TypeError,ValueError):checks[key]=dict(status='UNVERIFIABLE_TIMESTAMP_SCHEMA')
    extra=dict(obs[b['cursor']])
    extra_summary=dict(index=b['cursor'],kind=extra['kind'],time=extra.get('time'),
        emitted_event_count=len(extra.get('emitted_events',[])),old_rates_equal_new=extra.get('old_rates')==extra.get('new_rates'))
    reconstructed_bound=str(F(a['mass_error_bound'])-tail_bound)
    evidence=dict(source_snapshot_stage='POST_ADD_SAME_TIME_SETTLEMENT_THEN_T6_BASE_REJECTION',
        original_snapshot_now=a['now'],original_snapshot_cursor=a['cursor'],new_root_cursor=b['cursor'],
        new_observation_count=len(newobs),original_extra_observation=extra_summary,
        original_full_roundoff_count=len(logs_a),new_root_roundoff_count=k,
        historical_pre_submit_audit_prefix_length=k,
        prefix_extraction_basis='Identical complete t0-t3 observation prefix; appended t3 SCHEDULE; Atomic.submit calls advance_to(now); 22 FINAL plus one REPORTED_DELIVERY item at t3',
        historical_prefix_exact_multiset_equal=count_a==count_b,
        historical_prefix_exact_order_equal=prefix==logs_b,
        first_localizable_difference=first,
        tail_count=len(tail),tail_boundary_counts=dict(Counter(dict(v).get('boundary','REPORTED_DELIVERY') for v in tail)),
        tail_times=sorted({str(dict(v)['time']) for v in tail}),
        original_bound=a['mass_error_bound'],new_bound=b['mass_error_bound'],tail_absolute_bound=str(tail_bound),
        historical_bound_minus_post_submit_tail=reconstructed_bound,
        bound_after_offline_stage_adjustment_exact_equal=reconstructed_bound==b['mass_error_bound'],
        root_age_scientific_fields_exact_equal=prior['age_fields_exactly_equal'],
        raw_A_Q_I_D_at_last_t3_interval_exact_equal=scalar_equal,
        raw_A_Q_I_D_totals_bits=totals,
        observation_prefix_exact_equal=obs[:len(newobs)]==newobs,
        physical_input_digest_exact_equal=old['records'][1]['physical_input_sha256']==new['physical_sha256'],
        forecast_digest_exact_equal=old['forecast_sha256']==new['forecast_sha256'],
        energy_topology_samples_through_t3_exact_equal=through3(old_energy['samples'],'t_s')==through3(new_energy['samples'],'t_s'),
        event_prefix_comparisons=checks,
        no_old_or_new_native_state_modified=True,no_second_root_constructed=True,
        original_full_root_equivalence_claimed=False,
        original_0012_actual_root_hash_unverifiable=True)
    w.write('same_time_stage_and_audit_order_evidence.json',evidence)
    prior.update(original_age_snapshot_stage=evidence['source_snapshot_stage'],
        mixed_stage_differences_are_not_all_original_root_differences=True,
        stage_adjusted_audit_comparison=evidence,
        classifications={
            'A_INPUT':'REGISTERED_RAW_BYTES_UNCHANGED; PHYSICAL_AND_FORECAST_DIGESTS_EQUAL; original true-trace root checkpoint absent',
            'B_NETWORK':'A_Q_I_D_AT_T3_AND_OBSERVATION_PREFIX_EQUAL; full native root UNVERIFIABLE',
            'C_FIFO_ENERGY_HISTORY':'13 age fields equal; post-submit cursor/envelope differences explained; original full t3 energy UNVERIFIABLE',
            'D_ORDER':'Real service observation prefix equal; audit ordering difference CONFIRMED; old process seed UNVERIFIABLE',
            'E_HASH_METADATA':'roundoff_audit prefix is a permutation, order retained by original encode; confirmed fingerprint-sensitive difference, not proven exclusive cause',
            'F_MISSING_EVIDENCE':'Original hash preimage and native checkpoint absent; 0012 actual hash absent; faithful full native recovery not established'},
        first_localizable_difference=first,
        native_replay_decision='OPTION_2_ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE',
        exclusive_root_mismatch_cause='UNVERIFIABLE',conservation_root_cause='UNRESOLVED')
    # Only a new, unsealed report is updated; the initial coarse comparison is preserved above.
    with (w.A/'ROOT_RECONSTRUCTION_DIFF.json').open('w',encoding='utf-8',newline='\n') as f:
        json.dump(prior,f,ensure_ascii=True,sort_keys=True,indent=2);f.write('\n')
    print(w.canonical({k:evidence[k] for k in ('raw_A_Q_I_D_at_last_t3_interval_exact_equal',
        'historical_prefix_exact_multiset_equal','historical_prefix_exact_order_equal',
        'bound_after_offline_stage_adjustment_exact_equal','physical_input_digest_exact_equal',
        'forecast_digest_exact_equal','raw_A_Q_I_D_totals_bits')}),flush=True)
if __name__=='__main__':main()
