"""Run additive reader controls without changing the original test file."""
import importlib.util,io,json,sys,unittest
from pathlib import Path
V=Path(__file__).resolve().parents[2];A=Path(__file__).parent
spec=importlib.util.spec_from_file_location('root_readme_tests',V/'tests/test_root_readme_policy.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
    original_controls_reused_without_source_edit=22,new_root_readme_controls=10,
    failures=[dict(test=str(t),traceback=s) for t,s in result.failures],errors=[dict(test=str(t),traceback=s) for t,s in result.errors],
    skipped=[dict(test=str(t),reason=s) for t,s in result.skipped],output=stream.getvalue(),scope='ISOLATED_FILE_INTEGRITY_CONTROLS_ONLY')
with (A/'protection_test_report.json').open('x',encoding='utf-8',newline='\n') as out:json.dump(report,out,indent=2);out.write('\n')
print(json.dumps(report,indent=2));sys.exit(0 if result.wasSuccessful() else 1)
