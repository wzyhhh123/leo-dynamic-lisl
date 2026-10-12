"""Pinned N2-specific acceptance and unchanged N1a/N1b regressions, append only."""
import argparse,importlib.util,io,json,sys,unittest
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.bindings import EngineeringBinding
from runtime.n1b_evaluator import N1bEvidenceBinding
from runtime.n2_binding import N2EvidenceBinding
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def write_new(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def run(m):
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(m))
    return dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests_run=r.testsRun,output=stream.getvalue(),
        failures=[dict(test=str(t),traceback=s) for t,s in r.failures],errors=[dict(test=str(t),traceback=s) for t,s in r.errors],
        scientific_gate_pass=False,formal_experiments_executed=False)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected-manifest-sha256',required=True)
    parser.add_argument('--evidence-directory',type=Path,default=A);args=parser.parse_args()
    dest=args.evidence_directory;dest.mkdir(exist_ok=True)
    old=EngineeringBinding(P,'research_versions/dynamic_k_v1/acceptance/0004/implementation_manifest.json',
        '227043a6bcf318846bbc2e854130613b49082ef6a7e17f3913160f24f40456ad')
    fifo=N1bEvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0005/implementation_manifest.json',
        'c27ac2866d4bfd12a8384bd91a990f841daad45a7079230301d1aaef4436031a')
    new=N2EvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0006/implementation_manifest.json',args.expected_manifest_sha256)
    pre=new.verify();old_pre=old.verify();fifo_pre=fifo.verify()
    n2=load('n2_acceptance_tests',V/'tests/test_n2_actions.py');n2.N1A_BINDING=old;n2.N1B_BINDING=fifo;n2.N2_BINDING=new
    report=run(n2)
    # Preserve first-attempt failures before any schema/implementation follow-up.
    write_new(dest/'n2_test_report.json',dict(report,pre_execution_bindings=pre,post_execution_bindings=new.verify()))
    print(json.dumps({k:v for k,v in report.items() if k!='output'},indent=2),flush=True)
    if report['status']!='PASS':return 1
    n1a=load('n1a_unchanged_regression',V/'tests/test_n1a.py');n1a.EVIDENCE=old
    n1b=load('n1b_unchanged_regression',V/'tests/test_n1b_fifo.py');n1b.N1A_BINDING=old;n1b.N1B_BINDING=fifo
    upstream=dict(N1a=run(n1a),N1b=run(n1b))
    assert pre==new.verify() and old_pre==old.verify() and fifo_pre==fifo.verify()
    import jsonschema
    schema=json.loads((V/'schemas/n2_engineering_result_v1.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema);validator=jsonschema.Draft202012Validator(schema)
    for example in n2.EXAMPLES.values():validator.validate(example if 'schema' in example else example['result'])
    write_new(dest/'upstream_regression_report.json',upstream)
    write_new(dest/'engineering_examples.json',dict(scope='ENGINEERING_TEST_ONLY',bindings=new.verify(),examples=n2.EXAMPLES))
    write_new(dest/'acceptance_summary.json',dict(status='PASS' if all(r['status']=='PASS' for r in upstream.values()) else 'FAIL',
        N2_tests=report['tests_run'],N1a_tests=upstream['N1a']['tests_run'],N1b_tests=upstream['N1b']['tests_run'],
        example_schema_validation='PASS',pre_bindings=pre,post_bindings=new.verify(),scientific_gate_pass=False))
    print(json.dumps({k:{x:y for x,y in v.items() if x!='output'} for k,v in upstream.items()},indent=2))
    return 0 if all(r['status']=='PASS' for r in upstream.values()) else 1
if __name__=='__main__':sys.exit(main())
