"""N1a engineering tests with pre/post source and contract binding verification."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

VERSION = Path(__file__).resolve().parents[2]
PROJECT = VERSION.parents[1]
sys.path.insert(0, str(VERSION))
from runtime.bindings import EngineeringBinding


def write_new(path, doc):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args()
    binding = EngineeringBinding(PROJECT,
        'research_versions/dynamic_k_v1/acceptance/0004/implementation_manifest.json',
        args.expected_manifest_sha256)
    pre = binding.verify()
    spec = importlib.util.spec_from_file_location('test_n1a', VERSION / 'tests/test_n1a.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EVIDENCE = binding
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    post = binding.verify()
    assert pre == post
    import jsonschema
    schema = json.loads((VERSION/'schemas/n1a_engineering_result_v1.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    for example in module.EXAMPLES.values():
        if 'schema' in example:
            validator.validate(example)
    report = dict(scope='N1A_ENGINEERING_ACCEPTANCE_ONLY', tests_run=result.testsRun,
                  status='PASS' if result.wasSuccessful() else 'FAIL',
                  failures=[dict(test=str(t), traceback=s) for t, s in result.failures],
                  errors=[dict(test=str(t), traceback=s) for t, s in result.errors],
                  output=stream.getvalue(), pre_execution_bindings=pre,
                  post_execution_bindings=post, scientific_gate_pass=False,
                  N1b_implemented=False, N2_implemented=False,
                  formal_experiments_executed=False, engineering_example_schema_validation='PASS')
    write_new(Path(__file__).parent / 'n1a_test_report.json', report)
    write_new(Path(__file__).parent / 'engineering_examples.json',
              dict(scope='ENGINEERING_TEST_ONLY', examples=module.EXAMPLES, bindings=post))
    print(json.dumps({k:v for k,v in report.items() if k != 'output'}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
