"""Offline exact nominal-vs-effective propagation pulse timing audit."""
import json
from fractions import Fraction as F
from collections import defaultdict
from pathlib import Path
A=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def exact(v):return dict(rational=str(v),approx=float(v))
def fp(v):return F(float.fromhex(v['hex']))
def rows(p):
    with p.open(encoding='utf-8') as f:
        for line in f:yield json.loads(line)
def main():
    reports={}
    for name,d in [('ROOT_PREFIX',A/'ROOT_BASELINE/prefix_audit'),('HOLD',A/'HOLD'),('ADD',A/'ADD')]:
        before=None;consumed=[];totals=defaultdict(F)
        for b in rows(d/'boundaries.jsonl'):
            if b['label']=='BEFORE_PROPAGATION_EVENTS':before=b
            elif b['label']=='AFTER_PROPAGATION_EVENTS':
                assert before is not None
                ids={e['sequence'] for e in b['propagated_events']}
                for e in before['propagated_events']:
                    if e['sequence'] in ids:continue
                    nominal=fp(e['time']);effective=fp(before['time']);shift=nominal-effective
                    rate=fp(e['delta_rate']);excess=rate*shift
                    row=dict(sequence=e['sequence'],edge=e['edge'],commodity=e['commodity'],
                        nominal=exact(nominal),effective=exact(effective),processed_early_by_s=exact(shift),
                        delta_rate=exact(rate),arrival_volume_bias_after_nominal_time_bit=exact(excess))
                    consumed.append(row)
                    totals[json.dumps([e['edge'],e['commodity']])]+=excess
                before=None
        reports[name]=dict(consumed_events=len(consumed),early_events=[e for e in consumed if e['processed_early_by_s']['approx']>0],
            late_events=[e for e in consumed if e['processed_early_by_s']['approx']<0],
            exact_arrival_pulse_bias_by_edge={k:exact(v) for k,v in totals.items()},
            definition='delta_rate*(nominal_event_time-effective_processing_time), exact IEEE rationals; reference pulse integral only, not a state replacement')
    add=reports['ADD'];key=json.dumps([['X0_9','X0_10'],'f_hot'])
    add['first_threshold_edge_bias']=add['exact_arrival_pulse_bias_by_edge'].get(key)
    result=dict(reference_only=True,unchanged_event_tolerance_s=1e-12,reports=reports,
        kernel_modified=False,additional_simulation_runs=0)
    with (A/'PROPAGATION_EVENT_TIMING_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(dict(early=len(add['early_events']),late=len(add['late_events']),
        first_threshold_edge_bias=add['first_threshold_edge_bias'],early_events=add['early_events'])),flush=True)
if __name__=='__main__':main()
