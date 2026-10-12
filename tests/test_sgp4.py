import copy
import tempfile
from pathlib import Path
import unittest
import numpy as np
from dynamic_lisl.common import EPOCH,PROJECT,read_json,sha
from dynamic_lisl.sgp4_model import parse_tle,checksum,Sgp4Model
from dynamic_lisl.ephemeris import Ephemeris,time_grid
from dynamic_lisl.sgp4_geometry import search_windows,geometry_windows

L1='1 10000           26001.00000000  .00000000  00000-0  00000-0 0 00003'
L2='2 10000 084.9990 000.3204 0010616 248.4205 111.7252 13.17528788000010'
def fixed(line):return line[:68]+str(checksum(line))
def records():
    second1=fixed(L1[:2]+'10001'+L1[7:])
    second2=fixed(L2[:2]+'10001'+L2[7:17]+'010.3204'+L2[25:])
    return [dict(sat_name='X0_1',ssc=10000,line1=L1,line2=L2),dict(sat_name='X1_1',ssc=10001,line1=second1,line2=second2)]
def metadata():return dict(schema='dynamic_lisl_ephemeris_v2',frame='J2000',native_frame='TEMEOfDate',position_unit='km',velocity_unit='km/s',time_unit='s',propagator='SGP4',interpolation='cubic_hermite',epoch_utc=EPOCH,tle_bundle_sha256='a'*64)

class Sgp4Tests(unittest.TestCase):
    def test_tle_and_known_native_state(self):
        model=Sgp4Model(records());r,v=model.state([0],['X0_1'])
        np.testing.assert_allclose(r[0,0],[7577.98459373793,44.06019169689,19.22605094254],atol=1e-8,rtol=0)
        self.assertEqual(parse_tle(L1,L2).bstar,0)

    def test_bad_checksum_ssc_epoch_and_bstar(self):
        for a,b in [(L1[:-1]+'9',L2),(L1,L2[:2]+'10001'+L2[7:]),(fixed(L1[:18]+'27001.00000000'+L1[32:]),L2),(fixed(L1[:53]+' 12345-4'+L1[61:]),L2)]:
            with self.assertRaises(ValueError):parse_tle(a,b)
        with self.assertRaises(ValueError):parse_tle(L1,L2,10001)

    def test_duplicate_ids_and_catalog_numbers(self):
        rs=records();rs[1]['sat_name']=rs[0]['sat_name']
        with self.assertRaises(ValueError):Sgp4Model(rs)
        rs=records();rs[1]['ssc']=10000
        with self.assertRaises(ValueError):Sgp4Model(rs)

    def test_time_and_id_bounds(self):
        m=Sgp4Model(records())
        for t in (-1,86401,np.nan):
            with self.assertRaises(ValueError):m.state(t)
        with self.assertRaises(KeyError):m.state(0,['missing'])
        r,v=m.state([0,17.3,86400],['X1_1','X0_1']);self.assertEqual(r.shape,(3,2,3))

    def test_sgp4_not_constant_circular_radius(self):
        r,v=Sgp4Model(records()).state(np.linspace(0,86400,1000))
        self.assertGreater(np.ptp(np.linalg.norm(r[:,0],axis=1)),1.0)
        self.assertTrue(np.isfinite(v).all())

    def test_reader_rejects_archived_twobody_and_wrong_frame(self):
        p=PROJECT/'archive/twobody_20260921/outputs/ephemeris_20260918T135946_666110Z/ephemeris.npz'
        with self.assertRaises(ValueError):Ephemeris.load(p)
        for key,val in [('propagator','TwoBody'),('frame','TEME'),('native_frame','TEMEOfEpoch'),('epoch_utc','02 Jan 2026'),('tle_bundle_sha256','')]:
            meta=metadata();meta[key]=val
            with self.assertRaises(ValueError):Ephemeris([0,1],['A'],np.zeros((2,1,3)),np.zeros((2,1,3)),meta)

    def test_hermite_exact_cubic_and_derivative(self):
        t=np.array([0.,3.]);r=(t**3)[:,None,None]*np.ones((1,1,3));v=(3*t*t)[:,None,None]*np.ones((1,1,3))
        ep=Ephemeris(t,['A'],r,v,metadata());q=np.array([0.,0.37,2.,3.]);rr,vv=ep.state(q)
        np.testing.assert_allclose(rr[:,0,0],q**3,atol=1e-13);np.testing.assert_allclose(vv[:,0,0],3*q*q,atol=1e-13)
        with self.assertRaises(ValueError):ep.state(4)
        with self.assertRaises(ValueError):ep.state(1,['missing'])

    def test_archive_roundtrip_and_no_overwrite(self):
        ep=Ephemeris([0,1],['A'],np.ones((2,1,3)),np.zeros((2,1,3)),metadata())
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'e.npz';ep.save(p);loaded=Ephemeris.load(p)
            np.testing.assert_array_equal(loaded.state(0.5)[0],ep.state(0.5)[0])
            with self.assertRaises(FileExistsError):ep.save(p)

    def test_invalid_arrays(self):
        for t,ids,r in [([1,0],['A'],np.zeros((2,1,3))),([0,1],['A','A'],np.zeros((2,2,3))),([0,1],['A'],np.full((2,1,3),np.nan))]:
            with self.assertRaises(ValueError):Ephemeris(t,ids,r,np.zeros_like(r),metadata())
        np.testing.assert_array_equal(time_grid(65,30),[0,30,60,65])

    def test_sub_step_contact_detected(self):
        def state(t):
            r=np.zeros((len(t),2,3));r[:,:,0]=10;r[:,1,1]=5+(t-5)**2-0.01;return r
        report=search_windows(state,0,10,5,earth_radius_km=1,scan_step_s=2)
        np.testing.assert_allclose(report['roots_s'],[4.9,5.1],atol=0.001)
        self.assertTrue(any(x['state']=='visible' for x in report['intervals']))

    def test_tangent_retained_as_uncertain(self):
        def state(t):
            r=np.zeros((len(t),2,3));r[:,:,0]=10;r[:,1,1]=5+(t-5)**2;return r
        report=search_windows(state,0,10,5,earth_radius_km=1,scan_step_s=2)
        self.assertTrue(any(x['state']=='unresolved_grazing' for x in report['intervals']))
        self.assertFalse(any(x['state']=='visible' for x in report['intervals']))

    def test_actual_sgp4_boundary_resolution(self):
        report=geometry_windows(Sgp4Model(records()),['X0_1','X1_1'],stop_s=1000,max_range_km=1000)
        self.assertTrue(report['resolution_audit']['passed'])
        self.assertEqual(report['intervals'][0]['start_s'],0)
        self.assertEqual(report['intervals'][-1]['end_s'],1000)
        with self.assertRaises(ValueError):geometry_windows(Sgp4Model(records()),['X0_1','X0_1'])

    def test_formal_bundle_rejects_twobody_folder(self):
        with self.assertRaises((ValueError,FileNotFoundError)):Sgp4Model.load(PROJECT/'archive/twobody_20260921/outputs/gate_a_720_20260918T124844_819817Z')

if __name__=='__main__':unittest.main()
