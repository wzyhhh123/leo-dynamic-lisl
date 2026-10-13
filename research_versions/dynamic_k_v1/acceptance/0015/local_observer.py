"""P0F instance-only observers. No global monkeypatch of runtime classes."""
from types import MethodType
import support as w
old_auditor=w.old.load('p0f_auditor_base',w.V/'acceptance/0012/event_auditor.py')
from p0f_auditor_base import *
class InstanceAuditor(Auditor):
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
        oldintegrate=type(e)._integrate
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
        oldsettle=type(e)._settle_propagation_rate_events
        def settle(obj):
            if obj is not e:return oldsettle(obj)
            due=[x for x in sorted(e.propagation_agenda) if x.time_s<=e.now+1e-12]
            if due:a.boundary('BEFORE_PROPAGATION_EVENTS')
            out=oldsettle(obj)
            if due:a.boundary('AFTER_PROPAGATION_EVENTS')
            return out
        oldnext=type(e)._next_time
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
            (Engine,'_compensated_add',comp),(Engine,'_integrate',integrate),(Engine,'_settle_propagation_rate_events',settle),(Engine,'_next_time',nexttime)]:
            obj=e.queues if cls is QueueState else e.in_flight if cls is InFlightState else e
            local=fn if name=='_compensated_add' else MethodType(fn,obj)
            stack.enter_context(patch.object(obj,name,local))
        return stack
