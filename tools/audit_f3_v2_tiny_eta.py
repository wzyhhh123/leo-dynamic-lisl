"""Predeclared tiny min-eta diagnostic; no controller-performance experiment."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from test_f3_v2_tiny_diagnostics import eta_fixture
from dynamic_lisl.f3_v2.tiny_diagnostics import audit_tiny_eta
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256


def main():
    out=ROOT/'outputs'/('f3_v2_tiny_eta_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    cases=(('EQUAL_LIFETIMES',30),('ONE_SHORT_LIFETIME',3.25))
    # Both fixtures and interpretation tests were fixed in source before audit.
    # No value of V/J is used to revise the fixture, score or search budget.
    write_new_json(out/'fixture_contract.json',{'status':'ENGINEERING_ONLY_NOT_SCIENTIFIC_FREEZE',
        'cases':[{'id':cid,'target_1_end_s':end} for cid,end in cases],
        'nodes':8,'commodities':[{'id':'f0','source':'A0','destination':'D0','rate_bit_s':60},
                               {'id':'f1','source':'A1','destination':'D1','rate_bit_s':60}],
        'capacity_bit_s_per_direction':40,'propagation_per_edge_s':.05,
        'traffic_interval_s':[0,4],'decision_time_s':1,'retarget_s':1,'acquisition_s':1,
        'transitions':'two real independent MBB terminal pairs','all_legal_batches':'HOLD+{m0}+{m1}+{m0,m1}',
        'scoring':'frozen V_v2 whole-graph evaluator; explicit draft min eta',
        'actual_delivery_performance_or_rollout_evaluated':False,
        'code_hashes':{p:file_sha256(ROOT/p) for p in ('tests/test_f3_v2_tiny_diagnostics.py',
            'src/dynamic_lisl/f3_v2/tiny_diagnostics.py','src/dynamic_lisl/f3_v2/snapshot_controllers.py',
            'src/dynamic_lisl/scientific_snapshot.py')}})
    summaries=[]
    for cid,end in cases:
        engine,validator,pool=eta_fixture(end)
        report=audit_tiny_eta(engine,pool)
        write_new_json(out/(cid+'.json'),{'pool':pool.public_document(),'state':engine.canonical_state(),**report})
        summaries.append({'case_id':cid,'selected_batch_size':report['selected_batch_size'],
            'rows':[{'batch_size':r['batch_size'],'member_ids':r['member_ids'],
                'deltaV_bit_s':r['deltaV'],'eta':r['eta'],'score_bit_s':r['score']} for r in report['candidates']]})
    long,short=summaries
    joint=next(r for r in short['rows'] if r['batch_size']==2)
    long_only=next(r for r in short['rows'] if r['member_ids']==['m0'])
    equal_eta={r['eta'] for r in long['rows']}
    report={'status':'TINY_REAL_SCORING_DIAGNOSTIC_COMPLETE','summaries':summaries,
        'equal_window_all_batches_same_eta':len(equal_eta)==1,
        'short_member_suppresses_joint_eta':joint['eta']<long_only['eta'],
        'larger_ideal_benefit_but_lower_batch_score_observed':(
            type(joint['deltaV_bit_s']) in (int,float) and type(long_only['deltaV_bit_s']) in (int,float) and
            joint['deltaV_bit_s']>long_only['deltaV_bit_s']>0 and joint['score_bit_s']<long_only['score_bit_s']),
        'pairwise_break_even_proxy_condition':'deltaV_batch/deltaV_single > eta_single/eta_batch; for positive benefits only',
        'scientific_interpretation':'min eta is a conservative heuristic and can prefer smaller batches; not exact service-loss accounting',
        'scoring_or_budget_changed':False,'main_scale_generalization_claim':False,
        'registered_P1_v2_executed':False,'P2_started':False,'RL_started':False}
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out),
        'larger_ideal_benefit_but_lower_batch_score_observed':report['larger_ideal_benefit_but_lower_batch_score_observed']},indent=2))


if __name__=='__main__':main()
