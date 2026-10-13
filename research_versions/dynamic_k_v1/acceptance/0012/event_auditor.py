"""Read-only observations, exact binary rational references, unchanged calls.

All production methods execute once. No reference result is written into the
engine. Only dictionaries.get/items (never defaultdict subscripting) are used
for extra reads. Assertions and exceptions are preserved.
"""
import inspect,json,math
from collections import Counter,defaultdict
from contextlib import ExitStack
from decimal import Decimal
from fractions import Fraction as F
from unittest.mock import patch
from dynamic_lisl.queue_state import QueueState
from dynamic_lisl.in_flight import InFlightState
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine as Engine

def fraction(x):return F(float(x))
def fp(x):
    x=float(x);p,q=x.as_integer_ratio()
    return dict(repr=repr(x),hex=x.hex(),numerator=str(p),denominator=str(q),exact_decimal=str(Decimal.from_float(x)))
def exact(x):return dict(rational=str(x),approx_bits=float(x))
def rows(mapping):return [dict(key=list(k) if isinstance(k,tuple) else k,value=fp(v)) for k,v in mapping.items()]
def exact_total(mapping,commodity=None):
    return sum((fraction(v) for k,v in mapping.items() if commodity is None or (k[1] if isinstance(k,tuple) else k)==commodity),F())
def mass_reference(e,commodity=None):
    return exact_total(e.arrived,commodity)-exact_total(e.delivered,commodity)-exact_total(e.queues.bits,commodity)-exact_total(e.in_flight.bits,commodity)

