import copy
from dataclasses import replace
import math
from pathlib import Path
import random
import tempfile
import unittest
from dynamic_lisl.gate_a import Config,audit,synthetic,analytic_state,metadata,audit_ephemeris,extract_subset,audit_subset
from dynamic_lisl.stk_gate_a import reserve_output,PROJECT

class GateAValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Config();cls.rows=synthetic(cls.c)
    def rejects(self,rows,code):
        result,_=audit(rows,self.c);self.assertFalse(result['passed']);self.assertIn(code,{r['code'] for r in result['errors']})
    def test_correct_720(self):
        r,a=audit(self.rows,self.c);self.assertTrue(r['passed']);self.assertEqual(len(a),720)
        self.assertEqual(a[0]['r_km'],[7578.137,0.,0.]);self.assertAlmostEqual(r['expected_signed_phase_deg'],.5)
    def test_delta_is_not_star(self):
        r=copy.deepcopy(self.rows)
        for i,x in enumerate(r):x['raan_deg']=(i//40)*20.
        self.rejects(r,'RAAN_TARGET')
    def test_narrow_spread_rejected(self):
        r=copy.deepcopy(self.rows)
        for i,x in enumerate(r):x['raan_deg']=i//40
        self.rejects(r,'RAAN_TARGET')
    def test_alternating_phase_rejected(self):
        r=copy.deepcopy(self.rows)
        for i,x in enumerate(r):x['argument_of_latitude_deg']=(i%40)*9+((i//40)%2)*.5
        self.rejects(r,'GLOBAL_PHASE')
    def test_global_wrong_sign(self):self.rejects(synthetic(replace(self.c,sigma=-1)),'GLOBAL_PHASE')
    def test_explicit_negative_sign(self):
        c=replace(self.c,sigma=-1);self.assertTrue(audit(synthetic(c),c)[0]['passed'])
    def test_single_phase_outlier(self):
        r=copy.deepcopy(self.rows);r[0]['argument_of_latitude_deg']+=.01;self.rejects(r,'GLOBAL_PHASE')
    def test_single_raan_outlier(self):
        r=copy.deepcopy(self.rows);r[0]['raan_deg']+=.001;self.rejects(r,'RAAN_TARGET')
    def test_missing(self):self.rejects(self.rows[:-1],'COUNT')
    def test_duplicate_name(self):
        r=copy.deepcopy(self.rows);r[1]['source_name']=r[0]['source_name'];self.rejects(r,'DUPLICATE_ID')
    def test_duplicate_slot(self):
        r=copy.deepcopy(self.rows);r[1]['argument_of_latitude_deg']=r[0]['argument_of_latitude_deg'];self.rejects(r,'DUPLICATE_SLOT')
    def test_shuffle_invariance(self):
        rows=copy.deepcopy(self.rows);random.Random(17).shuffle(rows)
        self.assertEqual(audit(rows,self.c)[1],audit(self.rows,self.c)[1])
    def test_wraparound_seed(self):
        c=replace(self.c,seed_raan_deg=350,seed_u_deg=358);self.assertTrue(audit(synthetic(c),c)[0]['passed'])
    def test_nonfinite_data(self):
        for v in (float('nan'),float('inf')):
            r=copy.deepcopy(self.rows);r[0]['raan_deg']=v;self.rejects(r,'NONFINITE_OR_MISSING')
    def test_bad_configs(self):
        for change in [dict(planes=0),dict(sats_per_plane=2),dict(phase_increment=18),dict(sigma=0),dict(duration_s=0),dict(duration_s=math.nan),dict(frame='ICRF')]:
            with self.subTest(change=change),self.assertRaises(ValueError):replace(self.c,**change).validate()
    def test_metadata_failures(self):
        for key,value in [('frame','ICRF'),('distance_unit','m'),('epoch','wrong'),('propagator','J2Perturbation')]:
            r=copy.deepcopy(self.rows);r[0][key]=value;self.rejects(r,'METADATA')
    def test_cartesian_meters_not_km(self):
        r=copy.deepcopy(self.rows);r[0]['r_km']=[v*1000 for v in r[0]['r_km']];self.rejects(r,'INITIAL_POSITION')
    def test_initial_epoch_shift(self):
        r=copy.deepcopy(self.rows);pos,vel=analytic_state(self.c,0,0,10);r[0]['r_km']=pos.tolist();r[0]['v_km_s']=vel.tolist();self.rejects(r,'INITIAL_POSITION')
    def test_eccentric_or_wrong_inclination(self):
        for key,value,code in [('eccentricity',.001,'ECCENTRICITY'),('inclination_deg',84.,'INCLINATION')]:
            r=copy.deepcopy(self.rows);r[0][key]=value;self.rejects(r,code)
    def test_ephemeris_and_late_corruption(self):
        c=Config(planes=3,sats_per_plane=4,duration_s=600);_,a=audit(synthetic(c),c);samples=[];times=[0.,17.3,600.]
        for x in a:
            for t in times:
                r,v=analytic_state(c,x['plane_id'],x['slot_id'],t);samples.append(dict(sat_name=x['sat_name'],t_s=t,r_km=r.tolist(),v_km_s=v.tolist(),**metadata(c)))
        self.assertTrue(audit_ephemeris(samples,a,c,times)['passed'])
        samples[-1]['r_km'][0]+=.01;self.assertFalse(audit_ephemeris(samples,a,c,times)['passed'])
        self.assertFalse(audit_ephemeris(samples[:-1],a,c,times)['passed'])
    def test_subset_exact_parent_and_tamper(self):
        _,a=audit(self.rows,self.c);sub,ss=extract_subset(a,[],[0,1,2,3]);self.assertEqual(len(sub),160)
        self.assertTrue(audit_subset(sub,ss,a,[],[0,1,2,3])['passed'])
        sub[0]['r_km']=list(sub[0]['r_km']);sub[0]['r_km'][0]+=1
        self.assertFalse(audit_subset(sub,ss,a,[],[0,1,2,3])['passed'])
    def test_subset_invalid_planes(self):
        _,a=audit(self.rows,self.c)
        for planes in ([0,2],[17,18],[]):
            with self.assertRaises(ValueError):extract_subset(a,[],planes)
    def test_no_output_overwrite(self):
        with tempfile.TemporaryDirectory(dir=PROJECT/'outputs') as p:
            with self.assertRaises(FileExistsError):reserve_output(p)
        with self.assertRaises(ValueError):reserve_output(PROJECT/'configs'/'forbidden')

if __name__=='__main__':unittest.main()
