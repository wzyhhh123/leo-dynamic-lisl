"""Static preimplementation semantic check with exact rational analytical cases."""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

V = Path(__file__).resolve().parents[2]


def main():
    config = json.loads((V/'configs/n1b_fifo_semantics_v1.json').read_text(encoding='utf-8'))
    text = (V/'contracts/N1B_NODE_LOCAL_FIFO_SEMANTICS_CN.md').read_text(encoding='utf-8')
    checks = dict(local_fifo=config['fifo_order_key']=='LOCAL_QUEUE_ARRIVAL_TIME',
        proportional_ties=config['simultaneous_arrival_rule']=='PROPORTIONAL_BY_ARRIVAL_BITS',
        preserve_original_time=config['original_injection_time_preserved'] is True,
        no_midpoint=config['continuous_cohort_rule']=='PIECEWISE_ORIGINAL_TIME_MAP_NO_MIDPOINT_APPROXIMATION',
        old_scheduler=config['cross_commodity_scheduler']=='UNCHANGED_EQUAL_WEIGHT_MAX_MIN',
        scientific_null=all(v is None for v in config['scientific_parameters'].values()),
        no_formal_run=config['formal_experiments_authorized'] is False,
        no_production_edits=config['production_kernel_modification_authorized'] is False,
        no_N2=config['N2_authorized'] is False,
        no_delivery_null=config['no_delivery_mean_delay'] is None,
        closed_unknown_stop=config['unknown_age_or_unattributable_closure']=='STOP_WITH_EVIDENCE',
        continuous_moment_defined='integral r*(a*u+b) du' in text,
        conditional_identity='初始无历史业务' in text and 'J_T=M_D+W_remaining(T)' in text,
        clone_state='clone/checkpoint/restore' in text,
        precision_boundary='浮点转换误差' in text,
        original_timestamp_not_order='不是全网原始注入时间' in text)
    # Case1: two uniform6-bit cohorts, first departs3..4, delivered4..5.
    md = F(6)*4
    rem = F(6)*(5-F(5,2))
    j = F(3)+6+9+12+9
    checks['two_batch_exact'] = md == 24 and md/6 == 4 and rem == 15 and j == md+rem == 39
    # Case2: original mean arrival at u: 1/4*(u-4)+3/4*(u-2)=u-5/2.
    # 4bit served6..7: local u=4+(t-6)/2; delivered d=t+1.
    # Age(t)=t+1-(t/2-3/2)=t/2+5/2; integral6..7 rate4 =>23.
    md_mix = F(4)*(F(49-36,4)+F(5,2))
    checks['proportional_merge_exact'] = md_mix == 23 and md_mix/4 == F(23,4)
    checks['single_and_two_hop_exact'] = 10*1 == 10 and 10*2 == 20
    checks['wait_restore_exact'] = F(20)*(F(3,2)-F(1,8)) == F(55,2)
    assert all(checks.values()), checks
    # Proportional case derivation exposes incorrect hand arithmetic before code.
    assert 'M_D=23 bit·s、mean=5.75 s' in text, 'CONTRACT_ANALYTICAL_MERGE_RESULT_MISMATCH'
    bindings = {}
    for rel in ('contracts/N1B_NODE_LOCAL_FIFO_SEMANTICS_CN.md','configs/n1b_fifo_semantics_v1.json'):
        data = (V/rel).read_bytes()
        bindings[rel] = dict(byte_count=len(data), sha256=hashlib.sha256(data).hexdigest())
    report = dict(status='PASS', scope='STATIC_FIFO_SEMANTICS_ONLY', checks=checks,
                  bindings=bindings, N1b_engineering_pass=False,
                  analytical_cases=dict(two_batch_MD='24', two_batch_J='39',
                                        merge_MD='23', merge_mean='23/4', wait_MD='55/2'))
    with (Path(__file__).parent/'fifo_static_report.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
