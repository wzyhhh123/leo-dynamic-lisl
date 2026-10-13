"""Exact rational audit of saved IEEE updates only; no simulation objects."""
import json,math,hashlib
from fractions import Fraction as F
from collections import defaultdict
from pathlib import Path
A=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(name,d):
    with (A/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,sort_keys=True,indent=2);f.write('\n')
def exact(x):return dict(rational=str(x),approx=float(x))
def rows(p):
    with p.open(encoding='utf-8') as f:
        for line in f:yield json.loads(line)
def normkey(row):return json.dumps([row['kind'],row['key']],separators=(',',':'))
def scan(directory):
    summary=read(directory/'summary.json') if (directory/'summary.json').exists() else read(directory/'audit_summary.json')
    initial=sum((F(v['rational']) for v in summary['initial_exact_residual_by_commodity'].values()),F())
    total_error=F();signed_clip=F();nonclip=F();transfer=F();groups={};first_nonzero=None;first_error_threshold=None
    per_interval=defaultdict(lambda:dict(error=F(),clip=F(),nonclip=F(),count=0,first_op=None,last_op=None))
    for r in rows(directory/'operations.jsonl'):
        e=F(r['signed_global_mass_error']['rational']);sign=1 if r['kind']=='A' else -1
        clamp=F(float.fromhex(r['clip_mass_gain']['hex']));c=sign*clamp
        total_error+=e;signed_clip+=c;nonclip+=e-c
        transfer+=sign*F(float.fromhex(r['actual_increment']['hex']))
        if first_nonzero is None and e:first_nonzero=r
        if first_error_threshold is None and abs(initial+total_error)>F(1e-6):first_error_threshold=dict(operation=r,
            cumulative_error_residual=exact(initial+total_error),warning='Error-only audit; transfers mid-integration are not complete conservation states')
        k=normkey(r)
        if k not in groups:groups[k]=dict(kind=r['kind'],key=r['key'],commodity=r['commodity'],count=0,error=F(),signed_clip=F(),nonclip=F(),absolute_error=F())
        g=groups[k];g['count']+=1;g['error']+=e;g['signed_clip']+=c;g['nonclip']+=e-c;g['absolute_error']+=abs(e)
        iv=r['accounting_interval']
        if iv:
            key=(iv['start']['hex'],iv['end']['hex']);x=per_interval[key]
            x['error']+=e;x['clip']+=c;x['nonclip']+=e-c;x['count']+=1
            if x['first_op'] is None:x['first_op']=r['index']
            x['last_op']=r['index']
    b=[r for r in rows(directory/'boundaries.jsonl')]
    completed=[r for r in b if r['label'] in ('AFTER_INTEGRATE','AFTER_PROPAGATION_EVENTS','PRE_ACTION_t3','POST_ACTION_t3','UNCHANGED_EXCEPTION_STATE','RECIPE_PRE_ACTION_t3') or r['label'].startswith('PREDICTION_CHECKPOINT')]
    first_exact=next((r for r in completed if abs(F(r['totals']['exact_IEEE_operand_residual']['rational']))>F(1e-6)),None)
    first_formula=next((r for r in completed if abs(float.fromhex(r['totals']['A_minus_D_plus_QI']['hex']))>1e-6),None)
    first_any=next((r for r in completed if F(r['totals']['exact_IEEE_operand_residual']['rational'])),None)
    interval_details=[]
    for r in rows(directory/'intervals.jsonl'):
        k=(r['start']['hex'],r['end']['hex']);x=per_interval.get(k)
        if x:
            assert x['error']==F(r['actual_mass_error_change']['rational']),'INTERVAL_ERROR_DECOMPOSITION_MISMATCH'
            interval_details.append(dict(start_s=float.fromhex(k[0]),end_s=float.fromhex(k[1]),
                original=r,update_errors={key:exact(x[key]) for key in ('error','clip','nonclip')},
                operation_count=x['count'],first_operation=x['first_op'],last_operation=x['last_op']))
    final=F(summary['final_totals']['exact_IEEE_operand_residual']['rational'])
    assert initial+transfer+total_error==final,'FINAL_DECOMPOSITION_MISMATCH'
    assert total_error==signed_clip+nonclip
    grouped=[dict(**{k:v for k,v in g.items() if k not in ('error','signed_clip','nonclip','absolute_error')},
        **{k:exact(g[k]) for k in ('error','signed_clip','nonclip','absolute_error')}) for g in groups.values()]
    relevant=next((r for r in interval_details if first_formula and r['end_s']==first_formula['time_s']),None)
    operations=[]
    if relevant:
        operations=[r for r in rows(directory/'operations.jsonl') if relevant['first_operation']<=r['index']<=relevant['last_operation'] and
            (float.fromhex(r['clip_mass_gain']['hex'])>0 or F(r['signed_global_mass_error']['rational']))]
    compact_intervals=[{k:v for k,v in r.items() if k!='original'} for r in interval_details]
    out=dict(initial_exact_residual=exact(initial),final_exact_residual=exact(final),net_expected_transfers=exact(transfer),
        exact_signed_update_error=exact(total_error),exact_signed_clip_contribution=exact(signed_clip),
        exact_nonclip_arithmetic_contribution=exact(nonclip),decomposition_exactly_closed=True,
        first_nonzero_update_error=first_nonzero,first_completed_nonzero_residual=first_any,
        first_error_only_threshold_update=first_error_threshold,first_completed_exact_threshold=first_exact,
        first_completed_actual_N1a_formula_threshold=first_formula,
        first_actual_threshold_interval={k:v for k,v in relevant.items() if k!='original'} if relevant else None,
        first_actual_threshold_interval_raw_record=relevant['original'] if relevant else None,
        threshold_interval_nonzero_or_clipped_updates=operations,
        per_state_commodity_edge=grouped,intervals=compact_intervals,
        fixed_tolerance_bits=1e-6,production_state_not_replaced=True,
        reference_uses_exact_binary_float_operands=True,summary=summary)
    return out
