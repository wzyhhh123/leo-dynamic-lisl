"""Fixed-case raw figure data and export; no case search or simulation imports."""
import math
from pathlib import Path
from .result_analysis import analyze_registered_results


def finite_nonnegative(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def opening_figure_data(manifest,metrics_by_run,series_by_run,actions_by_run,events_by_run):
    analysis=analyze_registered_results(manifest,metrics_by_run)
    if analysis['status']!='COMPLETE_REGISTERED_EVIDENCE':raise ValueError('COMPLETE_REGISTERED_PACKAGE_REQUIRED_FOR_PAPER_FIGURE')
    case=manifest.get('registered_opening_figure_proposal',{})
    ids=case.get('run_ids',{})
    if set(ids)!={'B0','B1','B3','B4'} or case.get('no_post_result_case_replacement') is not True:
        raise ValueError('FIXED_OPENING_CASE_REQUIRED')
    if case.get('rho')!=.8 or case.get('phase_boundaries_s')!=[60,120,180,240]:
        raise ValueError('OPENING_CASE_REGISTRY_MISMATCH')
    registered={r['run_id']:r for r in manifest['runs']};curves=[]
    expected={'scale':160,'rho':.8,'topology_regime':'K_STAR','router':'SHORTEST_PROPAGATION_DELAY',
        'traffic':'HOTSPOT_MIGRATION','decision_cadence_s':5,'max_batch_replace':4}
    for controller in ('B0','B1','B3','B4'):
        rid=ids[controller];row=registered.get(rid,{})
        if row.get('controller')!=controller+'-v2' or any(row.get(k)!=v for k,v in expected.items()):
            raise ValueError('OPENING_CASE_CONFIG_MISMATCH:'+controller)
        metrics=metrics_by_run[rid];points=[];last=-math.inf
        for point in series_by_run[rid]:
            t=point['time_s'];q=point['queued_bits'];inflight=point['in_flight_bits']
            if not all(finite_nonnegative(v) for v in (t,q,inflight)) or t<last or t>metrics['evaluation_end_s']:
                raise ValueError('INVALID_RAW_FIGURE_TIMELINE:'+rid)
            if not all(finite_nonnegative(point[k]) for k in ('arrived_bits','delivered_bits')):
                raise ValueError('INVALID_RAW_FIGURE_TIMELINE:'+rid)
            last=t
            points.append({'time_s':t,'N_bits':q+inflight,'Q_bits':q,'I_bits':inflight,
                'A_minus_D_bits':point['arrived_bits']-point['delivered_bits']})
        if not points:raise ValueError('EMPTY_RAW_FIGURE_TIMELINE:'+rid)
        if points[0]['time_s']!=0 or points[-1]['time_s']!=metrics['evaluation_end_s']:
            raise ValueError('INCOMPLETE_RAW_FIGURE_TIMELINE:'+rid)
        markers=[]
        for decision in actions_by_run[rid]:
            action=decision['action'];count=len(action['members'])
            if count:
                t=decision['time_s']
                if not finite_nonnegative(t) or t>=600 or t>metrics['evaluation_end_s'] or not 1<=count<=4:
                    raise ValueError('INVALID_REPLACE_MARKER:'+rid)
                markers.append({'time_s':t,'batch_size':count,'batch_id':action['batch_id'],
                    'member_ids':[m['member_id'] for m in action['members']]})
        physical=[]
        for event in events_by_run[rid]:
            if event['event'] not in ('LINK_UP','LINK_DOWN'):continue
            t=event['time']
            if not finite_nonnegative(t) or t>metrics['evaluation_end_s']:raise ValueError('INVALID_PHYSICAL_MARKER:'+rid)
            physical.append({'time_s':t,'event':event['event'],'details':event['details']})
        curves.append({'controller':controller,'run_id':rid,'outcome':metrics['outcome'],
            'evaluation_end_s':metrics['evaluation_end_s'],'residual_backlog_bits':metrics['residual_backlog_bits'],
            'points':points,'replace_markers':markers,'physical_markers':physical})
    return {'schema':'F3_V2_FIXED_OPENING_RAW_DATA_V1','manifest_canonical_sha256':manifest['canonical_sha256'],
        'registered_case':case,'unit':'bits; display conversion 1 Gbit = 1e9 bit',
        'curves':curves,'resampling':False,'smoothing':False,'curves_ranked_by_J':False,
        'caption_notes':['N=Q+I from raw recorded states; A-D preserved as conservation cross-check',
            'lines connect recorded states; figure is not the objective-integral calculator',
            'LINK_DOWN includes natural expiry; do not equate every physical down event with setup outage',
            'COMPLETE/CENSORED status and residuals retained; censored curves do not imply complete-J ranking']}


def render_opening_figure(data,output_dir,*,engineering_fixture=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=Path(output_dir)
    if not out.is_dir():raise ValueError('EXISTING_NEW_ATTEMPT_DIRECTORY_REQUIRED')
    targets=[out/'opening_figure.png',out/'opening_figure.pdf']
    if any(p.exists() for p in targets):raise FileExistsError('FIGURE_ATTEMPT_MUST_NOT_BE_OVERWRITTEN')
    fig,axes=plt.subplots(5,1,figsize=(9,11),sharex=True,gridspec_kw={'height_ratios':[2,2,2,1.2,1.2]},constrained_layout=True)
    colors={'B0':'#555555','B1':'#D55E00','B3':'#0072B2','B4':'#009E73'}
    for index,curve in enumerate(data['curves']):
        color=colors[curve['controller']];label=curve['controller']+' / '+curve['outcome']
        points=curve['points'];times=[p['time_s'] for p in points]
        for ax,key in zip(axes[:3],('N_bits','Q_bits','I_bits')):
            ax.plot(times,[p[key]/1e9 for p in points],color=color,label=label,lw=1.4)
        markers=curve['replace_markers']
        if markers:axes[3].scatter([p['time_s'] for p in markers],[p['batch_size'] for p in markers],s=22,color=color,marker='o',label=curve['controller'])
        for event_name,symbol in (('LINK_UP','^'),('LINK_DOWN','v')):
            events=[p for p in curve['physical_markers'] if p['event']==event_name]
            if events:axes[4].scatter([p['time_s'] for p in events],[index]*len(events),s=22,color=color,marker=symbol)
    for ax in axes:
        for boundary in data['registered_case']['phase_boundaries_s']:ax.axvline(boundary,color='#777777',ls=':',lw=.8)
        ax.grid(alpha=.18)
    for ax,label in zip(axes[:3],('Unfinished N (Gbit)','Queued Q (Gbit)','In flight I (Gbit)')):ax.set_ylabel(label)
    axes[0].legend(fontsize=8,loc='upper left',ncol=2)
    axes[3].set_ylabel('REPLACE\nbatch size');axes[3].set_yticks([0,1,2,3,4]);axes[3].set_ylim(-.3,4.5)
    axes[4].set_ylabel('Physical link\nUP / DOWN');axes[4].set_yticks(range(4));axes[4].set_yticklabels([c['controller'] for c in data['curves']])
    axes[4].set_xlabel('Simulation time (s)')
    end=max(c['evaluation_end_s'] for c in data['curves']);axes[4].set_xlim(0,max(240,end))
    title='Fixed registered opening case: 160 satellites, rho = 0.8'
    if engineering_fixture:title='ENGINEERING LITERAL FIXTURE ONLY — '+title
    fig.suptitle(title,fontsize=11)
    try:
        fig.savefig(targets[0],dpi=180);fig.savefig(targets[1])
    finally:plt.close(fig)
    return [p.name for p in targets]
