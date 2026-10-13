"""Analytic event clock, FIFO, tail, and deliberate one-bit loss checks."""
import unittest,math,heapq
from fractions import Fraction as F
import support as w
from runtime.n4_p0f_events import ExactObservedD2Engine
from dynamic_lisl.in_flight import RateArrivalEvent
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment
from dynamic_lisl.commodity import Commodity
from runtime.n1b_evaluator import DeliveredFluidEvaluator
from runtime.n1b_fifo import DeliveredAgeLedger
N=tuple('S%03d'%i for i in range(160));a,b,c=N[:3];EXAMPLES={}
def engine(*,segments=None,edges=None,delay=1.,rate=10.):
    trace=PiecewiseConstantTrafficTrace(('f',),segments or [TrafficSegment(0.,1.,{'f':rate})])
    return ExactObservedD2Engine(N,edges if edges is not None else ((a,b),),2.**45,[Commodity('f',a,c if edges and (b,c) in edges else b)],
        trace,lambda edge,t:delay,TerminalExecutor(N),variant_binding=w.binding())
def evaluate(e,T):
    deps=w.old.old.dependencies()
    return DeliveredFluidEvaluator(e,T_s=T,time_tolerance_s=1e-9,energy_tolerance_J=1e-6,
        business_tolerance_bits=1e-6,n1a_binding=deps[0],n1b_binding=deps[1])
class EventClockTests(unittest.TestCase):
    def pulse(self,events):
        e=engine(rate=0.);e.now=1.;e.executor.advance(1.);e.propagation_agenda=list(events);heapq.heapify(e.propagation_agenda)
        e.in_flight.arrival_rates.clear();e.service_rates.clear();total=F();actual=[]
        for t in sorted({x.time_s for x in events}):
            old=e.now;rates=dict(e.in_flight.arrival_rates)
            total+=sum((F(v)*(F(t)-F(old)) for v in rates.values()),F())
            e.now=t;e._settle_propagation_rate_events();actual.append(dict(time=t,rates=dict(e.in_flight.arrival_rates)))
        return e,total,actual
    def test_01_no_early_positive_or_negative(self):
        t=math.nextafter(1.,math.inf);u=math.nextafter(t,math.inf)
        events=[RateArrivalEvent(t,1,(a,b),'f',2.**40),RateArrivalEvent(u,2,(a,b),'f',-2.**40)]
        e=engine(rate=0.);e.now=1.;e.propagation_agenda=events.copy();e._settle_propagation_rate_events()
        self.assertEqual(len(e.propagation_agenda),2);self.assertEqual(e.in_flight.arrival_rates.get(((a,b),'f'),0.),0.)
        e,total,actual=self.pulse(events);expected=F(2.**40)*(F(u)-F(t))
        self.assertEqual(total,expected);self.assertEqual(e.in_flight.arrival_rates[((a,b),'f')],0.)
        EXAMPLES['sub_ps_pulse']=dict(start=t,end=u,exact_integral_bit=str(total),actual_times=[r['time'] for r in actual])
    def test_02_true_simultaneous_events_multi_edges(self):
        events=[RateArrivalEvent(1.,1,(a,b),'f',10.),RateArrivalEvent(1.,2,(a,b),'f',-4.),
            RateArrivalEvent(1.,3,(b,c),'f',7.),RateArrivalEvent(2.,4,(a,b),'f',-6.),RateArrivalEvent(2.,5,(b,c),'f',-7.)]
        e,total,_=self.pulse(events);self.assertEqual(total,13);self.assertFalse(e.propagation_agenda)
    def test_03_extreme_short_positive_target_and_boundaries(self):
        e=engine(rate=0.);e.advance_to(1.);target=math.nextafter(1.,math.inf);e.advance_to(target)
        self.assertEqual(e.now,target);self.assertEqual(e.executor.now,target)
        with self.assertRaises(ValueError):e.advance_to(1.)
    def test_04_continuous_ulps_injection_fifo_exact_mass(self):
        t=1.;u=t+2.**-40;rate=2.**30
        e=engine(segments=[TrafficSegment(0.,t,{'f':0.}),TrafficSegment(t,u,{'f':rate}),TrafficSegment(u,2.,{'f':0.})],delay=2.**-20)
        ev=evaluate(e,3.);result=ev.run();expected=rate*(u-t)
        self.assertEqual(result['delivered_bits'],expected);self.assertEqual(e.arrived['f'],expected)
        self.assertEqual(result['age_accounting']['delivered_bits'],expected)
        self.assertEqual(result['age_accounting']['remaining_bit_age_integral_bit_s'],0.)
        EXAMPLES['continuous_short_fifo']=dict(bits=expected,delay=result['mean_delivered_fluid_delay_s'],age=result['delivered_bit_age_integral_bit_s'])
    def test_05_multihop_tail_delivery_and_age(self):
        ev=evaluate(engine(edges=((a,b),(b,c)),delay=.5),3.);r=ev.run()
        self.assertEqual(r['delivered_bits'],10.);self.assertEqual(r['delivered_bit_age_integral_bit_s'],10.)
        self.assertEqual(r['mean_delivered_fluid_delay_s'],1.)
    def test_06_explicit_real_one_bit_loss_rejected(self):
        ev=evaluate(engine(),3.);ev.run();ev.base.engine.delivered['f']-=1.
        with self.assertRaisesRegex(ValueError,'BUSINESS_CONSERVATION_MISMATCH'):ev.base.measure()
        EXAMPLES['loss_negative']=dict(deliberate_lost_bits=1.,threshold_bits=1e-6,rejected=True)
    def test_07_refresh_extreme_short_interval(self):
        e=engine(rate=0.);e.geometry_refresh_s=2.**-42;e.next_refresh=1.;e.now=1.;e.executor.advance(1.)
        e.advance_to(1.+2.**-41);self.assertEqual(e.now,1.+2.**-41);self.assertGreater(e.next_refresh,e.now)
if __name__=='__main__':
    result=w.old.old.test_module(__import__('__main__'));w.write(w.A/'analytic_tests.json',dict(**result,examples=EXAMPLES))
    print(result['status'],result['tests_run'],flush=True);raise SystemExit(result['status']!='PASS')
