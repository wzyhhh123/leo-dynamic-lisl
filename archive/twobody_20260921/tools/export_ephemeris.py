"""Export a verified STK Gate A scene; no network simulation or RL."""
import argparse
from pathlib import Path
import sys
import unittest
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from dynamic_lisl.stk_ephemeris import export


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gate-dir',type=Path)
    p.add_argument('--step-s',type=float,default=30)
    p.add_argument('--duration-s',type=float)
    p.add_argument('--sat-limit',type=int,help='Diagnostic prefix only; omit for all satellites')
    p.add_argument('--visible',action='store_true')
    p.add_argument('--check-only',action='store_true')
    a=p.parse_args()
    suite=unittest.defaultTestLoader.discover(str(PROJECT/'tests'),pattern='test_ephemeris.py')
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful(): raise SystemExit(1)
    if a.check_only:return
    if a.gate_dir is None:p.error('--gate-dir required for export')
    export(a.gate_dir,a.step_s,a.duration_s,a.sat_limit,a.visible)

if __name__=='__main__':main()
