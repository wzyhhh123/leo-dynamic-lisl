"""Recover instrumentation helper only; retain all ten completed predictions."""
import epoch_workflow as w
def main():
    prior=w.vc.read_json(w.A/'SMALL_INSTRUMENTED_HOLD.json')
    assert prior['error']['type']=='FrozenInstanceError'
    results={mode:w.vc.read_json(w.A/('SMALL_'+mode+'_SUMMARY.json')) for mode in ('PERSIST','ZERO')}
    for mode,d in results.items():
        assert len(d['rows'])==5 and all(r['error'] is None and r['result']['prediction_completed'] for r in d['rows'])
        assert d['decision']==w.select_success(d['rows'])
    assert results['PERSIST']['root_sha256']==results['ZERO']['root_sha256']
    assert results['PERSIST']['prefix_sha256']==results['ZERO']['prefix_sha256']
    assert w.vc.read_json(w.A/'SCORING_RULE_0015_CHECK.json')['status']=='PASS'
    live,built=w.load_live('TIMING');lease,live,g,startup=w.open_lease(live)
    try:
        fc=w.ForecastInput.from_current(w.causal_view(live).observation,T_s=30.,H_s=6.,mode='PERSIST')
        root=w.make_sanitized_root(live,fc,binding=g);root.verify_isolation();before=w.causal_view(root.atomic)
        plain=w.score(root,w.Hold());paired=w.score(root,w.Hold(),instrumented=True)
        w.write(w.A/'RECOVERED_TIMING_PAIR.json',dict(plain=plain,instrumented=paired))
        assert plain['error'] is None and paired['error'] is None
        old=next(x for x in results['PERSIST']['rows'] if x['result']['action']['kind']=='HOLD')
        assert w.stable(paired['result'])==w.stable(plain['result'])==w.stable(old['result'])
        assert before==w.causal_view(root.atomic)
        w.write(w.A/'SMALL_DOMAIN_ACCEPTANCE.json',dict(status='PASS',per_mode_branches=5,modes=['ZERO','PERSIST'],
            same_root_view=True,same_history_prefix=True,all_costs_from_real_fixed_horizon_execution=True,
            full_catalog_domain_claimed=False,instrumentation_result_exact_equal=True,
            plain_HOLD_wall_s=plain['actual_wall_s'],instrumented_HOLD_wall_s=paired['actual_wall_s'],
            observed_timer_overhead_s=paired['actual_wall_s']-plain['actual_wall_s'],startup_s=startup,root_build_s=built,
            initial_instrumentation_helper_error_retained=True,helper_fix='Remove attempted frozen guard dataclass setattr; retain immutable guard verification; wrap only mutable cloned instances',
            extra_successful_timing_branches=2,extra_failed_instrumentation_attempts=1,main_pilot_runs=0))
        print('SMALL_DOMAIN_PASS',flush=True)
    finally:lease.__exit__(None,None,None)
if __name__=='__main__':main()
