# -*- coding: utf-8 -*-
"""Read-only v2 preflight; this command never launches any experiment."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.preflight import validate_preflight
from dynamic_lisl.f3_v2.evidence import write_new_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','science-contract','k0-report','k1-report','engineering-report','runtime-budget','authorization'):
        p.add_argument('--'+key)
    args=p.parse_args()
    data={}
    for key,value in vars(args).items():
        data[key]=json.loads(Path(value).read_text(encoding='utf-8')) if value else {}
    report=validate_preflight(ROOT,**data)
    out=ROOT/'outputs'/('f3_v2_preflight_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir();write_new_json(out/'report.json',report)
    print(json.dumps({'output_dir':str(out),**report},indent=2))
    return 0 if report['status']=='READY' else 2


if __name__=='__main__':raise SystemExit(main())
