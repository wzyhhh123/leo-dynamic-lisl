"""Finite rollback, pending-state independence, tamper and terminal lifecycle."""
import copy,json,hashlib
import support18 as s
from correctness import binding,protect
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect,Disconnect
from runtime.n4_p0h_gate_c_final import SealedHistory,SourceBinding,install
from runtime.n1a import TerminalEnergyLedger
def rollback_alias():
    nodes=tuple('X%d_%d'%(p,n) for p in range(4) for n in range(40));ex=TerminalExecutor(nodes)
    a,b=('X0_1','D1'),('X1_1','D2')
    ex.submit([Connect(a,b,50.,0.,0.,0.)]);ex.submit([Connect(('X0_2','D1'),('X1_2','D2'),50.,2.,2.,1.)])
    history=SealedHistory(ex);left=history.clone(ex);right=history.clone(ex)
    rid=next(iter(left.reservations));assert left.reservations[rid] is not right.reservations[rid]
    before=protect(ex);right_before=protect(right)
    left.reservations[rid].visibility_end=49.;assert protect(ex)==before and protect(right)==right_before
    commands=(Disconnect(a,b),Connect(('unknown','D1'),('X2_2','D1'),20.,.5,.5,.5))
    results=[]
    for variant in (False,True):
        trial=history.clone(ex) if variant else copy.deepcopy(ex);start=protect(trial)
        try:trial.submit(commands);raise AssertionError('FAILED_TRANSACTION_ACCEPTED')
        except ValueError as e:message=str(e)
        assert protect(trial)==start and protect(ex)==before
        results.append(dict(optimized=variant,reason=message,rollback_exact=True,snapshot_log_sha256=start))
    assert results[0]['reason']==results[1]['reason']
    ledger=TerminalEnergyLedger(ex);ex.log[0]['event']='BAD_HISTORY'
    try:ledger.capture(ex);raise AssertionError('LEGACY_HISTORY_TAMPER_ACCEPTED')
    except ValueError as e:assert str(e)=='TERMINAL_HISTORY_TRUNCATED_OR_CHANGED'
    return dict(pending_reservation_independent=True,rollback=results,legacy_N1a_history_reject_preserved=True)
def source_negative():
    directory=s.A/'negative_inputs';directory.mkdir(exist_ok=False)
    target=directory/'source.txt';target.write_bytes(b'ORIGINAL_TEST_ONLY')
    manifest=directory/'manifest.json'
    s.w.write(manifest,dict(schema='dynamic_k_p0h_structural_seam_sources_v1',files=[s.bind(target)]))
    g=SourceBinding(s.P,manifest.relative_to(s.P).as_posix(),s.bind(manifest)['sha256']);g.verify()
    target.write_bytes(b'TAMPERED_TEST_ONLY')
    try:g.verify();raise AssertionError('RAW_INPUT_TAMPER_NOT_REJECTED')
    except ValueError as e:assert str(e).startswith('P0H_SOURCE_DRIFT:');reason=str(e)
    wrong=SourceBinding(g.project_root,g.manifest_path,'0'*64)
    try:wrong.verify();raise AssertionError('MANIFEST_TAMPER_NOT_REJECTED')
    except ValueError as e:assert str(e)=='P0H_MANIFEST_DRIFT'
    return dict(test_only_input_before='ORIGINAL_TEST_ONLY',test_only_input_after='TAMPERED_TEST_ONLY',
        dependency_tamper_reject=reason,manifest_anchor_reject='P0H_MANIFEST_DRIFT',frozen_sources_touched=False)
def main():
    local=rollback_alias();negative=source_negative();s.write('ROLLBACK_AND_TAMPER_FINAL.json',dict(status='PASS',local=local,source=negative))
    c=s.root('LIFECYCLE');lease,c,g,startup=s.w.open_lease(c)
    try:
        rows=[]
        for name,action in [(n,a) for n,a in s.actions(c) if n in ('ADD_hot','BBM_hot','MBB_hot')]:
            old=c.clone();new=install(c.clone(),binding());old.submit(action);new.submit(action)
            for abort in (False,True):
                oe=old.engine.executor.clone_for_transaction();ne=new.engine.executor.clone_for_transaction()
                ol=copy.deepcopy(old.evaluator.base.ledger);nl=copy.deepcopy(new.evaluator.base.ledger)
                if abort:
                    oe.expire_visibility(action.a,action.b);ne.expire_visibility(action.a,action.b)
                for t in (3.,3.5,4.,4.25):
                    oe.advance(t);ne.advance(t);ol.capture(oe);nl.capture(ne)
                    assert oe.snapshot()==ne.snapshot() and oe.log==ne.log and ol.metrics()==nl.metrics()
                rows.append(dict(action=name,setup_abort=abort,terminal_log_sha256=s.digest(oe.log),
                    terminal_snapshot_sha256=s.digest(oe.snapshot()),energy=ol.metrics(),exact_equal=True,
                    scope='Isolated Gate B executor and N1a ledger only, no network forecast propagation'))
        s.write('TERMINAL_LIFECYCLE_ENERGY_TUPLE.json',dict(status='PASS',cases=rows,network_forecast_branches=0))
        print('NEGATIVE_LIFECYCLE_PASS',flush=True)
    finally:lease.__exit__(None,None,None)
if __name__=='__main__':main()
