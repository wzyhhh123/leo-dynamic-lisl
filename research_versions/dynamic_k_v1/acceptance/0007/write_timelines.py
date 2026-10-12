"""Display measured K / draining / setup transitions, retaining microstep ties."""
import argparse,json
from pathlib import Path
A=Path(__file__).parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);args=parser.parse_args()
    dest=A/args.attempt;assert dest.parent==A
    examples=json.loads((dest/'engineering_examples.json').read_text(encoding='utf-8'))['examples']
    cases={k:v for k,v in examples.items() if isinstance(v,dict) and 'STATIC_HOLD' in v}
    cases['real160_natural_SGP4']=examples['real160_natural_SGP4_controlled_catalog_paired_multi_epoch']['paired_results']
    lines=['# N3 配对工程 K 状态时间线','',
        '仅 ENGINEERING_TEST_ONLY。表格压缩相邻且所有展示状态一致的重复行；相同时间戳的不同真实微步状态保留，不代表额外驻留区间。原始完整序列在 engineering_examples.json / paired_metrics.json。显示数值四舍五入，原始 binary64 值和 N1b 精度/误差界保留在 JSON。','']
    for scenario,pair in cases.items():
        lines+=['## '+scenario,'']
        for name,r in pair.items():
            lines+=[name+'（T='+str(r['fixture_identity']['T_s'])+' s）','',
                '|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|','|---:|---:|---:|---:|---:|']
            previous=None;last_t=None
            for row in r['metrics']['K_time_series']:
                state=tuple(row[k] for k in ('K_admit','K_draining','setup_terminal_count','setup_reserved_terminal_count'))
                if state!=previous:
                    lines.append('|'+format(row['t_s'],'.15g')+'|'+'|'.join(str(v) for v in state)+'|')
                    previous=state;last_t=row['t_s']
            if last_t!=r['fixture_identity']['T_s']:
                lines.append('|'+str(r['fixture_identity']['T_s'])+'|'+'|'.join(str(v) for v in previous)+'|')
            lines+=['','实际控制动作：'+', '.join(str(a['time_s'])+'s '+a['selected_action']['kind']+
                ('/'+a['selected_action']['mode'] if 'mode' in a['selected_action'] else '') for a in r['decision_audit'])+'。','']
    with (A/'K_TIMELINES_CN.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print('Wrote measured paired K timelines:',A/'K_TIMELINES_CN.md')
if __name__=='__main__':main()
