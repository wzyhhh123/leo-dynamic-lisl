"""Read frozen TLEs and print SGP4 native TEME states without starting STK."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dynamic_lisl.common import PROJECT,EPOCH
from dynamic_lisl.sgp4_model import Sgp4Model
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--time-s',type=float,default=0)
p.add_argument('--sat-id',action='append')
a=p.parse_args()
m=Sgp4Model.load(PROJECT/'data/raw/sgp4_x720')
ids=a.sat_id or ['X0_1']
r,v=m.state(a.time_s,ids)
print(json.dumps(dict(epoch_utc=EPOCH,time_s=a.time_s,frame='TEMEOfDate',sat_ids=ids,position_km=r[0].tolist(),velocity_km_s=v[0].tolist()),indent=2))
