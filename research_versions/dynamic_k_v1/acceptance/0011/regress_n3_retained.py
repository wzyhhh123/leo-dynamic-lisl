"""Frozen N3 suite with its existing independently pinned evidence branch.

Avoids an unbounded repeated historical catalog scan; fresh P0R full-catalog
cost diagnosis is separate and explicitly bounded. No test expectation changes.
"""
import workflow as w
from runtime.n4_p0 import P0EvidenceBinding
def main():
    origin='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
    parent='fa9564caf795279ce608cf7ff31c9a86693c7336238b285a52c95c7ffb66c897'
    expected=w.vc.load_expected(w.P,origin,parent)[2]
    path=w.V/'acceptance/0007/attempt01/catalog_coverage.json';rel=path.relative_to(w.P).as_posix()
    assert w.vc.file_info(path)==expected[rel]
    deps=w.old.dependencies()
    with w.ReaderLease(deps+[w.guard()],w.vc) as lease:
        m=w.old.load('p0r_N3_retained',w.V/'tests/test_n3_baselines.py')
        m.N1A_BINDING,m.N1B_BINDING,m.N2_BINDING,m.N3_BINDING=[lease.guard(x) for x in deps]
        m.PRIOR_CATALOG_EVIDENCE=(path,expected[rel]['sha256'])
        result=w.old.test_module(m);result['catalog_regression_mode']='FROZEN_TEST_EXISTING_RETAINED_EVIDENCE_BRANCH'
        result['retained_catalog_binding']=dict(path=rel,**expected[rel]);result['fresh_complete_catalog_scan_claimed']=False
        w.write('regression_N3_retained.json',result);w.write('n3_retained_coverage_validation.json',m.COVERAGE)
        print(result['status'],result['tests_run'],flush=True);return result['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
