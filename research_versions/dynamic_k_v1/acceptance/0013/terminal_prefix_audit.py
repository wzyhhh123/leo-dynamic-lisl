"""Read-only comparisons of historical event prefixes and current JSON."""
import root_audit as w
def fields(x):return dict(x['fields']) if isinstance(x,dict) and 'fields' in x else dict(x)
def main():
    original=w.read(w.V/'acceptance/0011/conservation_failure_original_attempt02.json')
    new=w.vc.read_json(w.A/'actual_root_summary.json')
    root=w.vc.read_json(w.A/'actual_root_hash_preimage.json');r=fields(root)
    engine=fields(original['records'][1]['engine_state']);ex=fields(engine['executor']);cur=fields(new['live_engine_state'])
    oldlog=ex['log'];nowlog=r['terminal_history'];before=[x for x in oldlog if fields(x)['time']<3.]
    at3=[x for x in oldlog if fields(x)['time']==3.]
    reports={}
    for name in ('graph_event_sequence','route_changes','terminal_event_sequence'):
        rows=engine[name];current=cur[name]
        if rows and isinstance(rows[0],list):timekey=next((k for k,_ in rows[0] if k in ('time_s','time','t_s')),None)
        else:timekey=None
        if timekey:
            a=[x for x in rows if fields(x)[timekey]<3.]
            b=[x for x in current if fields(x)[timekey]<3.]
            reports[name]=dict(timestamp_field=timekey,comparison='STRICTLY_BEFORE_ADD_T3',
                original_count=len(a),current_count=len(b),exact_equal=a==b)
        else:reports[name]=dict(status='UNVERIFIABLE_TIMESTAMP_SCHEMA')
    energy=fields(original['records'][1]['energy_state']);ne=fields(new['energy_state'])
    samples_a=[x for x in energy['samples'] if fields(x)['t_s']<3.]
    samples_b=[x for x in ne['samples'] if fields(x)['t_s']<3.]
    ep=dict(original_samples_before_t3=samples_a,current_samples_before_t3=samples_b,
        samples_before_t3_exact_equal=samples_a==samples_b,
        original_samples_at_t3=[x for x in energy['samples'] if fields(x)['t_s']==3.],
        current_samples_at_t3=[x for x in ne['samples'] if fields(x)['t_s']==3.],
        warning='Original t3 sample includes post-ADD setup. Does not reconstruct old dwell/cursor/agenda.')
    w.write('terminal_event_and_energy_prefix_evidence.json',dict(
        terminal_history_before_t3_exactly_equals_new_root_history=before==nowlog,
        original_pre_t3_log_count=len(before),new_root_history_count=len(nowlog),
        original_at_t3_events=[dict(time=fields(x)['time'],event=fields(x)['event'],details=fields(x)['details']) for x in at3],
        event_prefix_comparisons=reports,energy_prefix_comparison=ep,
        old_full_t3_terminal_snapshot='UNVERIFIABLE',old_full_t3_agenda='UNVERIFIABLE',
        old_full_t3_energy_dwell='UNVERIFIABLE',old_full_t3_reservations='UNVERIFIABLE',
        simulated_roots_constructed=0,actions_submitted=0))
    print(w.canonical(dict(history_exact_equal=before==nowlog,old_count=len(before),new_count=len(nowlog),
        energy_pre3_equal=samples_a==samples_b,event_prefixes=reports)),flush=True)
if __name__=='__main__':main()
