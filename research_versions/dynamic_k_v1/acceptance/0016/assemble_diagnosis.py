"""Offline evidence assembly; no new service or topology execution."""
import json
from collections import Counter
import epoch_workflow as w
def main():
    rows=[]
    for mode in ('PERSIST','ZERO'):
        for p in sorted((w.A/'small'/mode).glob('*.json')):
            d=w.vc.read_json(p);r=d['result'];n2=r['n2_result'];b=n2['n1b_result']
            rows.append(dict(mode=mode,evidence=w.bind(p),action=r['action'],action_receipt=r['receipt'],
                J_h_bit_s=r['J_h_bit_s'],N_end_bits=r['N_end_bits'],E_h_J=r['E_h_J'],DeltaE_h_J=r['DeltaE_h_J'],
                cost_bit_s=r['cost_bit_s'],actual_wall_s=d['actual_wall_s'],timings=r['timings'],
                branch_final_state_sha256=r['branch_final_state_sha256'],state_checks=d['state_checks'],
                K_admit=n2['K_admit'],K_draining=n2['K_draining'],setup_terminal_count=n2['setup_terminal_count'],
                delivered_bit_age_integral_bit_s=b['delivered_bit_age_integral_bit_s'],
                delivered_bits=b['delivered_bits'],mean_delivered_fluid_delay_s=b['mean_delivered_fluid_delay_s'],
                mean_delay_absolute_error_bound_s=b['mean_delay_absolute_error_bound_s'],
                cohort_count=r['cohort_count'],service_observation_count=r['service_observation_count'],
                terminal_event_count=r['terminal_event_count'],memory=d['memory']))
    assert len(rows)==10
    catalog=w.vc.read_json(w.A/('CATALOG_HARD_STOP.json' if (w.A/'CATALOG_HARD_STOP.json').exists() else 'CATALOG_DIAGNOSIS.json'))
    progress=sorted(w.A.glob('CATALOG_PROGRESS_*.json'),key=lambda p:int(p.stem.split('_')[-1]))
    last=w.vc.read_json(progress[-1]) if progress else None
    w.write(w.A/'FINAL_DIAGNOSTIC_EVIDENCE.json',dict(small_domain_rows=rows,catalog=catalog,
        last_completed_stage_snapshot=last,stage_snapshot_is_not_complete_enumeration=True,
        small_domain_score_order={m:w.vc.read_json(w.A/('SMALL_'+m+'_SUMMARY.json'))['decision'] for m in ('ZERO','PERSIST')},
        selected_full_epoch_action=None if not (w.A/'SINGLE_EPOCH_ACCEPTANCE.json').exists() else 'SEE_EPOCH_EVIDENCE',
        profiler_pair=w.bind(w.A/'OBSERVER_PROFILE_TIMING_PAIR.json'),
        instrumentation_scope='Actual profiler overhead only on paired HOLD; full catalog uses lightweight wrappers; no full uninstrumented catalog rerun authorized or executed',
        catalog_peak_memory_source=w.bind(w.A/'CATALOG_MEMORY_SNAPSHOT_01.json'),
        frozen_source_changes=0,main_pilot_runs=0,science_gate_pass=False))
    print(json.dumps(dict(catalog=catalog,last_stage=last),indent=2),flush=True)
if __name__=='__main__':main()
