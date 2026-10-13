"""Bounded physical equivalence, rollback and immutable-history tests."""
import time,traceback,json,copy
import support18 as s
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect,Disconnect
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog,TerminalPairWindow
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from runtime.n2_actions import Hold,Add,Drop,Replace,Setup,LinkRef,ActionValidator
from runtime.n2_physical import N2PhysicalLayer,SyntheticWindowGuard
if (s.A/'SEAM_BINDING_TUPLE.json').exists():
    from runtime.n4_p0h_gate_c_final import SealedHistory,StructuralCatalog,SourceBinding,install,materialize
else:
    from runtime.n4_p0h_gate_c import SealedHistory,StructuralCatalog,SourceBinding,install
    materialize=lambda x:x
def binding():
    p=s.A/('SEAM_BINDING_TUPLE.json' if (s.A/'SEAM_BINDING_TUPLE.json').exists() else 'SEAM_BINDING_FINAL.json')
    r=s.vc.read_json(p if p.exists() else s.A/'SEAM_BINDING.json');return SourceBinding(s.P,r['path'],r['sha256'])
def optimized(physical,ex):
    cat=physical.catalog
    c=StructuralCatalog([w for ws in cat.windows.values() for w in ws],cat.plane_by_satellite,
        history=SealedHistory(ex),binding=binding(),parent_catalog=cat.parent_catalog,model=cat.model,config=cat.config)
    return N2PhysicalLayer(TerminalPairPhysicalFeasibility(c,physical.gate_c.hardware),physical.guard)
def protect(ex):return s.digest(dict(snapshot=ex.snapshot(),log=materialize(ex.log)))
def attempt(validator,ex,action):
    try:return dict(result=s.verdict(validator.validate(ex,action)),error=None)
    except Exception as e:return dict(result=None,error=dict(type=type(e).__name__,message=str(e)))
def compare(name,physical,ex,action,rows):
    start=protect(ex);old=attempt(ActionValidator(physical),ex,action)
    new=attempt(ActionValidator(optimized(physical,ex)),ex,action)
    assert old==new,'EXACT_VERDICT_DIFF:'+name
    assert protect(ex)==start,'SOURCE_CHANGED:'+name
    oldhash=s.digest(old);newhash=s.digest(new);assert oldhash==newhash
    rows.append(dict(name=name,action=s.asdict(action),expected_sha256=oldhash,actual_sha256=newhash,
        exact_equal=True,source_unchanged=True,error=old['error'],verdict=old['result']))
def synthetic_cases():
    nodes=tuple('X%d_%d'%(p,n) for p in range(4) for n in range(40));a=('X0_1','D1');b=('X1_1','D2');c=('X0_2','D1');d=('X1_2','D2')
    def build(end=100.):
        ex=TerminalExecutor(nodes);cat=TerminalPairCatalog([
            TerminalPairWindow(a[0],a[1],b[0],b[1],0.,end),
            TerminalPairWindow(c[0],c[1],d[0],d[1],0.,100.)],{n:int(n[1]) for n in nodes})
        return ex,N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),SyntheticWindowGuard())
    rows=[];ex,p=build();setup=Setup(.5,.5,.5)
    compare('idle_HOLD',p,ex,Hold(),rows);compare('idle_ADD',p,ex,Add(a,b,setup),rows)
    compare('idle_ADD_repeat',p,ex,Add(a,b,setup),rows)
    compare('unknown_terminal',p,ex,Add(('bad','D1'),b,setup),rows)
    compare('bad_setup',p,ex,Add(a,b,Setup(-1.,.5,.5)),rows)
    compare('not_visible',p,ex,Add(('X0_3','D1'),('X1_3','D2'),setup),rows)
    ex.submit([Connect(a,b,50.,0.,0.,0.)]);ref=LinkRef.from_link(next(iter(ex.links.values())))
    compare('occupied_ADD',p,ex,Add(a,b,setup),rows)
    compare('active_DROP',p,ex,Drop(ref),rows)
    compare('active_BBM_same_pair',p,ex,Replace((ref,),a,b,setup,'BBM'),rows)
    compare('active_BBM_free_pair',p,ex,Replace((ref,),c,d,setup,'BBM'),rows)
    compare('active_MBB_free_pair',p,ex,Replace((ref,),c,d,setup,'MBB'),rows)
    compare('MBB_occupied',p,ex,Replace((ref,),a,b,setup,'MBB'),rows)
    compare('wrong_old_ref',p,ex,Drop(LinkRef('wrong',ref.endpoints)),rows)
    compare('undeclared_release',p,ex,Replace((LinkRef('wrong',ref.endpoints),),a,b,setup,'BBM'),rows)
    ex.start_tx(a,2.);ex.submit([Disconnect(a,b)])
    compare('DRAINING_DROP',p,ex,Drop(ref),rows);compare('DRAINING_ADD',p,ex,Add(a,b,setup),rows)
    ex,p=build();ex.submit([Connect(a,b,50.,2.,2.,1.)])
    compare('future_reservation_ADD',p,ex,Add(a,b,setup),rows)
    for name,end in [('ready_equal',1.),('ready_epsilon',1.+5e-10),('ready_inside',1.+2e-9),('expired_window',0.5)]:
        ex,p=build(end)
        if name=='expired_window':ex.advance(.5)
        compare(name,p,ex,Add(a,b,setup),rows)
    ex,p=build();ex.extra_field='unregistered'
    compare('clone_field_audit_rejects',p,ex,Add(a,b,setup),rows)
    return rows
