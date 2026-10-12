"""Exact rational FIFO and unchanged D2 integration probes; engineering only."""
from copy import deepcopy
from fractions import Fraction as F
import importlib.util
from pathlib import Path
import sys
import unittest

V = Path(__file__).resolve().parents[1]
P = V.parents[1]
sys.path.insert(0,str(V))
sys.path.insert(0,str(P/'src'))
from runtime.n1b_fifo import LocalFIFO, Stream, Cohort, DeliveredAgeLedger
from runtime.n1b_observer import ObservedD2Engine
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine
from dynamic_lisl.terminal_executor import TerminalExecutor, Connect, Disconnect
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.commodity import Commodity
from runtime.n1b_evaluator import DeliveredFluidEvaluator, validate_n1b
from runtime.n1a import FixedHorizonEvaluator

N1A_BINDING = N1B_BINDING = None  # Pinned independently by acceptance runner.
EXAMPLES = {}

NODES = tuple('S%03d'%i for i in range(160))
A,B,C = NODES[:3]


def stream(start,end,rate,a=1,b=0):
    return Stream(F(start),F(end),F(rate),((F(1),F(a),F(b)),))


def engine(cls=ObservedD2Engine, *, rate=10., edges=None, capacity=20., delay=1.,
           destination=B, dynamic=False, segments=None):
    ex=TerminalExecutor(NODES)
    if dynamic:
        ex.submit([Connect((A,'D1'),(B,'D1'),100.,0.,0.,0.)])
    trace=PiecewiseConstantTrafficTrace(('f',),segments or [TrafficSegment(0.,1.,{'f':rate})])
    return cls(NODES, ((A,B),) if edges is None and not dynamic else (edges or ()),capacity,
               [Commodity('f',A,destination)],trace,lambda edge,t:delay,ex)


def underlying_document(e):
    # Compare ALL old state including terminal histories, counters and heaps.
    d=e.business_state() if isinstance(e,ObservedD2Engine) else e.__dict__
    def plain(value):
        if isinstance(value,dict):
            return sorted((repr(k),plain(v)) for k,v in value.items())
        if isinstance(value,(list,tuple)):
            return [plain(v) for v in value]
        if isinstance(value,(set,frozenset)):
            return sorted(map(repr,value))
        if hasattr(value,'__dict__'):
            return (type(value).__name__,plain(value.__dict__))
        if callable(value):
            return 'DETERMINISTIC_TEST_DELAY_PROVIDER'
        return value
    return plain(d)


class LocalFIFOExactTests(unittest.TestCase):
    def test_two_batch_continuous_exact_MD24_J39(self):
        q=LocalFIFO()
        q.advance_piece(0,1,[stream(0,1,6)],0)
        q.advance_piece(1,2,[],0)
        q.advance_piece(2,3,[stream(2,3,6)],0)
        sent=q.advance_piece(3,4,[],6)
        original=sum((s.moment() for s in sent),F())
        delivery=sum((s.rate*((s.end+1)**2-(s.start+1)**2)/2 for s in sent),F())
        self.assertEqual(delivery-original,24)
        self.assertEqual((delivery-original)/6,4)
        self.assertEqual(5*q.total()-q.original_moment(),15)
        self.assertEqual(delivery-original+5*q.total()-q.original_moment(),39)

    def test_proportional_merge_not_edge_order_exact_partial_MD23(self):
        results=[]
        inputs=[stream(4,5,2,1,-4),stream(4,5,6,1,-2)]
        for ordered in (inputs,inputs[::-1]):
            q=LocalFIFO()
            q.advance_piece(4,5,ordered,0)
            sent=q.advance_piece(6,7,[],4)
            md=sum((s.rate*((s.end+1)**2-(s.start+1)**2)/2-s.moment() for s in sent),F())
            self.assertEqual(md,23)
            self.assertEqual(q.total(),4)
            results.append((sent,q.rows))
        self.assertEqual(results[0],results[1])

    def test_local_order_not_global_injection_order(self):
        q=LocalFIFO()
        q.advance_piece(2,3,[stream(2,3,1,1,-1)],0)  # original1..2
        q.advance_piece(3,4,[stream(3,4,1,1,-3)],0)  # original0..1, arrives later
        sent=q.advance_piece(4,5,[],1)
        self.assertEqual(sum((s.moment() for s in sent),F()),F(3,2))

    def test_continuous_partial_service_keeps_distribution(self):
        q=LocalFIFO()
        sent=q.advance_piece(0,1,[stream(0,1,10)],4)
        self.assertEqual(q.total(),6)
        self.assertEqual(sum((s.moment() for s in sent),F()),F(4,5))
        self.assertEqual(q.original_moment(),F(21,5))

    def test_closure_impulse_retains_distribution_and_mixes_ties(self):
        results=[]
        c1=Cohort(F(2),((F(1),F(1,2),F(0)),),F(3),F())
        c2=Cohort(F(6),((F(1),F(1,6),F(2)),),F(3),F())
        for rows in ((c1,c2),(c2,c1)):
            q=LocalFIFO()
            for c in rows:q.append_impulse(deepcopy(c))
            s=q.advance_piece(4,5,[],4)
            results.append(s)
        self.assertEqual(results[0],results[1])
        self.assertTrue(any(a for s in results[0] for w,a,b in s.components))


