"""Export the fixed opening case from sealed registered results; no simulation."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.result_analysis import load_sealed_registered_results
from dynamic_lisl.f3_v2.paper_figures import opening_figure_data,render_opening_figure
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True);parser.add_argument('--run-directory-map',required=True)
    args=parser.parse_args()
    out=ROOT/'outputs'/('f3_v2_paper_figures_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    write_new_json(out/'invocation.json',{'command':sys.argv,'cwd':str(Path.cwd()),
        'tool_sha256':file_sha256(Path(__file__)),'registered_experiment_started':False})
    try:
        manifest=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        mapping=json.loads(Path(args.run_directory_map).read_text(encoding='utf-8'))
        metrics,sources=load_sealed_registered_results(ROOT,manifest,mapping)
        write_new_json(out/'source_evidence_hashes.json',sources)
        by_file=lambda name:{rid:json.loads((ROOT/mapping[rid]/name).read_text(encoding='utf-8')) for rid in mapping}
        data=opening_figure_data(manifest,metrics,by_file('timeseries.json'),
            by_file('action_timeline.json'),by_file('transition_timeline.json'))
        write_new_json(out/'opening_figure_data.json',data)
        exports=render_opening_figure(data,out)
        caption=('固定预注册opening case：160星、rho=0.8、K*、热点迁移、shortest-propagation common router、'
                 '5 s决策和最多4条REPLACE。N/Q/I为原始记录的unfinished/queued/in-flight work；'
                 '点间连线不用于计算J。圆点标记实际选中batch大小，向上/向下三角分别标记物理LINK_UP/DOWN（包括自然到期）。'
                 '竖线为60/120/180/240 s外生phase边界；COMPLETE/CENSORED均保留，不根据曲线或J替换case。')
        (out/'opening_figure_caption_CN.md').write_text(caption+'\n',encoding='utf-8')
        report={'status':'FIXED_REGISTERED_FIGURE_EXPORT_PASS','exports':exports,
            'manifest_canonical_sha256':manifest['canonical_sha256'],'run_ids':data['registered_case']['run_ids'],
            'result_based_case_selection':False,'censored_run_ids':[c['run_id'] for c in data['curves'] if c['outcome']!='COMPLETE'],
            'controller_performance_run_started':False}
    except Exception as error:
        report={'status':'FIGURE_EXPORT_BLOCKED','error_type':type(error).__name__,'error':str(error),
            'controller_performance_run_started':False}
        write_new_json(out/'failure_summary.json',report)
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out)},indent=2))
    return 0 if report['status']=='FIXED_REGISTERED_FIGURE_EXPORT_PASS' else 1


if __name__=='__main__':raise SystemExit(main())
