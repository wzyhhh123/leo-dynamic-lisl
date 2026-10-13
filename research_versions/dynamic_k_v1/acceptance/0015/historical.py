"""Frozen original historical suites, keep pre-existing F3 failure unchanged."""
import sys,unittest,io,json
import support as w
def main():
    reference=w.vc.read_json(w.V/'acceptance/0011/historical_regression.json')
    groups=[]
    def find(d):
        if isinstance(d,dict):
            if 'patterns' in d:groups.append(d)
            else:
                for v in d.values():find(v)
    find(reference);reports=[]
    sys.path.insert(0,str(w.P/'tests'))
    for index,group in enumerate(groups):
        suite=unittest.TestSuite()
        for pattern in group['patterns']:suite.addTests(unittest.defaultTestLoader.discover(str(w.P/'tests'),pattern=pattern))
        stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        result=dict(tests_run=r.testsRun,patterns=group['patterns'],failures=[dict(test=str(t),traceback=s) for t,s in r.failures],
            errors=[dict(test=str(t),traceback=s) for t,s in r.errors],skipped=[str(t) for t,_ in r.skipped],output=stream.getvalue(),
            original_kernel_only=True,variant_not_imported_into_frozen_fixture=True,
            reference_tests_run=group['tests_run'],reference_failure_tests=[x['test'] for x in group['failures']])
        result['no_new_failures']=r.testsRun==group['tests_run'] and [x['test'] for x in result['failures']]==result['reference_failure_tests'] and not result['errors']
        reports.append(result);w.write(w.A/('historical_group_'+str(index)+'.json'),result)
        print('HISTORICAL',r.testsRun,'failures',len(r.failures),'new',not result['no_new_failures'],flush=True)
    w.write(w.A/'historical_summary.json',dict(tests=sum(x['tests_run'] for x in reports),no_new_failures=all(x['no_new_failures'] for x in reports)))
    return not all(x['no_new_failures'] for x in reports)
if __name__=='__main__':raise SystemExit(main())
