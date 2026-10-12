"""Run Gate A preflight, STK smoke, or the 720 mother constellation only."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from dynamic_lisl.gate_a import Config
from dynamic_lisl.stk_gate_a import run_stk,dump

def preflight():
    suite=unittest.defaultTestLoader.discover(str(PROJECT/'tests'),pattern='test_gate_a.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report=dict(passed=result.wasSuccessful(),tests_run=result.testsRun,failures=[str(t) for t,_ in result.failures],errors=[str(t) for t,_ in result.errors])
    folder=PROJECT/'outputs'/'gate_a_preflight';folder.mkdir(exist_ok=True)
    dump(folder/'latest.json',report)
    if not result.wasSuccessful():raise RuntimeError('A0_FAILED: STK will not launch')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['preflight','smoke','720'],default='preflight')
    parser.add_argument('--visible',action='store_true',help='Explicitly show the owned STK instance; otherwise hidden')
    parser.add_argument('--earth-cb',default='D:/Program Files/AGI/STK 11/STKData/CentralBodies/Earth/Earth.cb')
    args=parser.parse_args()
    preflight()
    if args.mode=='preflight':return
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    smoke=run_stk(Config(planes=3,sats_per_plane=4,duration_s=600),PROJECT/'outputs'/f'gate_a_smoke_{stamp}',args.earth_cb,args.visible)
    print('STK smoke output:',smoke,flush=True)
    if args.mode=='720':
        out=run_stk(Config(),PROJECT/'outputs'/f'gate_a_720_{stamp}',args.earth_cb,args.visible)
        print('720 output:',out,flush=True)
        print('PASS_SAMPLED_GEOMETRY; no continuous lifetime or network claims.')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('GATE A FAILED:',exc,file=sys.stderr)
        raise SystemExit(1)