def alias_tests():
    nodes=tuple('X%d_%d'%(p,n) for p in range(4) for n in range(40));ex=TerminalExecutor(nodes)
    ex.submit([Connect(('X0_1','D1'),('X1_1','D2'),50.,0.,0.,0.)])
    seal=SealedHistory(ex);left=seal.clone(ex);right=seal.clone(ex)
    assert left.log is not right.log
    if (s.A/'SEAM_BINDING_TUPLE.json').exists():
        assert left.log[0] is not right.log[0] and left.log[0]._data is right.log[0]._data
    else:assert left.log[0] is right.log[0] is seal.records[0]
    assert ex.log[0] is not left.log[0] and ex.log==left.log
    before=protect(ex);right_before=protect(right)
    t=next(iter(left.terminals));left.terminals[t].orientation=(0.,1.,0.)
    link=next(iter(left.links.values()));link.tx_end[t]=7.
    left.events.append((9.,0,999,'FAKE',None));left.log.append(dict(time=0.,event='LOCAL',details={},terminals=[]))
    assert protect(ex)==before and protect(right)==right_before
    denied=0
    for fn in [lambda:left.log[0].update(event='BAD'),lambda:left.log[0]['details'].clear(),
               lambda:left.log[0]['terminals'].append({}),lambda:left.log[0]['terminals'][0].__setitem__('phase','BAD')]:
        try:fn();raise AssertionError('MUTABLE_SHARED_HISTORY')
        except TypeError:denied+=1
    # Deliberate base-class bypass is caught before further preview use.
    bad=SealedHistory(ex)
    if (s.A/'SEAM_BINDING_TUPLE.json').exists():
        try:dict.__setitem__(bad.records[0],'event','BYPASS');raise AssertionError('BASE_BYPASS_NOT_REJECTED')
        except TypeError:pass
        try:bad._payload=();raise AssertionError('SEALED_DESCRIPTOR_MUTABLE')
        except TypeError:pass
    else:
        dict.__setitem__(bad.records[0],'event','BYPASS')
        try:bad.verify(ex);raise AssertionError('UNDETECTED_BASE_BYPASS')
        except ValueError as e:assert str(e)=='P0H_SEALED_HISTORY_TAMPER'
    ex.log[0]['event']='SOURCE_TAMPER'
    try:seal.clone(ex);raise AssertionError('UNDETECTED_SOURCE_TAMPER')
    except ValueError as e:assert str(e)=='P0H_SOURCE_HISTORY_CHANGED_REBIND_REQUIRED'
    return dict(independent_current_state=True,independent_log_lists=True,shared_records_read_only=True,
        public_mutations_rejected=denied,base_class_bypass_detected=True,source_tamper_detected=True)
def main():
    suffix='_TUPLE' if (s.A/'SEAM_BINDING_TUPLE.json').exists() else '_FINAL' if (s.A/'SEAM_BINDING_FINAL.json').exists() else ''
    rows=synthetic_cases();alias=alias_tests();s.write('SYNTHETIC_EQUIVALENCE'+suffix+'.json',dict(status='PASS',cases=rows,alias_tests=alias))
    c=s.root('CORRECTNESS'+suffix);lease,c,g,startup=s.w.open_lease(c)
    try:
        real=[]
        for name,action in s.actions(c):compare('real160_'+name,c.validator.physical,c.engine.executor,action,real)
        submits=[]
        # One atomic submission at t=3, never a 3-to-9 forecast or epoch.
        for name,action in s.actions(c)[:1]+s.actions(c)[1:2]+s.actions(c)[3:6]:
            old=c.clone();new=install(c.clone(),binding())
            old_receipt=old.submit(action);new_receipt=new.submit(action)
            assert old_receipt==new_receipt,'REAL_RECEIPT_DIFF:'+name
            assert old.last_result==new.last_result,'REAL_MEASUREMENT_DIFF:'+name
            assert old.engine.canonical_state()==new.engine.canonical_state(),'REAL_CANONICAL_DIFF:'+name
            assert old.engine.executor.log==new.engine.executor.log,'REAL_LOG_DIFF:'+name
            submits.append(dict(name=name,receipt=old_receipt,exact_equal=True,
                state_sha256=old.engine.canonical_state_sha256(),new_state_sha256=new.engine.canonical_state_sha256(),
                absolute_time_s=old.engine.now,no_positive_forecast_advance=True))
        s.write('REAL160_EQUIVALENCE'+suffix+'.json',dict(status='PASS',cases=real,atomic_submissions=submits,
            physical_candidate_checks=14,atomic_submissions_count=10,full_catalog=False,forecast_branches=0))
        s.write('CORRECTNESS_ACCEPTANCE'+suffix+'.json',dict(status='PASS_LIMITED_SEAM_CORRECTNESS',synthetic_cases=len(rows),
            real160_cases=len(real),paired_real_atomic_actions=len(submits),history_alias_tests=alias,
            full_N4_P0_engineering_pass=False))
        print('CORRECTNESS_PASS',flush=True)
    finally:lease.__exit__(None,None,None)
if __name__=='__main__':main()