class Auditor:
    def __init__(self,engine,ledger,directory):
        self.e=engine;self.ledger=ledger;self.files={n:(directory/(n+'.jsonl')).open('x',encoding='utf-8',newline='\n') for n in ('boundaries','operations','intervals','next_events')}
        self.seq=0;self.boundary_seq=0;self.interval=None;self.counts=Counter()
        self.errors=defaultdict(F);self.absolute_errors=defaultdict(F);self.clamps=defaultdict(F)
        self.transfer=defaultdict(F);self.initial={c.commodity_id:mass_reference(engine,c.commodity_id) for c in engine.commodities}
        self.first_clip=None;self.first_threshold=None;self.largest_clip=None;self.boundaries=[];self.operations=[]
    def emit(self,kind,row):self.files[kind].write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
    def close(self):
        for stream in self.files.values():stream.close()
    def current_totals(self):
        e=self.e;a=math.fsum(e.arrived.values());d=math.fsum(e.delivered.values());q=math.fsum(e.queues.bits.values());i=math.fsum(e.in_flight.bits.values());n=q+i
        return dict(A=fp(a),D=fp(d),Q=fp(q),I=fp(i),N=fp(n),
            A_minus_D_minus_QI=fp((a-d)-n),A_minus_D_plus_QI=fp(a-(d+n)),
            exact_IEEE_operand_residual=exact(mass_reference(e)),
            fsum_signed_all_terms=fp(math.fsum([*e.arrived.values(),*(-v for v in e.delivered.values()),*(-v for v in e.queues.bits.values()),*(-v for v in e.in_flight.bits.values())])))
    def boundary(self,label):
        e=self.e;self.boundary_seq+=1;by={}
        for c in e.commodities:
            k=c.commodity_id;a=e.arrived.get(k,0.);d=e.delivered.get(k,0.);q=math.fsum(v for (_,key),v in e.queues.bits.items() if key==k);i=math.fsum(v for (_,key),v in e.in_flight.bits.items() if key==k)
            predicted=self.initial[k]+self.transfer[k]+self.errors[k]
            actual=mass_reference(e,k)
            if actual!=predicted:raise AssertionError('READ_ONLY_ERROR_DECOMPOSITION_NOT_CLOSED:'+k)
            by[k]=dict(A=fp(a),D=fp(d),Q=fp(q),I=fp(i),D2_sequential_error=fp(((a-d)-q)-i),
                exact_residual=exact(actual),initial_exact_residual=exact(self.initial[k]),
                exact_signed_expected_transfers=exact(self.transfer[k]),exact_cumulative_update_error=exact(self.errors[k]),
                exact_cumulative_absolute_update_error=exact(self.absolute_errors[k]),exact_clip_mass_gain=exact(self.clamps[k]))
        row=dict(index=self.boundary_seq,label=label,time_s=e.now,time=fp(e.now),
            accounting_interval=self.interval,totals=self.current_totals(),by_commodity=by,
            original_queue_order=rows(e.queues.bits),original_flight_order=rows(e.in_flight.bits),
            original_arrived_order=rows(e.arrived),original_delivered_order=rows(e.delivered),
            arrived_compensation=rows(e.arrived_compensation),delivered_compensation=rows(e.delivered_compensation),
            completed_operation_count=self.seq,
            propagated_events=[dict(time=fp(x.time_s),sequence=x.sequence,edge=list(x.edge),commodity=x.commodity_id,delta_rate=fp(x.delta_rate_bit_s)) for x in sorted(e.propagation_agenda)])
        self.emit('boundaries',row)
        self.boundaries.append(dict(index=row['index'],label=label,time_s=e.now,residual_bits=row['totals']['exact_IEEE_operand_residual']['approx_bits'],
            exact_residual=row['totals']['exact_IEEE_operand_residual']['rational'],op_count=self.seq))
        if self.first_threshold is None and abs(mass_reference(e))>F(1e-6):self.first_threshold=row
    def update(self,kind,key,before,after,delta,*,source,clamp=0.,rounded=None,comp_before=None,comp_after=None):
        sign=1 if kind=='A' else -1;commodity=key if kind in ('A','D') else key[1]
        err=fraction(after)-fraction(before)-fraction(delta);signed=sign*err
        self.errors[commodity]+=signed;self.absolute_errors[commodity]+=abs(err);self.transfer[commodity]+=sign*fraction(delta)
        self.clamps[commodity]+=fraction(clamp);self.seq+=1;self.counts[kind]+=1
        row=dict(index=self.seq,kind=kind,key=key,commodity=commodity,time=fp(self.e.now),accounting_interval=self.interval,
            caller=source,before=fp(before),actual_increment=fp(delta),after=fp(after),
            exact_update_error=exact(err),signed_global_mass_error=exact(signed),clip_mass_gain=fp(clamp),
            nonclip_arithmetic_error=exact(err-fraction(clamp)),preclip_rounded_sum=fp(rounded) if rounded is not None else None,
            compensation_before=fp(comp_before) if comp_before is not None else None,compensation_after=fp(comp_after) if comp_after is not None else None)
        self.emit('operations',row);self.operations.append(row)
        if clamp>0:
            if self.first_clip is None:self.first_clip=row
            if self.largest_clip is None or clamp>float.fromhex(self.largest_clip['clip_mass_gain']['hex']):self.largest_clip=row
    def context(self):
        a=self;e=self.e;stack=ExitStack()
        qadd=QueueState.add;iadd=InFlightState.add_bits;iset=InFlightState.set_bits;qset=QueueState.set
        def queue(obj,node,key,delta,tolerance=1e-7):
            if obj is not e.queues:return qadd(obj,node,key,delta,tolerance)
            k=(node,key);b=obj.bits.get(k,0.);d=float(delta);r=b+d;caller=inspect.currentframe().f_back
            out=qadd(obj,node,key,delta,tolerance)
            a.update('Q',k,b,obj.bits.get(k,0.),d,source=dict(file=caller.f_code.co_filename,line=caller.f_lineno,function=caller.f_code.co_name),
                clamp=max(0.,-r),rounded=r);return out
        def flight(obj,edge,key,delta,tolerance=1e-6):
            if obj is not e.in_flight:return iadd(obj,edge,key,delta,tolerance)
            k=(edge,key);b=obj.bits.get(k,0.);d=float(delta);r=b+d;caller=inspect.currentframe().f_back
            out=iadd(obj,edge,key,delta,tolerance)
            a.update('I',k,b,obj.bits.get(k,0.),d,source=dict(file=caller.f_code.co_filename,line=caller.f_lineno,function=caller.f_code.co_name),
                clamp=max(0.,-r),rounded=r);return out
        def setflight(obj,edge,key,value,tolerance=1e-6):
            if obj is not e.in_flight:return iset(obj,edge,key,value,tolerance)
            k=(edge,key);b=obj.bits.get(k,0.);v=float(value);caller=inspect.currentframe().f_back
            out=iset(obj,edge,key,value,tolerance)
            # Exact set operation: desired delta is exact(value)-exact(before),
            # not a newly rounded subtraction. Closure uses value=0 exactly.
            d=v-b;assert fraction(d)==fraction(v)-fraction(b),'SET_DELTA_REFERENCE_NOT_EXACT'
            a.update('I',k,b,obj.bits.get(k,0.),d,source=dict(file=caller.f_code.co_filename,line=caller.f_lineno,function=caller.f_code.co_name),clamp=max(0.,-v));return out
        def setqueue(obj,node,key,value,tolerance=1e-7):
            if obj is not e.queues:return qset(obj,node,key,value,tolerance)
            k=(node,key);b=obj.bits.get(k,0.);v=float(value);caller=inspect.currentframe().f_back;out=qset(obj,node,key,value,tolerance)
            d=v-b;assert fraction(d)==fraction(v)-fraction(b)
            a.update('Q',k,b,obj.bits.get(k,0.),d,source=dict(file=caller.f_code.co_filename,line=caller.f_lineno,function=caller.f_code.co_name),clamp=max(0.,-v));return out
        oldcomp=Engine._compensated_add
        def comp(values,compensations,key,increment):
            kind='A' if values is e.arrived else 'D' if values is e.delivered else None
            if kind is None:return oldcomp(values,compensations,key,increment)
            b=values.get(key,0.);c=compensations.get(key,0.);caller=inspect.currentframe().f_back
            out=oldcomp(values,compensations,key,increment)
            a.update(kind,key,b,values.get(key,0.),increment,source=dict(file=caller.f_code.co_filename,line=caller.f_lineno,function=caller.f_code.co_name),comp_before=c,comp_after=compensations.get(key,0.));return out
        oldintegrate=Engine._integrate
        def integrate(obj,next_time,external,inputs,derivative,delivery):
            if obj is not e:return oldintegrate(obj,next_time,external,inputs,derivative,delivery)
            start=e.now;dt=next_time-start;a.interval=dict(start=fp(start),end=fp(next_time),dt=fp(dt))
            a.boundary('BEFORE_INTEGRATE');begin=mass_reference(e);op=a.seq
            products=[]
            for label,mapping in [('EXTERNAL',external),('SERVICE',e.service_rates),('ARRIVAL',e.in_flight.arrival_rates)]:
                for k,rate in (mapping.items() if label=='EXTERNAL' else sorted(mapping.items())):
                    p=float(rate)*dt;ideal=fraction(rate)*(fraction(next_time)-fraction(start))
                    products.append(dict(kind=label,key=k,rate=fp(rate),product=fp(p),exact_rate_times_exact_dt=exact(ideal),product_rounding=exact(fraction(p)-ideal)))
            out=oldintegrate(obj,next_time,external,inputs,derivative,delivery)
            a.boundary('AFTER_INTEGRATE');a.emit('intervals',dict(start=fp(start),end=fp(next_time),dt=fp(dt),products=products,
                original_external_order=list(external),original_service_order=[k for k,_ in sorted(e.service_rates.items())],
                original_arrival_order=[k for k,_ in sorted(e.in_flight.arrival_rates.items())],
                actual_mass_error_change=exact(mass_reference(e)-begin),first_operation=op+1,last_operation=a.seq,
                original_inputs=rows(inputs),original_queue_derivatives=rows(derivative),original_delivery_rates=rows(delivery)))
            a.interval=None;return out
        oldsettle=Engine._settle_propagation_rate_events
        def settle(obj):
            if obj is not e:return oldsettle(obj)
            due=[x for x in sorted(e.propagation_agenda) if x.time_s<=e.now+1e-12]
            if due:a.boundary('BEFORE_PROPAGATION_EVENTS')
            out=oldsettle(obj)
            if due:a.boundary('AFTER_PROPAGATION_EVENTS')
            return out
        oldnext=Engine._next_time
        def nexttime(obj,limit,derivative):
            if obj is not e:return oldnext(obj,limit,derivative)
            candidates=[]
            for (node,k),d in derivative.items():
                b=e.queues.bits.get((node,k),0.)
                if b>e.state_tol and d<-1e-15:
                    t=e.now+b/(-d);candidates.append(dict(node=node,commodity=k,backlog=fp(b),derivative=fp(d),
                        exhaustion_time=fp(t),exact_exhaustion_time=exact(fraction(e.now)+fraction(b)/-fraction(d)),
                        passes_forward_filter=t>e.now+1e-13))
            result=oldnext(obj,limit,derivative)
            a.emit('next_events',dict(now=fp(e.now),limit=fp(limit),selected=fp(result),queue_exhaustion_candidates=candidates,
                propagation_head=e.propagation_agenda[0].__dict__ if e.propagation_agenda else None,terminal_head=e.executor.events[0] if e.executor.events else None))
            return result
        for cls,name,fn in [(QueueState,'add',queue),(QueueState,'set',setqueue),(InFlightState,'add_bits',flight),(InFlightState,'set_bits',setflight),
            (Engine,'_compensated_add',staticmethod(comp)),(Engine,'_integrate',integrate),(Engine,'_settle_propagation_rate_events',settle),(Engine,'_next_time',nexttime)]:stack.enter_context(patch.object(cls,name,fn))
        return stack
    def summary(self):
        return dict(initial_exact_residual_by_commodity={k:exact(v) for k,v in self.initial.items()},
            update_count=self.seq,update_counts=dict(self.counts),boundary_count=self.boundary_seq,first_clip=self.first_clip,
            largest_clip=self.largest_clip,first_boundary_above_N1a_threshold=self.first_threshold,
            final_by_commodity={k:dict(initial=exact(self.initial[k]),expected_transfers=exact(self.transfer[k]),
                exact_update_error=exact(self.errors[k]),absolute_update_error_bound=exact(self.absolute_errors[k]),clip_mass_gain=exact(self.clamps[k])) for k in self.initial},
            final_totals=self.current_totals(),boundaries=self.boundaries,
            decomposition_exactly_closed=True,original_methods_once=True,state_substitutions=False,tolerances_changed=False)
