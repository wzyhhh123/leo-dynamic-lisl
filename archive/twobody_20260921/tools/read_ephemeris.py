"""Query an exported ephemeris with Python only (no STK)."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dynamic_lisl.ephemeris import Ephemeris
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('dataset',type=Path)
p.add_argument('--time-s',type=float,required=True)
p.add_argument('--sat-id',action='append',required=True)
a=p.parse_args()
ep=Ephemeris.load(a.dataset)
r,v=ep.state(a.time_s,a.sat_id)
print(json.dumps(dict(epoch_utc=ep.metadata['epoch_utc'],frame='J2000',time_s=a.time_s,sat_ids=a.sat_id,position_km=r[0].tolist(),velocity_km_s=v[0].tolist()),indent=2))
