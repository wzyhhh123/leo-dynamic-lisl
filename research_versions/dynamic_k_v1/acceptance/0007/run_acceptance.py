"""Pinned N3 acceptance + unchanged upstream regressions, preserving attempts."""
import argparse,importlib.util,io,json,sys,unittest
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.bindings import EngineeringBinding
from runtime.n1b_evaluator import N1bEvidenceBinding
from runtime.n2_binding import N2EvidenceBinding
from runtime.n3_baselines import N3EvidenceBinding

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ProgressResult(unittest.TextTestResult):
    def startTest(self,test):
        print('START '+str(test),flush=True);super().startTest(test)
    def stopTest(self,test):
        print('DONE '+str(test),flush=True);super().stopTest(test)

def run(module):
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=ProgressResult).run(unittest.defaultTestLoader.loadTestsFromModule(module))
    return dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests_run=r.testsRun,output=stream.getvalue(),
        failures=[dict(test=str(t),traceback=s) for t,s in r.failures],errors=[dict(test=str(t),traceback=s) for t,s in r.errors],
        skipped=[dict(test=str(t),reason=s) for t,s in r.skipped],scientific_gate_pass=False,formal_experiments_executed=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest-name',default='implementation_manifest.json')
    parser.add_argument('--expected-manifest-sha256',required=True);parser.add_argument('--attempt',required=True)
    parser.add_argument('--retained-catalog-path');parser.add_argument('--expected-catalog-sha256');args=parser.parse_args()
    dest=A/args.attempt;assert dest.parent==A;dest.mkdir(exist_ok=False)
    old=EngineeringBinding(P,'research_versions/dynamic_k_v1/acceptance/0004/implementation_manifest.json','227043a6bcf318846bbc2e854130613b49082ef6a7e17f3913160f24f40456ad')
    fifo=N1bEvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0005/implementation_manifest.json','c27ac2866d4bfd12a8384bd91a990f841daad45a7079230301d1aaef4436031a')
    atomic=N2EvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0006/implementation_manifest.json','34e3412da99a96c58fe603af5de69777d69e0e2bc292fba4cbd3cfca8acb0b4a')
    new=N3EvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0007/'+args.manifest_name,args.expected_manifest_sha256)
    pre=new.verify();old.verify();fifo.verify();atomic.verify()
    n3=load('n3_acceptance_tests',V/'tests/test_n3_baselines.py')
    n3.N1A_BINDING=old;n3.N1B_BINDING=fifo;n3.N2_BINDING=atomic;n3.N3_BINDING=new
    if args.retained_catalog_path:
        path=P/args.retained_catalog_path
        assert path.resolve().is_relative_to(A.resolve()) and args.expected_catalog_sha256
        n3.PRIOR_CATALOG_EVIDENCE=(path,args.expected_catalog_sha256)
    report=run(n3)
    write_new(dest/'n3_test_report.json',dict(report,pre_execution_bindings=pre,post_execution_bindings=new.verify()))
    write_new(dest/'engineering_examples.json',dict(scope='ENGINEERING_TEST_ONLY',bindings=pre,examples=n3.EXAMPLES))
    write_new(dest/'catalog_coverage.json',n3.COVERAGE)
    print(json.dumps({k:v for k,v in report.items() if k!='output'},indent=2),flush=True)
    if report['status']!='PASS':return 1
    import jsonschema
    schema=json.loads((V/'schemas/n3_engineering_result_v1.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema);validator=jsonschema.Draft202012Validator(schema)
    count=0
    def validate_tree(value):
        nonlocal count
        if isinstance(value,dict):
            if value.get('schema')=='dynamic_k_n3_engineering_result_v1':validator.validate(value);count+=1
            else:
                for child in value.values():validate_tree(child)
        elif isinstance(value,list):
            for child in value:validate_tree(child)
    validate_tree(n3.EXAMPLES)
    n1a=load('n1a_unchanged_regression',V/'tests/test_n1a.py');n1a.EVIDENCE=old
    n1b=load('n1b_unchanged_regression',V/'tests/test_n1b_fifo.py');n1b.N1A_BINDING=old;n1b.N1B_BINDING=fifo
    n2=load('n2_unchanged_regression',V/'tests/test_n2_actions.py');n2.N1A_BINDING=old;n2.N1B_BINDING=fifo;n2.N2_BINDING=atomic
    upstream=dict(N1a=run(n1a),N1b=run(n1b),N2=run(n2))
    write_new(dest/'upstream_regression_report.json',upstream)
    assert pre==new.verify()
    summary=dict(status='PASS' if all(x['status']=='PASS' for x in upstream.values()) else 'FAIL',
        N3_tests=report['tests_run'],upstream_test_counts={k:v['tests_run'] for k,v in upstream.items()},
        schema_validated_examples=count,complete_catalog_status=n3.COVERAGE['status'],
        pre_bindings=pre,post_bindings=new.verify(),scientific_gate_pass=False)
    write_new(dest/'acceptance_summary.json',summary);print(json.dumps(summary,indent=2),flush=True)
    return 0 if summary['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
