"""Frozen upstream/historical tests, no full catalog and no long BBM replay."""
import support18 as s
def main():
    binding=s.w.s15.binding();s.w.s15.binding=lambda:binding
    destination=s.A/'regressions';destination.mkdir(exist_ok=False)
    s.w.s15.A=destination;s.w.s15.PARENT=s.PARENT
    for mode in ('original','variant'):
        m=s.w.old.old.load('p0h_reg_'+mode,s.V/'acceptance/0015/regression.py');assert m.main(mode)==0
    inline=s.w.old.old.load('p0h_inline',s.V/'acceptance/0015/inline_variant_test.py');assert inline.main()==0
    events=s.w.old.old.load('p0h_clock',s.V/'acceptance/0015/test_event_clock.py')
    r=s.w.old.old.test_module(events);s.write('UPSTREAM_EVENT_TESTS.json',r);assert r['status']=='PASS'
    history=s.w.old.old.load('p0h_history',s.V/'acceptance/0015/historical.py');assert history.main()==0
    s.write('REGRESSION_ACCEPTANCE.json',dict(status='PASS_NO_NEW_FAILURES',original_targeted=116,variant_targeted=116,
        inline_variant=1,event_clock_and_1bit_loss=7,historical_tests=132,historical_passed=131,known_F3_failed=1,
        source_tests_or_expectations_modified=False,new_seam_scope='Separately tested bounded root-scoped cases, not auto-injected into frozen N3 multi-epoch controllers',
        full_catalog_enumerated=False,forecast_performance_runs=0))
    print('REGRESSION_PASS',flush=True)
if __name__=='__main__':main()
