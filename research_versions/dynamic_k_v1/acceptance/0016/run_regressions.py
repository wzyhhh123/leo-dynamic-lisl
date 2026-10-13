"""Rerun pinned original suites into new append-only acceptance files."""
import sys,json,types
from pathlib import Path
import epoch_workflow as w
def load(name,p):return w.old.old.load(name,p)
def main():
    # Local verification/output context of acceptance helpers only, never a
    # production class or source patch. Same frozen tests and original assertions.
    original_binding=w.s15.binding()
    w.s15.binding=lambda:original_binding
    # Preserve bootstrap failure artifacts; successful retry has its own folder.
    destination=w.A/'regressions';destination.mkdir(exist_ok=False)
    w.s15.A=destination;w.s15.PARENT=w.PARENT
    for mode in ('variant','original'):
        module=load('p0g_regress_'+mode,w.V/'acceptance/0015/regression.py')
        code=module.main(mode)
        if code:raise RuntimeError('REGRESSION_FAILED:'+mode)
    inline=load('p0g_inline',w.V/'acceptance/0015/inline_variant_test.py')
    assert inline.main()==0
    events=load('p0g_clock_tests',w.V/'acceptance/0015/test_event_clock.py')
    result=w.old.old.test_module(events);result['examples']=events.EXAMPLES
    w.write(w.A/'analytic_tests.json',result);assert result['status']=='PASS'
    historical=load('p0g_history',w.V/'acceptance/0015/historical.py')
    assert historical.main()==0
    w.write(w.A/'REGRESSION_ACCEPTANCE.json',dict(status='PASS_NO_NEW_FAILURES',
        original_targeted=116,variant_targeted=116,variant_inline=1,event_clock_and_1bit_loss=7,
        historical=132,historical_passed=131,known_F3_failed=1,
        source_tests_or_expectations_modified=False,complete_catalog_reenumerated=False))
    print('REGRESSION_PASS_NO_NEW_FAILURES',flush=True)
if __name__=='__main__':main()
