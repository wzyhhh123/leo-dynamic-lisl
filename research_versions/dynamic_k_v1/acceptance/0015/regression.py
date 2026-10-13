"""All frozen targeted tests via process-local imported fixture seams."""
import sys,unittest,inspect,io,json
import support as w
from runtime.n4_p0r_handle_reader import HandleReaderLease
def main(mode):
    deps=w.old.old.dependencies();g=w.old.guard();reports={}
    with HandleReaderLease(deps+[g],w.vc) as lease:
        bound=[lease.guard(x) for x in deps]
        fixture=w.old.old.load('p0f_fixture_'+mode,w.V/'tests/test_n3_baselines.py')
        fixture.N1A_BINDING,fixture.N1B_BINDING,fixture.N2_BINDING,fixture.N3_BINDING=bound
        w.bind_test_module(fixture,mode)
        for name,filename,attributes in [('N1a','test_n1a.py',['EVIDENCE']),('N1b','test_n1b_fifo.py',['N1A_BINDING','N1B_BINDING']),
            ('N2','test_n2_actions.py',['N1A_BINDING','N1B_BINDING','N2_BINDING']),('N3','test_n3_baselines.py',['N1A_BINDING','N1B_BINDING','N2_BINDING','N3_BINDING']),
            ('P0','test_n4_p0.py',[])]:
            m=w.old.old.load('p0f_reg_'+mode+'_'+name,w.V/'tests'/filename)
            for attr,value in zip(attributes,bound):setattr(m,attr,value)
            w.bind_test_module(m,mode)
            if name=='N3':
                p=w.V/'acceptance/0007/attempt01/catalog_coverage.json'
                expected=w.vc.load_expected(w.P,w.ORIGIN,w.PARENT)[2]
                assert w.vc.file_info(p)==expected[p.relative_to(w.P).as_posix()]
                m.PRIOR_CATALOG_EVIDENCE=(p,w.vc.file_info(p)['sha256'])
            if name=='P0':m.FIXTURES=fixture;m.BINDING=lease.guard(g)
            # One P0 test imports observer inside method: use a separate local
            # fixture seam for the explicitly rebuilt observer; no global import patch.
            # Its default constructor is left original and marked below if present.
            r=w.old.old.test_module(m);r.update(mode=mode,expectations_unmodified=True,
                selection='ALL_ORIGINAL_TEST_CASES',catalog_scan='RETAINED_FROZEN_EVIDENCE_NOT_ENUMERATED',
                module_local_constructor_binding_only=True)
            w.write(w.A/(mode+'_'+name+'_regression.json'),r);reports[name]=dict(status=r['status'],tests=r['tests_run'])
            print(mode+' '+name+' '+r['status']+' '+str(r['tests_run']),flush=True)
            if r['status']!='PASS':
                w.write(w.A/(mode+'_REGRESSION_STOP.json'),dict(status='BLOCKED',results=reports));return 2
    w.write(w.A/(mode+'_regression_summary.json'),reports);return 0
if __name__=='__main__':raise SystemExit(main(sys.argv[1]))
