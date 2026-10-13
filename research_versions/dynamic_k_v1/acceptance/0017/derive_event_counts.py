"""Structural counts from sealed records, not new runtime instrumentation."""
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    d=read(V/'acceptance/0015/ROOT_BASELINE/ROOT_FULL_STATE.json');objects=d['objects']
    ref=lambda r:objects[r[1]]
    engine=next(x for x in objects if x['type'].endswith('ExactObservedD2Engine'))
    ledger=next(x for x in objects if x['type'].endswith('DeliveredAgeLedger'))
    observations=ref(dict(engine['fields'])['age_observations'])['items']
    initial=Counter(next(v[1] for k,v in ref(z)['items'] if k==['str','kind']) for z in observations)
    initial_closures=len(ref(dict(ledger['fields'])['closure_audit'])['items']);assert initial_closures==0
    rows=[]
    for mode in ('PERSIST','ZERO'):
        for p in sorted((V/'acceptance/0016/small'/mode).glob('*.json')):
            result=read(p)['result'];age=result['n2_result']['n1b_result']['age_accounting']
            closures=len(age['closure_audit'])-initial_closures
            delta=result['service_observation_count'];numerator=delta-closures-3
            assert numerator>=0 and numerator%2==0
            steps=numerator//2
            rows.append(dict(mode=mode,action=result['action'],age_record_delta=delta,
                closure_record_delta=closures,derived_positive_time_steps=steps,
                derived_microstep_and_SCHEDULE_calls=steps+3,
                derived_INTERVAL_records=steps,atomic_advance_calls=3,
                derived_age_consume_calls=3,derived_age_metrics_calls=6,
                actual_propagation_heap_pops=None,
                kind='EXACT_STRUCTURAL_DERIVATION_UNDER_BOUND_SUCCESSFUL_CALL_PATH'))
    bbm=read(V/'acceptance/0016/small/PERSIST/04_REPLACE_BBM.json')['result']['n2_result']['n1b_result']['age_accounting']
    samples=[str(x) for x in bbm['exact_rational'].values()]
    samples.extend(x[k] for x in bbm['roundoff_audit'] for k in ('difference_bits','cohort_bits','legacy_bits') if k in x)
    values=[Fraction(x) for x in samples]
    out=dict(schema='dynamic_k_0017_structural_event_counts_v1',initial_observation_count=len(observations),
        initial_observation_kinds=dict(initial),initial_closure_audit_count=initial_closures,rows=rows,
        equation='record_delta = 2*positive_time_steps + 3 endpoint_settles + closure_delta',
        assumptions=['All branches accepted/completed without exception; no legacy scripted actions',
            'Frozen score_action calls Atomic.advance_to at submit time 3, then cuts 6 and 9',
            'Every ExactEventClock._step executes one _microstep and one _integrate',
            'Every advance_to ends with exactly one settle_current_time/_microstep',
            'ObservedD2 emits one SCHEDULE per _schedule_service_segments, one INTERVAL per _integrate',
            'FIFO consumes every observer record once, appends one closure_audit per CLOSURE',
            '0016 plain score wrapper and read-only sampler do not advance the engine'],
        not_counted=['Propagation rate agenda individual pops','Cohort allocation/split/consume lifetime counts','Peak active streams'],
        stored_fraction_witnesses=dict(samples=len(values),max_numerator_bits=max(abs(x.numerator).bit_length() for x in values),
            max_denominator_bits=max(x.denominator.bit_length() for x in values),
            scope='Stored BBM final metrics and roundoff entries only, not maximum transient arithmetic operands'),
        simulation_runs=0)
    with (A/'STRUCTURAL_EVENT_COUNTS.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2,sort_keys=True)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
