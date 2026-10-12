"""Engineering-only bounded observation of the unchanged replacement source.

Run in an isolated engineering process. The temporary validator wrapper returns
the original result, restores its module binding on every exit, and never
provides a partial inventory as a production source or a coverage certificate.
"""
import math
import time
from unittest.mock import patch
from . import candidate_source
from .joint_action import terminal_state_hash


class ObservationBudgetReached(RuntimeError):
    pass


def observe_replacement_source(executor,physical_layer,*,max_evaluations,wall_budget_s,
                               row_sink=None,legacy_physical=False,**source_kwargs):
    if type(max_evaluations) is not int or max_evaluations<1 or not math.isfinite(wall_budget_s) or wall_budget_s<=0:
        raise ValueError('EXPLICIT_ENGINEERING_OBSERVATION_BUDGET_REQUIRED')
    before=terminal_state_hash(executor);original=candidate_source.BatchPhysicalValidator
    rows=[];started=time.perf_counter();result=None;error=None;status=None

    class ObservedValidator(original):
        def __init__(self,*args,**kwargs):
            kwargs['counterfactual_physical_clone']=not legacy_physical
            super().__init__(*args,**kwargs)
        def evaluate(self,live,action,**kwargs):
            if len(rows)>=max_evaluations:raise ObservationBudgetReached('ROW_EVALUATION_BUDGET')
            if time.perf_counter()-started>=wall_budget_s:raise ObservationBudgetReached('WALL_BUDGET')
            call_start=time.perf_counter();evaluation=super().evaluate(live,action,**kwargs)
            member=action.members[0]
            row={'index':len(rows),'member_id':member.member_id,'old_binding':member.old_binding,
                 'new_terminal_pair':member.new_terminal_pair,'accepted':evaluation.accepted,
                 'reason':evaluation.reason,'validator_wall_s':time.perf_counter()-call_start,
                 'member_result':evaluation.member_results[0] if evaluation.member_results else None}
            rows.append(row)
            if row_sink is not None:row_sink(row)
            return evaluation

    try:
        with patch.object(candidate_source,'BatchPhysicalValidator',ObservedValidator):
            result=candidate_source.replacement_inventory(executor,physical_layer,**source_kwargs)
        status='SOURCE_OBSERVATION_COMPLETE'
    except ObservationBudgetReached as failure:
        status='SOURCE_OBSERVATION_BUDGET_UNKNOWN';error=str(failure)
    except Exception as failure:
        status='SOURCE_OBSERVATION_FAIL_STOP';error=type(failure).__name__+':'+str(failure)
    after=terminal_state_hash(executor)
    restored=candidate_source.BatchPhysicalValidator is original
    if before!=after or not restored:
        status='SOURCE_OBSERVATION_FAIL_STOP';error='LIVE_MUTATION_OR_WRAPPER_NOT_RESTORED';result=None
    return {'status':status,'source_result':result,'rows':rows,'error':error,
        'wall_s':time.perf_counter()-started,'validator_wall_total_s':sum(r['validator_wall_s'] for r in rows),
        'evaluations_completed':len(rows),'root_before_sha256':before,'root_after_sha256':after,
        'live_unchanged':before==after,'wrapper_restored':restored,
        'complete_raw_coverage_known':status=='SOURCE_OBSERVATION_COMPLETE',
        'partial_result_not_usable_as_source':status!='SOURCE_OBSERVATION_COMPLETE',
        'production_source_modified':False,'controller_performance_read':False,
        'registered_experiment_started':False}
