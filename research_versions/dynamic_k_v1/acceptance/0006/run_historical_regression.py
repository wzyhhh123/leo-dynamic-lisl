"""Unchanged B/C/D2 and clone regressions plus previously known F3 failure."""
import io,json,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(P/'src'))
BASE=('test_terminal_executor.py','test_gate_d1.py','test_gate_d2.py','test_inflight_propagation_closure.py',
      'test_b4_lightweight_clone.py','test_b4_checkpoint_alignment.py','test_gate_f3_drain_continuation_adapter.py',
      'test_f3_v2_joint_snapshot.py','test_f3_v2_search_policy_probe.py')
EXTRA=('test_gate_c.py','test_gate_c_simplified.py','test_gate_c_for_reasons.py')
def run(patterns):
    suite=unittest.TestSuite()
    for pattern in patterns:suite.addTests(unittest.defaultTestLoader.discover(str(P/'tests'),pattern))
    out=io.StringIO();r=unittest.TextTestRunner(stream=out,verbosity=2).run(suite)
    return dict(scope='ENGINEERING_HISTORICAL_REGRESSION',tests_run=r.testsRun,
        failures=[dict(test=str(t),traceback=s) for t,s in r.failures],errors=[dict(test=str(t),traceback=s) for t,s in r.errors],
        skipped=[dict(test=str(t),reason=s) for t,s in r.skipped],patterns=patterns,output=out.getvalue())
if __name__=='__main__':
    report=dict(base=run(BASE),physical_gate_c=run(EXTRA))
    with Path(sys.argv[1]).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:{x:y for x,y in v.items() if x!='output'} for k,v in report.items()},indent=2))
    sys.exit(bool(report['base']['failures'] or report['base']['errors'] or report['physical_gate_c']['failures'] or report['physical_gate_c']['errors']))
