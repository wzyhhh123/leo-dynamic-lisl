"""Engineering regression only; writes to an explicitly new evidence path."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
PATTERNS = (
    'test_terminal_executor.py', 'test_gate_d1.py', 'test_gate_d2.py',
    'test_inflight_propagation_closure.py', 'test_b4_lightweight_clone.py',
    'test_b4_checkpoint_alignment.py', 'test_gate_f3_drain_continuation_adapter.py',
    'test_f3_v2_joint_snapshot.py', 'test_f3_v2_search_policy_probe.py',
)

if __name__ == '__main__':
    suite = unittest.TestSuite()
    for pattern in PATTERNS:
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = dict(scope='ENGINEERING_HISTORICAL_REGRESSION_ONLY',
                  patterns=PATTERNS, tests_run=result.testsRun,
                  failures=[dict(test=str(t), traceback=s) for t, s in result.failures],
                  errors=[dict(test=str(t), traceback=s) for t, s in result.errors],
                  skipped=[dict(test=str(t), reason=s) for t, s in result.skipped],
                  output=stream.getvalue())
    with Path(sys.argv[1]).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'output'}, indent=2))
    sys.exit(bool(result.failures or result.errors))