def main():
    reports={}
    for name,d in [('ROOT_PREFIX',A/'ROOT_BASELINE/prefix_audit'),('HOLD',A/'HOLD'),('ADD',A/'ADD')]:
        dest=A/('EXACT_'+name+'_DIAGNOSIS.json')
        if dest.exists():reports[name]=read(dest)
        else:reports[name]=scan(d);write(dest.name,reports[name])
    held=read(A/'HOLD/branch_result.json');added=read(A/'ADD/branch_result.json')
    bs=read(A/'ROOT_BASELINE/root_binding.json')
    pairs={}
    for name in ('HOLD','ADD'):
        p=read(A/name/'PRE_ACTION_SUMMARY.json');post=read(A/name/'POST_ACTION_SUMMARY.json')
        pairs[name]=dict(PRE_ACTION=p,POST_ACTION=post,result=read(A/name/'branch_result.json'),
            pre_complete_sha_equals_bound_sanitized=p['complete_typed_state_sha256']==bs['sanitized']['complete_typed_state_sha256'],
            pre_causal_sha_equals_bound_sanitized=p['causal_state_sha256']==bs['sanitized']['causal_state_sha256'])
        assert pairs[name]['pre_causal_sha_equals_bound_sanitized']
    clone=read(A/'CLONE_SET_LAYOUT_AUDIT.json')
    assert clone['paired_HOLD_ADD_PRE_ACTION_every_field_equal'] and clone['supplementary_set_semantic_graph_every_field_equal']
    write('HOLD_ADD_COMPARISON.json',dict(scenario_id=bs['scenario_id'],paired_initial_state_exact=True,
        original_0011_root_replay=False,branches=pairs,clone_layout_audit=clone,
        comparable_horizon_metrics=added['status']=='COMPLETED_SINGLE_BRANCH',
        ADD_final_mean_delay_s=None if added['error'] else added['accepted_n2_result']['n1b_result']['mean_delivered_fluid_delay_s'],
        ADD_final_mean_delay_null_reason='N1a rejected before N1b consumes observations to t6; no accepted full-horizon result' if added['error'] else None))
    add=reports['ADD'];root=reports['ROOT_PREFIX'];h=reports['HOLD']
    write('DIAGNOSIS_SUMMARY.json',dict(scenario_id=bs['scenario_id'],status=added['status'],
        root_reconstruction_pass=True,original_0011_replay=False,
        classification='MEASURED_NUMERICAL_CLAMP_DOMINATED_CONSERVATION_BOUNDARY' if added['error'] and add['net_expected_transfers']['approx']==0. and abs(add['exact_signed_clip_contribution']['approx'])>1e-6 else 'UNRESOLVED',
        root_prefix_first_update_error=root['first_nonzero_update_error'],
        root_prefix_final_exact_residual=root['final_exact_residual'],HOLD_final_exact_residual=h['final_exact_residual'],
        ADD_initial_exact_residual=add['initial_exact_residual'],ADD_final_exact_residual=add['final_exact_residual'],
        ADD_clip_contribution=add['exact_signed_clip_contribution'],ADD_nonclip_contribution=add['exact_nonclip_arithmetic_contribution'],
        ADD_expected_transfer_net=add['net_expected_transfers'],
        first_completed_N1a_formula_threshold_time_s=(add['first_completed_actual_N1a_formula_threshold'] or {}).get('time_s'),
        first_threshold_interval=add['first_actual_threshold_interval'],
        kernel_or_tolerance_modified=False,formula_changed=False,universal_error_bound_claimed=False,
        original_0011_root_cause_resolved=False,N4_P0_engineering_pass=False))
    print(json.dumps({k:read(A/'DIAGNOSIS_SUMMARY.json')[k] for k in ('classification','ADD_final_exact_residual','ADD_clip_contribution','ADD_nonclip_contribution','ADD_expected_transfer_net','first_completed_N1a_formula_threshold_time_s')}),flush=True)
if __name__=='__main__':main()
