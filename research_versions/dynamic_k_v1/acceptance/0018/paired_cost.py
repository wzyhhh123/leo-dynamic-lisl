"""Correctness-gated bounded paired checks, never full catalog or forecasts."""
import time,statistics
import support18 as s
from stage_timer import Timer
from correctness import binding
if (s.A/'SEAM_BINDING_TUPLE.json').exists():
    from runtime.n4_p0h_gate_c_final import install,StructuralCatalog,SealedHistory,SourceBinding,history_bytes
else:
    from runtime.n4_p0h_gate_c import install,StructuralCatalog,SealedHistory,SourceBinding,history_bytes
from runtime.n4_p0r_handle_reader import HandleReaderLease
def main():
    suffix='_TUPLE' if (s.A/'SEAM_BINDING_TUPLE.json').exists() else '_FINAL' if (s.A/'SEAM_BINDING_FINAL.json').exists() else ''
    assert s.vc.read_json(s.A/('CORRECTNESS_ACCEPTANCE'+suffix+'.json'))['status']=='PASS_LIMITED_SEAM_CORRECTNESS'
    c=s.root('COST'+suffix);lease,c,g,startup=s.w.open_lease(c)
    source_lease=HandleReaderLease([binding()],s.vc);source_lease.__enter__()
    fresh_binding=source_lease.guard(binding())
    try:
        old=c.clone();start=time.perf_counter();new=install(c.clone(),fresh_binding);install_s=time.perf_counter()-start
        rows=[];instrumented=[];start_all=time.perf_counter()
        extra={StructuralCatalog.connect_command.__code__:'GateC_connect_other',
            SealedHistory.clone.__code__:'GateC_sealed_structural_clone_other',
            SealedHistory.verify.__code__:'history_integrity_validation',
            history_bytes.__code__:'history_JSON_encoding',SourceBinding.verify.__code__:'seam_source_validation'}
        extra[fresh_binding.verify.function.__code__]='seam_source_validation'
        for name,action in s.actions(c):
            timings={'original':[],'optimized':[]};expected=None
            for repetition in range(3):
                order=[('original',old),('optimized',new)]
                if repetition%2:order.reverse()
                for group,controller in order:
                    ex=controller.engine.executor;before=s.digest(dict(snapshot=ex.snapshot(),log=ex.log))
                    start=time.perf_counter();result=controller.validator.validate(ex,action);elapsed=time.perf_counter()-start
                    value=s.verdict(result)
                    if expected is None:expected=value
                    assert value==expected,'PAIRED_VERDICT_DIFF:'+name
                    assert before==s.digest(dict(snapshot=ex.snapshot(),log=ex.log))
                    timings[group].append(elapsed)
            rows.append(dict(name=name,action=s.asdict(action),original_wall_s=timings['original'],optimized_wall_s=timings['optimized'],
                original_median_s=statistics.median(timings['original']),optimized_median_s=statistics.median(timings['optimized']),
                median_ratio_original_over_optimized=statistics.median(timings['original'])/statistics.median(timings['optimized']),
                identical_verdict_sha256=s.digest(expected),exact_equal=True))
            for group,controller in [('original',old),('optimized',new)]:
                ex=controller.engine.executor;timer=Timer(ex,extra)
                result,parts=timer.run(lambda:controller.validator.validate(ex,action))
                assert s.verdict(result)==expected,'PROFILE_PAIR_DIFF:'+name
                instrumented.append(dict(name=name,group=group,parts=parts,exact_equal=True,
                    comparator_median_s=statistics.median(timings[group]),
                    instrumentation_excess_over_median_s=parts['actual_wall_s']-statistics.median(timings[group])))
            if time.perf_counter()-start_all>120.:raise RuntimeError('BOUNDED_MEASUREMENT_120S_STOP')
        plain_old=sum(sum(x['original_wall_s']) for x in rows);plain_new=sum(sum(x['optimized_wall_s']) for x in rows)
        s.write('PAIRED_COST'+suffix+'.json',dict(status='PASS_BOUNDED_PAIRED_MEASUREMENT',rows=rows,stage_profiles=instrumented,
            paired_repetitions_per_action=3,specified_actions=7,plain_validate_calls=42,profiled_validate_calls=14,
            full_catalog_enumerated=False,forecast_branches=0,wall_s=time.perf_counter()-start_all,
            engineering_measurement_stop_s=120.,install_and_clone_s=install_s,reader_startup_s=startup,
            plain_original_total_s=plain_old,plain_optimized_total_s=plain_new,
            plain_total_speed_ratio=plain_old/plain_new,
            plain_optimized_plus_cold_install_total_s=plain_new+install_s,
            complete_catalog_under_300s_claimed=False,scientific_gate_pass=False,
            profiler_warning='All classified stage times include thread observer overhead; production effect uses unprofiled pairs only'))
        s.write('SOURCE_READER_ADAPTER_AUDIT'+suffix+'.json',dict(audit=source_lease.audit,
            fresh_raw_reads=source_lease.reads,bytes_hashed=source_lease.bytes_hashed,positive_hash_results_cached=False))
        print('PAIRED_COST_PASS original='+str(plain_old)+' optimized='+str(plain_new)+' ratio='+str(plain_old/plain_new),flush=True)
    finally:source_lease.__exit__(None,None,None);lease.__exit__(None,None,None)
if __name__=='__main__':main()
