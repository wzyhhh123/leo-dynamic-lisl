"""Bounded paired whole-interval timing, after correctness only."""
import time,json,tracemalloc
from types import SimpleNamespace
import common as c
def main():
    assert json.loads((c.A/'CORRECTNESS.json').read_text())['status']=='PASS_EXACT_FIELDS_AND_ORDER'
    c.source_verify()
    old=c.load('fifo19_diagnostic_reuse',c.V/'acceptance/0019/diagnostic_child.py')
    rows=[]
    for layout,sizes in [('disjoint',(32,64,128,256,512)),('dense',(16,32,64))]:
        for n in sizes:
            timings=[]
            for repeat in range(3):
                pair={};states={}
                for mode in ('reference','sweep'):
                    module=SimpleNamespace(DeliveredAgeLedger=c.DeliveredAgeLedger if mode=='reference' else c.SweepDeliveredAgeLedger,Stream=c.Stream)
                    tick=time.perf_counter();states[mode],data=old.interval_fixture(module,n,layout)
                    pair[mode]=dict(total_fixture_s=time.perf_counter()-tick,interval_including_index_cold_build_s=data['wall_s'])
                assert states['reference']==states['sweep'],'STOP_PERFORMANCE_FIELD_MISMATCH'
                timings.append(pair)
            measurements=[];cls=c.counted_sweep_class(measurements)
            state,_=old.interval_fixture(SimpleNamespace(DeliveredAgeLedger=cls,Stream=c.Stream),n,layout)
            assert state==states['reference']
            memory={}
            for mode,ledger in [('reference',c.DeliveredAgeLedger),('sweep',c.SweepDeliveredAgeLedger)]:
                tracemalloc.start();tick=time.perf_counter()
                current,_=old.interval_fixture(SimpleNamespace(DeliveredAgeLedger=ledger,Stream=c.Stream),n,layout)
                memory[mode]=dict(current_bytes=tracemalloc.get_traced_memory()[0],peak_bytes=tracemalloc.get_traced_memory()[1],
                                  instrumented_wall_s=time.perf_counter()-tick)
                tracemalloc.stop();assert current==states['reference']
            row=dict(layout=layout,n=n,paired_plain_samples=timings,sweep_light_measurements=measurements,
                memory_scope='TRACEMALLOC_SEPARATE_RUN_ENTIRE_SYNTHETIC_FIXTURE_NOT_PRODUCTION_WALL',memory=memory,
                all_fields_exact=True,index_build_and_maintenance_in_plain_timings=True)
            c.write('fixture_pairs/%s_%d.json'%(layout,n),row);rows.append(row)
            print(layout,n,timings[0],flush=True)
    c.write('FIXTURE_PERFORMANCE.json',dict(status='PASS_PAIRED_EQUIVALENCE_AND_MEASURED_COST',cases=rows,
        profiler_callbacks=0,plain_order='REFERENCE_THEN_SWEEP_FIXED_ORDER_3_REPEATS',
        statistical_claim=False,full_BBM_speedup_claim=False))
if __name__=='__main__':main()
