"""Compare persisted JSON evidence with identical serialization types."""
import epoch_workflow as w
def main():
    pair=w.vc.read_json(w.A/'OBSERVER_PROFILE_TIMING_PAIR.json')
    plain=pair['plain'];prof=pair['instrumented']
    old=w.vc.read_json(w.A/'small/PERSIST/03_HOLD_.json')
    assert plain['error'] is None and prof['error'] is None
    assert w.stable(plain['result'])==w.stable(prof['result'])==w.stable(old['result'])
    assert plain['state_checks']==prof['state_checks']==old['state_checks']
    results={m:w.vc.read_json(w.A/('SMALL_'+m+'_SUMMARY.json')) for m in ('PERSIST','ZERO')}
    for d in results.values():assert len(d['rows'])==5 and d['decision']==w.select_success(d['rows'])
    assert results['PERSIST']['root_sha256']==results['ZERO']['root_sha256']
    assert results['PERSIST']['prefix_sha256']==results['ZERO']['prefix_sha256']
    assert w.vc.read_json(w.A/'SCORING_RULE_0015_CHECK.json')['status']=='PASS'
    w.write(w.A/'SMALL_DOMAIN_ACCEPTANCE.json',dict(status='PASS',per_mode_branches=5,modes=['ZERO','PERSIST'],
        same_root_view=True,same_history_prefix=True,all_costs_from_real_fixed_horizon_execution=True,
        full_catalog_domain_claimed=False,instrumentation_result_exact_equal=True,
        comparison='Exact persisted JSON fields, same serialization for all branches; timings only excluded; no numerical tolerance; final state hashes and post-wrapper state checks equal',
        evidence=w.bind(w.A/'OBSERVER_PROFILE_TIMING_PAIR.json'),
        plain_HOLD_wall_s=plain['actual_wall_s'],instrumented_HOLD_wall_s=prof['actual_wall_s'],
        observed_timer_overhead_s=prof['actual_wall_s']-plain['actual_wall_s'],
        helper_errors_retained=['FrozenInstanceError','wrapper_state_hash_difference','native_tuple_vs_persisted_JSON_list_comparison'],
        extra_successful_timing_branches=4,extra_failed_instrumentation_attempts=1,main_pilot_runs=0))
    print('SMALL_DOMAIN_PASS_EXACT_SERIALIZED_FIELDS',flush=True)
if __name__=='__main__':main()
