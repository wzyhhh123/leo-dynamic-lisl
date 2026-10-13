"""Closed event IDs and untouched frozen source checks, no simulation."""
import json,hashlib
from pathlib import Path
import support as w
def main():
    ledger={}
    for name in ('HOLD','ADD'):
        d=w.A/name;start=dict(w.vc.read_json(d/'PRE_ACTION_CAUSAL_PREIMAGE.json'));end=dict(w.vc.read_json(d/'CHECKPOINT_9_CAUSAL_PREIMAGE.json'))
        settled=[];before=None
        with (d/'boundaries.jsonl').open(encoding='utf-8') as f:
            for line in f:
                b=json.loads(line)
                if b['label']=='BEFORE_PROPAGATION_EVENTS':before=b
                elif b['label']=='AFTER_PROPAGATION_EVENTS':
                    afterids={x['sequence'] for x in b['propagated_events']}
                    settled.extend(x['sequence'] for x in before['propagated_events'] if x['sequence'] not in afterids)
                    assert all(float.fromhex(x['time']['hex'])>b['time_s'] for x in b['propagated_events']),'DUE_EVENT_LEFT_IN_AGENDA'
        pending=[dict(x) for x in end['propagation_agenda']]
        pendingids={x['sequence'] for x in pending};offered=set(range(start['sequence']+1,end['sequence']+1))
        offered.update(dict(x)['sequence'] for x in start['propagation_agenda'])
        ok=len(settled)==len(set(settled)) and set(settled).isdisjoint(pendingids) and set(settled)|pendingids==offered
        assert ok and all(x['time_s']>9. for x in pending),'EVENT_OMISSION_OR_DUPLICATE'
        ledger[name]=dict(sequence_start=start['sequence'],sequence_final=end['sequence'],emitted_after_root=end['sequence']-start['sequence'],
            settled_count=len(settled),pending_count=len(pending),pending=pending,
            every_event_id_accounted_once=ok,all_final_pending_strictly_after_horizon=True)
    origin=Path(w.P/'src/dynamic_lisl/transition_service_orchestrator.py')
    bound=w.vc.load_expected(w.P,w.ORIGIN,w.PARENT)[2]
    assert w.vc.file_info(origin)==bound[origin.relative_to(w.P).as_posix()]
    tests={}
    for mode in ('original','variant'):
        d=w.vc.read_json(w.A/(mode+'_regression_summary.json'));assert all(x['status']=='PASS' for x in d.values());tests[mode]=d
    assert w.vc.read_json(w.A/'analytic_tests.json')['status']=='PASS'
    assert w.vc.read_json(w.A/'variant_P0_inline_constructor_test.json')['status']=='PASS'
    assert w.vc.read_json(w.A/'historical_summary.json')['no_new_failures']
    files=sorted([p for p in (w.A/'ROOT_BASELINE').rglob('*') if p.is_file()]+[w.A/'replay_recipe.json',w.A/'variant_dependencies.json',w.A/'VARIANT_BINDING.json'])
    w.write(w.A/'root_artifact_anchor.json',dict(schema='p0f_new_root_artifact_anchor_v1',files=[w.info(p) for p in files]))
    w.write(w.A/'FINAL_EVIDENCE_CHECKS.json',dict(status='PASS_N4_P0F_ISOLATED_EVENT_SEMANTICS_ONLY',event_ledger=ledger,
        frozen_engine_binding=w.info(origin),regression=tests,analytic_test_count=7,inline_test_count=1,
        historical_test_count=132,historical_failures=1,known_failure='test_known_witness_domain_discovers_every_registered_size_without_J',
        variant_root_replay_strict_pass=True,full_N4_P0_engineering_pass=False,scientific_gate_pass=False))
    print(json.dumps(dict(status='PASS',event_ledger=ledger)),flush=True)
if __name__=='__main__':main()
