import copy
import math
import tempfile
from pathlib import Path
import unittest
import numpy as np
from dynamic_lisl.gate_a import Config, synthetic, audit
from dynamic_lisl.ephemeris import Ephemeris, circular_states, time_grid, audit_interpolation, geometry_windows


def meta(c):
    return dict(schema='dynamic_lisl_ephemeris_v1',frame='J2000',position_unit='km',velocity_unit='km/s',time_unit='s',propagator='TwoBody',interpolation='cubic_hermite',epoch_utc=c.epoch)


class EphemerisTests(unittest.TestCase):
    def setUp(self):
        self.c=Config(planes=3,sats_per_plane=4,duration_s=10000)
        self.rows=audit(synthetic(self.c),self.c)[1]

    def make(self,step=30,duration=600):
        t=time_grid(duration,step); r,v=circular_states(self.c,self.rows,t)
        return Ephemeris(t,[x['sat_name'] for x in self.rows],r,v,meta(self.c))

    def test_fractional_stop_and_invalid_grid(self):
        np.testing.assert_array_equal(time_grid(65,30),[0,30,60,65])
        for d,s in [(0,30),(600,0),(600,float('nan'))]:
            with self.assertRaises(ValueError):time_grid(d,s)

    def test_exact_cubic_and_derivative(self):
        t=np.array([0.,3.]); r=(t**3)[:,None,None]*np.ones((1,1,3)); v=(3*t*t)[:,None,None]*np.ones((1,1,3))
        ep=Ephemeris(t,['A'],r,v,meta(self.c)); q=np.array([0.,0.37,2.,3.]); rr,vv=ep.state(q)
        np.testing.assert_allclose(rr[:,0,0],q**3,atol=1e-13)
        np.testing.assert_allclose(vv[:,0,0],3*q*q,atol=1e-13)

    def test_time_bounds_unknown_id_and_reordering(self):
        ep=self.make()
        for q in [-1,601,float('nan')]:
            with self.assertRaises(ValueError):ep.state(q)
        with self.assertRaises(ValueError):ep.state(10,['missing'])
        ids=list(ep.sat_ids[[3,0]])
        np.testing.assert_array_equal(ep.state(0,ids)[0][0],ep.position_km[0,[3,0]])

    def test_reject_corrupted_axes_units_and_states(self):
        ep=self.make()
        with self.assertRaises(ValueError):Ephemeris(ep.time_s[::-1],ep.sat_ids,ep.position_km,ep.velocity_km_s,ep.metadata)
        bad=copy.deepcopy(ep.metadata);bad['frame']='TEME'
        with self.assertRaises(ValueError):Ephemeris(ep.time_s,ep.sat_ids,ep.position_km,ep.velocity_km_s,bad)
        badr=ep.position_km.copy();badr[0,0,0]=np.nan
        with self.assertRaises(ValueError):Ephemeris(ep.time_s,ep.sat_ids,badr,ep.velocity_km_s,ep.metadata)
        with self.assertRaises(ValueError):Ephemeris(ep.time_s,['X']*len(ep.sat_ids),ep.position_km,ep.velocity_km_s,ep.metadata)

    def test_archive_roundtrip_without_pickle_or_overwrite(self):
        ep=self.make()
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'e.npz';ep.save(p);loaded=Ephemeris.load(p)
            np.testing.assert_array_equal(loaded.state([0,17.3,600])[0],ep.state([0,17.3,600])[0])
            with self.assertRaises(FileExistsError):ep.save(p)

    def test_sampling_interval_changes_error_and_rejects_coarse(self):
        fine=audit_interpolation(self.make(30),self.c,self.rows,velocity_tol_km_s=1e-5)
        coarse=audit_interpolation(self.make(120),self.c,self.rows,velocity_tol_km_s=1e-5)
        self.assertTrue(fine['passed']);self.assertFalse(coarse['passed'])
        self.assertGreater(coarse['max_position_error_m'],fine['max_position_error_m']*100)

    def test_geometry_partition_and_interior_checks(self):
        a,b=self.rows[0],self.rows[4]
        report=geometry_windows(self.c,a,b,0,600,5000,tolerance_s=0.1)
        pieces=report['intervals']; self.assertEqual(pieces[0]['start_s'],0);self.assertEqual(pieces[-1]['end_s'],600)
        for left,right in zip(pieces[:-1],pieces[1:]):self.assertEqual(left['end_s'],right['start_s'])
        for p in pieces:
            if p['state']=='unresolved_boundary':self.assertLessEqual(p['end_s']-p['start_s'],0.1)
            else:
                tt=np.linspace(p['start_s'],p['end_s'],7);r,_=circular_states(self.c,[a,b],tt)
                delta=r[:,1]-r[:,0];frac=np.clip(-np.sum(r[:,0]*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
                margins=np.minimum(np.linalg.norm(r[:,0]+frac[:,None]*delta,axis=1)-6378.137,5000-np.linalg.norm(delta,axis=1))
                self.assertTrue(np.all(margins>0) if p['state']=='visible' else np.all(margins<0))

    def test_short_contact_not_missed_by_equal_endpoint_signs(self):
        a,b=self.rows[0],self.rows[4]
        period=2*math.pi*math.sqrt(self.c.sma_km**3/self.c.mu_km3_s2)
        tt=np.linspace(0,period,2001);r,_=circular_states(self.c,[a,b],tt)
        d=np.linalg.norm(r[:,1]-r[:,0],axis=1);limit=float(d.min()+10)
        self.assertGreater(d[0],limit);self.assertGreater(d[-1],limit)
        report=geometry_windows(self.c,a,b,0,period,limit,earth_radius_km=1,tolerance_s=0.1,coarse_step_s=period)
        self.assertTrue(any(p['state']=='visible' for p in report['intervals']))
        self.assertGreater(report['unresolved_leaf_count'],0)

    def test_geometry_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):geometry_windows(self.c,self.rows[0],self.rows[0],0,600,5000)
        with self.assertRaises(ValueError):geometry_windows(self.c,self.rows[0],self.rows[1],0,20000,5000)

if __name__=='__main__':unittest.main()