class D2AgeIntegrationTests(unittest.TestCase):
    def test_read_only_observer_does_not_repeat_delay_queries(self):
        class CountingDelay:
            def __init__(self):self.calls=[]
            def __call__(self,edge,t):self.calls.append((edge,t));return 1.
        old,new=engine(TransitionAwareNetworkServiceEngine),engine()
        old.delay,new.delay=CountingDelay(),CountingDelay()
        old.advance_to(4.);new.advance_to(4.)
        self.assertGreater(len(old.delay.calls),0)
        self.assertEqual(underlying_document(old),underlying_document(new))

    def test_multicommodity_intermediate_queue_old_allocation_unchanged(self):
        def make(cls):
            trace=PiecewiseConstantTrafficTrace(('f','g'),[TrafficSegment(0.,1.,{'f':10.,'g':10.}),
                                                       TrafficSegment(1.,3.,{'f':0.,'g':10.})])
            return cls(NODES,((A,B),(B,C)),10.,[Commodity('f',A,C),Commodity('g',B,C)],
                       trace,lambda edge,t:1.,TerminalExecutor(NODES))
        old,new=make(TransitionAwareNetworkServiceEngine),make(ObservedD2Engine)
        age=DeliveredAgeLedger(new)
        old.advance_to(2.);new.advance_to(2.);age.consume(new)
        self.assertEqual(underlying_document(old),underlying_document(new))
        self.assertGreater(age.queue[(B,'f')].total(),0)
        old.advance_to(6.);new.advance_to(6.);age.consume(new)
        self.assertEqual(underlying_document(old),underlying_document(new))
        self.assertEqual(age.metrics()['delivered_bits'],40.)
        self.assertAlmostEqual(age.metrics()['delivered_bit_age_integral_bit_s'],sum(new.objective_by_commodity.values()))

    def test_all_real_D2_transition_fixtures_unchanged_and_age_conserved(self):
        from dynamic_lisl.gate_d2_fixtures import SMALL_FIXTURE_BUILDERS
        for name,builder in SMALL_FIXTURE_BUILDERS.items():
            with self.subTest(case=name):
                old,new=builder(),builder()
                new.__class__=ObservedD2Engine;new.age_observations=[]
                age=DeliveredAgeLedger(new)
                old.advance_to(30.);new.advance_to(30.);age.consume(new)
                self.assertEqual(underlying_document(old),underlying_document(new))
                m=age.metrics()
                self.assertLessEqual(abs(sum(new.objective_by_commodity.values())-m['delivered_bit_age_integral_bit_s']
                    -m['remaining_bit_age_integral_bit_s']),2*m['delivered_age_absolute_error_bound_bit_s']+1e-3)

    def test_real_D2_two_batch_exact_MD24_J39(self):
        segments=[TrafficSegment(0.,1.,{'f':6.}),TrafficSegment(1.,2.,{'f':0.}),TrafficSegment(2.,3.,{'f':6.})]
        e=engine(dynamic=True,capacity=6.,segments=segments)
        e.executor.submit([Disconnect((A,'D1'),(B,'D1'))])
        age=DeliveredAgeLedger(e)
        e.advance_to(3.);age.consume(e)
        e.executor.submit([Connect((A,'D1'),(B,'D1'),100.,0.,0.,0.)])
        e.advance_to(4.);age.consume(e)
        e.executor.submit([Disconnect((A,'D1'),(B,'D1'))])
        e.advance_to(5.);age.consume(e)
        m=age.metrics()
        self.assertEqual(m['delivered_bit_age_integral_bit_s'],24.)
        self.assertEqual(m['mean_delivered_fluid_delay_s'],4.)
        self.assertEqual(m['remaining_bit_age_integral_bit_s'],15.)
        self.assertEqual(sum(e.objective_by_commodity.values()),39.)
        EXAMPLES['two_batch_FIFO_MD24_mean4_J39']=dict(scope='ENGINEERING_ANALYTICAL_CASE',
            age_accounting=m, J_T_bit_s=sum(e.objective_by_commodity.values()))

    def test_real_D2_simultaneous_two_incoming_edges_merge(self):
        mid,dest=NODES[3:5]
        segments=[TrafficSegment(0.,1.,{'f':2.}),TrafficSegment(1.,2.,{'f':0.}),TrafficSegment(2.,3.,{'f':6.})]
        ex=TerminalExecutor(NODES);ex.submit([Connect((A,'D1'),(B,'D1'),100.,0.,0.,0.)])
        trace=PiecewiseConstantTrafficTrace(('f',),segments)
        e=ObservedD2Engine(NODES,((B,mid),(C,mid),(mid,dest)),20.,[Commodity('f',A,dest)],trace,
                          lambda edge,t:3. if edge==(A,B) else 1.,ex)
        age=DeliveredAgeLedger(e)
        e.advance_to(1.);age.consume(e)
        ex.submit([Disconnect((A,'D1'),(B,'D1'))])
        e.advance_to(2.);age.consume(e)
        ex.submit([Connect((A,'D1'),(C,'D1'),100.,0.,0.,0.)])
        e.advance_to(5.5);age.consume(e)
        m=age.metrics()
        self.assertEqual(m['delivered_bits'],4.)
        self.assertEqual(m['delivered_bit_age_integral_bit_s'],14.)
        self.assertEqual(m['mean_delivered_fluid_delay_s'],3.5)
        remaining=age.queue[(mid,'f')].total()
        self.assertEqual(remaining,0)

    def test_single_link_all_delivered(self):
        e=engine(); age=DeliveredAgeLedger(e)
        e.advance_to(4.); age.consume(e)
        m=age.metrics()
        self.assertEqual((m['delivered_bits'],m['delivered_bit_age_integral_bit_s'],m['mean_delivered_fluid_delay_s']),(10.,10.,1.))

    def test_two_hop_queue_and_propagation(self):
        e=engine(edges=((A,B),(B,C)),destination=C); age=DeliveredAgeLedger(e)
        e.advance_to(5.); age.consume(e)
        self.assertEqual(age.metrics()['delivered_bit_age_integral_bit_s'],20.)

    def test_no_route_no_delivery_null(self):
        e=engine(edges=()); age=DeliveredAgeLedger(e)
        e.advance_to(4.);age.consume(e)
        self.assertIsNone(age.metrics()['mean_delivered_fluid_delay_s'])
        self.assertEqual(age.metrics()['remaining_bit_age_integral_bit_s'],35.)

    def test_restore_after_wait_and_J_identity(self):
        e=engine(dynamic=True,rate=0.);e.executor.submit([Disconnect((A,'D1'),(B,'D1'))])
        e.trace=PiecewiseConstantTrafficTrace(('f',),[TrafficSegment(0.,1.,{'f':10.})])
        e.boundaries=list(e.trace.boundaries_after(0.))
        age=DeliveredAgeLedger(e)
        e.advance_to(2.); age.consume(e)
        e.executor.submit([Connect((A,'D1'),(B,'D1'),100.,0.,0.,0.)])
        e.advance_to(4.);age.consume(e)
        self.assertEqual(age.metrics()['delivered_bit_age_integral_bit_s'],27.5)
        self.assertEqual(sum(e.objective_by_commodity.values()),27.5)

    def test_partial_T_remaining_identity(self):
        e=engine(capacity=4.);age=DeliveredAgeLedger(e)
        e.advance_to(2.);age.consume(e)
        m=age.metrics()
        self.assertEqual(m['delivered_bits'],4.)
        self.assertEqual(m['delivered_bit_age_integral_bit_s'],5.2)
        self.assertEqual(m['remaining_bit_age_integral_bit_s'],7.8)
        self.assertEqual(m['exact_rational']['M_D_bit_s'],'26/5')
        self.assertEqual(m['delivered_bit_age_integral_bit_s']+m['remaining_bit_age_integral_bit_s'],sum(e.objective_by_commodity.values()))

    def test_observer_all_legacy_state_exactly_unchanged(self):
        for kwargs in ({},{'capacity':4.},{'edges':()},{'dynamic':True}):
            with self.subTest(kwargs=kwargs):
                old,new=engine(TransitionAwareNetworkServiceEngine,**kwargs),engine(**kwargs)
                old.advance_to(4.);new.advance_to(4.)
                self.assertEqual(underlying_document(old),underlying_document(new))

    def test_clone_checkpoint_restore_replay(self):
        e=engine(); age=DeliveredAgeLedger(e)
        e.advance_to(.5);age.consume(e)
        restored=e.clone(); restored_age=age.clone()
        e.advance_to(4.);age.consume(e)
        restored.advance_to(4.);restored_age.consume(restored)
        self.assertEqual(age.metrics(),restored_age.metrics())
        self.assertEqual(underlying_document(e),underlying_document(restored))

    def test_real_natural_expiry_numerical_closure_no_synthetic_birth(self):
        from dynamic_lisl.gate_d2_fixtures import fixture_g_natural_expiry
        old=fixture_g_natural_expiry();e=fixture_g_natural_expiry()
        e.__class__=ObservedD2Engine;e.age_observations=[]
        age=DeliveredAgeLedger(e)
        old.advance_to(30.);e.advance_to(30.);age.consume(e)
        self.assertEqual(underlying_document(old),underlying_document(e))
        self.assertTrue(e.propagation_closure_events)
        self.assertGreaterEqual(age.metrics()['delivered_age_absolute_error_bound_bit_s'],0.)

    def test_unknown_closure_rejected_even_if_tiny(self):
        from runtime.n1b_fifo import AgeSemanticConflict
        e=engine();age=DeliveredAgeLedger(e)
        with self.assertRaisesRegex(AgeSemanticConflict,'NO_KNOWN_SOURCE'):
            age._closure(dict(edge=(A,B),commodity_id='f',time_s=0.,closed_bits=1e-16,credited_to='DELIVERED'))

    def test_nonbinary_continuous_trace_not_falsely_exact(self):
        e=engine(rate=.3,capacity=.2,delay=.1);age=DeliveredAgeLedger(e)
        e.advance_to(4.);age.consume(e)
        m=age.metrics()
        self.assertEqual(m['metric_status'],'IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT')
        self.assertGreater(m['delivered_age_absolute_error_bound_bit_s'],0.)


