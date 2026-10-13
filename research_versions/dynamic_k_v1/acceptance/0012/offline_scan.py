"""High precision of encoded IEEE states, never production substitutions."""
from fractions import Fraction as F
import math
import audit_workflow as w
def residual(s):return sum(map(F,s['A'].values()),F())-sum(map(F,s['D'].values()),F())-sum(map(F,s['Q'].values()),F())-sum(map(F,s['I'].values()),F())
def main():
    a=w.read_old('conservation_failure_original_attempt02.json');b=w.read_old('conservation_failure_handle_attempt02.json')
    assert a['records']==b['records'] and a['root_sha256']==b['root_sha256']
    rows=[];first=None;largest=None
    for i,r in w.intervals(a):
        if r['start']<3.:continue
        before,after=residual(r['before']),residual(r['after']);delta=after-before
        row=dict(observation_index=i,start_s=r['start'],end_s=r['end'],start_hex=float(r['start']).hex(),end_hex=float(r['end']).hex(),
            exact_before=str(before),exact_after=str(after),exact_change=str(delta),change_bits=float(delta),residual_bits=float(after))
        rows.append(row)
        if first is None and abs(after)>F(1e-6):first=row
        if largest is None or abs(delta)>abs(F(largest['exact_change'])):largest=row
    w.write('offline_saved_evidence_scan.json',dict(status='BOUND_0011_STATES_EXACTLY_EQUAL',root_sha256=a['root_sha256'],forecast_sha256=a['forecast_sha256'],
        interval_count=len(rows),first_interval_over_N1a_threshold_exact_IEEE_state=first,largest_interval_change=largest,
        rows=rows,reference='Fraction of original IEEE-754 operands; decimal printed strings are not treated as exact real inputs'))
    print('INTERVALS',len(rows),'FIRST',first,'LARGEST',largest,flush=True)
if __name__=='__main__':main()
