"""Frozen synthetic TLE model and independent SGP4 native-TEME evaluator."""
from pathlib import Path
import math
import numpy as np
from sgp4.api import Satrec, SatrecArray, WGS72, SGP4_ERRORS
from .common import EPOCH, EPOCH_JD, DURATION, read_json, sha


def checksum(line):return sum(int(x) if x.isdigit() else 1 if x=='-' else 0 for x in line[:68])%10

def parse_tle(line1,line2,expected_ssc=None):
    for line,number in ((line1,'1'),(line2,'2')):
        if len(line)!=69 or not line.startswith(number+' ') or not line[68].isdigit() or checksum(line)!=int(line[68]):
            raise ValueError('TLE_FORMAT_OR_CHECKSUM')
    if line1[2:7]!=line2[2:7]:raise ValueError('TLE_SSC_MISMATCH')
    sat=Satrec.twoline2rv(line1,line2,WGS72)
    if expected_ssc is not None and sat.satnum!=expected_ssc:raise ValueError('TLE_SSC_EXPECTATION')
    if abs((sat.jdsatepoch-EPOCH_JD)+sat.jdsatepochF)>1e-10:raise ValueError('TLE_EPOCH')
    if sat.bstar!=0:raise ValueError('SYNTHETIC_BSTAR_MUST_BE_ZERO')
    if not 0<=sat.ecco<0.01 or not math.isfinite(sat.no_kozai) or sat.no_kozai<=0:raise ValueError('INVALID_ORBIT')
    return sat


class Sgp4Model:
    """Native TEME-of-date states in km and km/s; no circular orbit equations."""
    def __init__(self,records,duration_s=DURATION):
        if not np.isfinite(duration_s) or duration_s<=0:raise ValueError('INVALID_DURATION')
        self.records=records;self.duration_s=duration_s
        self.ids=[r['sat_name'] for r in records]
        if not self.ids or len(set(self.ids))!=len(self.ids):raise ValueError('DUPLICATE_OR_EMPTY_IDS')
        ssc=[r['ssc'] for r in records]
        if len(set(ssc))!=len(ssc):raise ValueError('DUPLICATE_SSC')
        self.models=[parse_tle(r['line1'],r['line2'],r['ssc']) for r in records]
        self.lookup={name:i for i,name in enumerate(self.ids)}

    def state(self,times,ids=None):
        t=np.atleast_1d(np.asarray(times,float))
        if t.ndim!=1 or not np.isfinite(t).all() or np.any(t<0) or np.any(t>self.duration_s):raise ValueError('SGP4_TIME_OUTSIDE_WINDOW')
        models=self.models if ids is None else [self.models[self.lookup[x]] for x in ids]
        errors,r,v=SatrecArray(models).sgp4(np.full(len(t),EPOCH_JD),t/86400.0)
        if np.any(errors):raise ValueError('SGP4_PROPAGATION_ERRORS: '+str(np.unique(errors[errors!=0]).tolist()))
        if not np.isfinite(r).all() or not np.isfinite(v).all():raise ValueError('SGP4_NONFINITE')
        return r.transpose(1,0,2),v.transpose(1,0,2)

    @classmethod
    def load(cls,folder):
        folder=Path(folder).resolve();manifest=read_json(folder/'manifest.json')
        if manifest.get('schema')!='sgp4_bundle_v1' or manifest.get('propagator')!='SGP4' or manifest.get('epoch_utc')!=EPOCH or manifest.get('status')!='FROZEN_SYNTHETIC_TLE':
            raise ValueError('NOT_FORMAL_SGP4_BUNDLE')
        prov=read_json(folder/'hashes.json')
        for name in ('manifest.json','constellation.tle'):
            if sha(folder/name)!=prov.get(name):raise ValueError('SGP4_BUNDLE_HASH_MISMATCH')
        records=manifest['satellites']
        expected=''.join(r['sat_name']+'\n'+r['line1']+'\n'+r['line2']+'\n' for r in records)
        if (folder/'constellation.tle').read_text(encoding='ascii')!=expected:raise ValueError('TLE_FILE_MANIFEST_MISMATCH')
        return cls(records,manifest['duration_s'])


def tle_mean_elements(model):
    return dict(inclination_deg=math.degrees(model.inclo),raan_deg=math.degrees(model.nodeo),eccentricity=model.ecco,
        argument_of_perigee_deg=math.degrees(model.argpo),mean_anomaly_deg=math.degrees(model.mo),mean_motion_rev_day=model.no_kozai*1440/(2*math.pi),bstar=model.bstar,gravity='WGS72',operationmode=model.operationmode)