class N1bEvaluationTests(unittest.TestCase):
    def evaluator(self,e,T=4.):
        self.assertIsNotNone(N1B_BINDING,'Use pinned N1b acceptance runner')
        return DeliveredFluidEvaluator(e,T_s=T,time_tolerance_s=1e-9,energy_tolerance_J=1e-6,
            business_tolerance_bits=1e-6,n1a_binding=N1A_BINDING,n1b_binding=N1B_BINDING)

    def test_fixed_T_all_N1a_fields_exactly_unchanged(self):
        for kwargs in ({},{'capacity':4.},{'edges':()},{'dynamic':True},{'rate':.3,'capacity':.2,'delay':.1}):
            with self.subTest(case=kwargs):
                old=FixedHorizonEvaluator(engine(TransitionAwareNetworkServiceEngine,**kwargs),T_s=4.,
                    time_tolerance_s=1e-9,energy_tolerance_J=1e-6,business_tolerance_bits=1e-6,
                    evidence_binding=N1A_BINDING).run()
                new=self.evaluator(engine(**kwargs)).run()
                self.assertEqual(new['n1a_result'],old)
                EXAMPLES[repr(kwargs)]=new

    def test_wrapper_checkpoint_clone_restore_and_replay(self):
        ev=self.evaluator(engine(capacity=4.))
        ev.advance_to(.5)
        restored=DeliveredFluidEvaluator.restore(ev.checkpoint())
        clone=ev.clone()
        r=ev.run()
        self.assertEqual(r,restored.run());self.assertEqual(r,clone.run())

    def test_zero_delivery_null_and_remaining(self):
        r=self.evaluator(engine(edges=())).run()
        self.assertIsNone(r['mean_delivered_fluid_delay_s'])
        self.assertEqual(r['delivered_bit_age_integral_bit_s'],0.)
        self.assertEqual(r['age_accounting']['remaining_bit_age_integral_bit_s'],35.)

    def test_measured_range_and_cross_field_rejection(self):
        r=self.evaluator(engine()).run()
        for field,value in [('mean_delivered_fluid_delay_s',0.),('delivered_bits',11.),
                            ('delivered_bit_age_integral_bit_s',-1.),('mean_delay_absolute_error_bound_s',float('nan'))]:
            bad=deepcopy(r);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_n1b(bad)


if __name__=='__main__':unittest.main()
