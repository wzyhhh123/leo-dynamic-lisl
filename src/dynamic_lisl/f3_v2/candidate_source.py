"""Independent traffic-blind terminal-level replacement source."""
from dataclasses import dataclass,replace
from ..terminal_executor import pair
from .joint_action import BatchReplaceMember,JointAction,canonical_sha256,terminal_state_hash
from .batch_executor import BatchPhysicalValidator


@dataclass(frozen=True)
class RawCandidateBudget:
    BBM_cap:int
    MBB_cap:int
    total_cap:int
    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in self.__dict__.values()):raise ValueError('EXPLICIT_RAW_BUDGET_REQUIRED')
        if self.total_cap<self.BBM_cap+self.MBB_cap:raise ValueError('RAW_TOTAL_INCONSISTENT_WITH_STRATA')


def replacement_inventory(executor,physical_layer,*,plane_by_satellite,retarget_a_s,
                          retarget_b_s,acquisition_s,observation_end_s,raw_budget=None):
    before=terminal_state_hash(executor);rejected=[];entries=[]
    frame='STRUCTURAL_RAW_SOURCE'
    validator=BatchPhysicalValidator(physical_layer,max_batch_replace=1,
        observation_end_s=observation_end_s,absolute_time_frame_id=frame)
    windows=physical_layer.catalog.terminal_pair_candidates(executor.now,executor.satellite_ids)
    for old in sorted(executor.links.values(),key=lambda l:l.endpoints):
        if old.draining or old.release_owner:continue
        for w in windows:
            new=pair(w.endpoint_a,w.endpoint_b)
            if plane_by_satellite[new[0][0]]==plane_by_satellite[new[1][0]]:continue
            if new==old.endpoints:continue
            identity={'time_s':executor.now,'old':old.endpoints,'new':new}
            m=BatchReplaceMember('V2-RAW-'+canonical_sha256(identity),0,old.endpoints,new,
                                 retarget_a_s,retarget_b_s,acquisition_s)
            # Same evaluator as runtime legality. Rejections are retained in the
            # uncapped audit, not silently removed to improve coverage statistics.
            p=validator.evaluate(executor,JointAction(executor.now,frame,before,canonical_sha256([]),(m,)))
            if not p.accepted:
                rejected.append({'member_id':m.member_id,'reason':p.reason});continue
            entries.append((m,p.member_results[0]))
    def rank(x):
        m,r=x
        return (-r['usable_lifetime_s'],int(r['window'].get('plane_gap') or 0),m.old_binding,m.new_terminal_pair,m.member_id)
    groups={mode:sorted((x for x in entries if x[1]['transition_mode']==mode),key=rank) for mode in ('MBB','BBM')}
    selected=groups['MBB']+groups['BBM'] if raw_budget is None else groups['MBB'][:raw_budget.MBB_cap]+groups['BBM'][:raw_budget.BBM_cap]
    members=tuple(replace(m,canonical_index=i) for i,(m,r) in enumerate(selected))
    if terminal_state_hash(executor)!=before:raise AssertionError('RAW_SOURCE_CHANGED_EXECUTOR')
    doc={'schema':'f3_v2_raw_source_v1','root_terminal_sha256':before,'time_s':executor.now,
         'uncapped':raw_budget is None,'uncapped_physical_count':len(entries),
         'selected_member_ids':[m.member_id for m in members],'members':[m.to_dict() for m in members],
         'stratum_counts':{mode:sum(r['transition_mode']==mode for m,r in selected) for mode in ('MBB','BBM')},
         'physical_rejections':rejected,'performance_input_read':False}
    return {'members':members,'audit':doc,'raw_source_sha256':canonical_sha256(doc)}
