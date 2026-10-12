"""Complete tiny legal/action oracle; never a main-scale controller."""
import itertools
from dataclasses import replace
from .joint_action import JointAction,canonical_sha256
from .joint_proposer import JointProposalPool
from .snapshot_controllers import SnapshotBatchController
from .batch_rollout import JointRolloutController


def enumerate_tiny_joint_actions(engine,validator,physical_singletons,*,max_members):
    if not 4<=len(engine.nodes)<=16 or len(physical_singletons)>8:
        raise ValueError('TINY_ORACLE_ONLY_NOT_MAIN_SCALE')
    if not 1<=max_members<=4:raise ValueError('TINY_ACTION_SIZE_OUTSIDE_CONTRACT')
    members=tuple(sorted(physical_singletons,key=lambda m:m.canonical_index))
    root=engine.decision_root_sha256();frame=engine.absolute_time_frame_id
    actions=[];plans=[];rejected=[]
    for size in range(max_members+1):
        for subset in itertools.combinations(members,size):
            a=JointAction(engine.now,frame,root,canonical_sha256([]),subset)
            p=validator.evaluate(engine.executor,a,decision_root_sha256=root)
            if not p.accepted:
                rejected.append({'action':a.to_dict(),'reason':p.reason});continue
            actions.append(a)
            if subset:plans.append(p)
    digest=canonical_sha256({'actions':[a.identity_document() for a in actions],'rejected':rejected})
    actions=tuple(replace(a,joint_proposal_set_sha256=digest) for a in actions)
    plans=tuple(replace(p,action=a) for p,a in zip(plans,actions[1:]))
    audit={'oracle':True,'rejections':rejected,'complete_enumeration_through_size':max_members,
           'evaluation_count':len(actions)+len(rejected),'physical_singletons':len(members)}
    return JointProposalPool(root,digest,actions,plans,audit,members)


def audit_tiny_approximation(engine,validator,bounded_pool,*,max_members,horizon_s):
    exact=enumerate_tiny_joint_actions(engine,validator,bounded_pool.physical_singletons,max_members=max_members)
    before=engine.canonical_state_sha256()
    b3=SnapshotBatchController('B3-v2',eta_aggregation='min')
    b4=JointRolloutController(validator,rollout_cap=len(exact.actions))
    exact_b3=b3.observe(engine,exact);bounded_b3=b3.observe(engine,bounded_pool)
    exact_b4=b4.observe(engine,exact,horizon_s=horizon_s)
    bounded_b4=b4.observe(engine,bounded_pool,horizon_s=horizon_s)
    ids={a.batch_id for a in bounded_pool.actions};by_size={}
    for size in range(max_members+1):
        actions=[a for a in exact.actions if len(a.members)==size]
        retained=sum(a.batch_id in ids for a in actions)
        by_size[str(size)]={'exact_legal':len(actions),'retained':retained,
                           'recall':retained/len(actions) if actions else None}
    exact_score=exact_b4.metadata['branches'][exact_b4.metadata['selected_pool_index']]['J_H_bit_s']
    bounded_score=bounded_b4.metadata['branches'][bounded_b4.metadata['selected_pool_index']]['J_H_bit_s']
    if engine.canonical_state_sha256()!=before:raise AssertionError('TINY_ORACLE_CHANGED_LIVE_STATE')
    return {'scope':'TINY_ENGINEERING_ONLY','exact_legal_pool':exact.public_document(),
            'coverage_by_size':by_size,'omitted_batch_ids':[a.batch_id for a in exact.actions if a.batch_id not in ids],
            'exact_B3_batch_id':exact_b3.action.batch_id,'bounded_B3_batch_id':bounded_b3.action.batch_id,
            'exact_B4_batch_id':exact_b4.action.batch_id,'bounded_B4_batch_id':bounded_b4.action.batch_id,
            'exact_B4_J_H':exact_score,'bounded_B4_J_H':bounded_score,
            'same_forecast':True,'B3_B4_equal_action_required':False,'budgets_tuned_by_this_result':False,
            'main_scale_optimality_claim':False}
