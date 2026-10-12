"""Pinned N1b acceptance, unchanged N1a regression, schemas and evidence."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

V=Path(__file__).resolve().parents[2]
P=V.parents[1]
A=Path(__file__).parent
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.bindings import EngineeringBinding
from runtime.n1b_evaluator import N1bEvidenceBinding

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def run(m):
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(m))
    return dict(tests_run=result.testsRun,status='PASS' if result.wasSuccessful() else 'FAIL',
        failures=[dict(test=str(t),traceback=s) for t,s in result.failures],
        errors=[dict(test=str(t),traceback=s) for t,s in result.errors],
        output=stream.getvalue(),scientific_gate_pass=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected-manifest-sha256',required=True)
    args=parser.parse_args()
    old=EngineeringBinding(P,'research_versions/dynamic_k_v1/acceptance/0004/implementation_manifest.json',
        '227043a6bcf318846bbc2e854130613b49082ef6a7e17f3913160f24f40456ad')
    new=N1bEvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0005/implementation_manifest.json',
        args.expected_manifest_sha256)
    pre=new.verify();old_pre=old.verify()
    n1b=module('n1b_acceptance_tests',V/'tests/test_n1b_fifo.py')
    n1b.N1A_BINDING=old;n1b.N1B_BINDING=new
    report=run(n1b)
    n1a=module('n1a_regression_tests',V/'tests/test_n1a.py');n1a.EVIDENCE=old
    old_report=run(n1a)
    post=new.verify();assert pre==post and old_pre==old.verify()
    import jsonschema
    schema=json.loads((V/'schemas/n1b_engineering_result_v1.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator=jsonschema.Draft202012Validator(schema)
    for example in n1b.EXAMPLES.values():
        if 'schema' in example:validator.validate(example)
    report.update(scope='N1B_ENGINEERING_ACCEPTANCE_ONLY',pre_execution_bindings=pre,post_execution_bindings=post,
        engineering_example_schema_validation='PASS',formal_experiments_executed=False,N2_implemented=False)
    old_report.update(scope='UNCHANGED_N1A_ENGINEERING_REGRESSION',bindings=old.verify())
    write_new(A/'n1b_test_report.json',report)
    write_new(A/'n1a_regression_report.json',old_report)
    write_new(A/'engineering_examples.json',dict(scope='ENGINEERING_TEST_ONLY',bindings=post,examples=n1b.EXAMPLES))
    print(json.dumps(dict(N1b={k:v for k,v in report.items() if k not in ('output','pre_execution_bindings','post_execution_bindings')},
                         N1a={k:v for k,v in old_report.items() if k not in ('output','bindings')}),indent=2))
    return 0 if report['status']==old_report['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())
