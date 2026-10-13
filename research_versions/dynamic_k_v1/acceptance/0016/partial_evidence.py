"""Read already completed branches; never run or approximate predictions."""
import epoch_workflow as w
def main():
    rows=[];checks=[]
    for p in sorted((w.A/'small/PERSIST').glob('*.json')):
        d=w.vc.read_json(p);r=d['result']
        assert d['error'] is None and r['accepted'] and r['prediction_completed']
        rows.append(dict(evidence=w.bind(p),action=r['action'],J_h_bit_s=r['J_h_bit_s'],
            N_end_bits=r['N_end_bits'],DeltaE_h_J=r['DeltaE_h_J'],cost_bit_s=r['cost_bit_s'],
            actual_wall_s=d['actual_wall_s'],timings=r['timings'],state_checks=d['state_checks'],
            cohort_count=r['cohort_count'],service_observation_count=r['service_observation_count'],
            terminal_event_count=r['terminal_event_count'],memory=d['memory'],receipt=r['receipt']))
        kind=r['action']['kind']
        if kind in ('HOLD','ADD'):
            old=w.vc.read_json(w.V/'acceptance/0015'/kind/'branch_result.json')
            fields=('J_h_bit_s','N_end_bits','DeltaE_h_J')
            exact=all(r[k]==old[k] for k in fields)
            expected=old['J_h_bit_s']+6.*old['N_end_bits']+1000.*old['DeltaE_h_J']
            assert exact and r['cost_bit_s']==expected
            checks.append(dict(action=kind,exact_fields_equal=exact,expected_cost_bit_s=expected,
                actual_cost_bit_s=r['cost_bit_s'],evidence=w.bind(p)))
    w.write(w.A/'COMPLETED_BRANCHES_PARTIAL.json',dict(status='PARTIAL_NOT_DOMAIN_PASS',
        mode='PERSIST',completed_count=len(rows),rows=rows,selected_action=None,
        partial_order_by_cost=[r['action'] for r in sorted(rows,key=lambda r:r['cost_bit_s'])],
        partial_order_is_not_an_epoch_selection=True))
    w.write(w.A/'SCORING_RULE_0015_CHECK_PARTIAL.json',dict(status='PASS_HOLD_ADD_RULE_CHECK_ONLY',
        lambda_N_s=6.,lambda_E_bit_s_per_J=1000.,checks=checks,formal_science_frozen=False))
if __name__=='__main__':main()
