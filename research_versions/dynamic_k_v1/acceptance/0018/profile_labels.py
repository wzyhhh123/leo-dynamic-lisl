"""One paired ADD observation with disjoint Gate C/N2 clone labels."""
import support18 as s
from stage_timer import Timer
from correctness import binding
from runtime.n4_p0h_gate_c_final import install,StructuralCatalog,SealedHistory,SourceBinding,history_bytes
from runtime.n4_p0r_handle_reader import HandleReaderLease
def main():
    c=s.root('STAGE_LABELS');lease,c,g,startup=s.w.open_lease(c);source=HandleReaderLease([binding()],s.vc);source.__enter__()
    try:
        bound=source.guard(binding());old=c.clone();new=install(c.clone(),bound);action=s.actions(c)[1][1];rows=[];expected=None
        extra={StructuralCatalog.connect_command.__code__:'GateC_connect_other',SealedHistory.clone.__code__:'GateC_sealed_structural_clone_other',
            SealedHistory.verify.__code__:'history_integrity_validation',history_bytes.__code__:'history_JSON_encoding',
            bound.verify.function.__code__:'seam_source_validation'}
        for name,controller in [('original',old),('optimized',new)]:
            timer=Timer(controller.engine.executor,extra)
            r,timing=timer.run(lambda:controller.validator.validate(controller.engine.executor,action))
            value=s.verdict(r)
            if expected is None:expected=value
            assert value==expected
            rows.append(dict(group=name,stage=timing,exact_equal=True))
        s.write('DISJOINT_STAGE_PROFILE.json',dict(status='PASS',rows=rows,profiled_validate_calls=2,
            note='Earlier CLONE label grouped Gate C top structural clone into N2_outer; this separate observation uses disjoint labels. No new plain timings or full catalog inferred.'))
        print('DISJOINT_STAGE_PASS',flush=True)
    finally:source.__exit__(None,None,None);lease.__exit__(None,None,None)
if __name__=='__main__':main()
