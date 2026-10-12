"""Run only the isolated SGP4 project's tests, irrespective of shell cwd."""
from pathlib import Path
import sys
import unittest
project=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(project/'src'))
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(project/'tests'),pattern='test_sgp4.py'))
raise SystemExit(0 if result.wasSuccessful() and result.testsRun else 1)
