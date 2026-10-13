"""Read-only reproduction of the failed authorized PERSIST/ADD branch.

No further candidates, cost search or simulation scenarios. Capture unchanged
validation inputs, preserve exceptions, compare original vs optimized path.
"""
import json,time,traceback
from copy import deepcopy
from unittest.mock import patch
import workflow as w
from controlled_cost import real_fixture,stage_manifest,SETUP,COST
from equivalence import bind_live
from runtime.n4_p0 import ForecastInput,causal_view,make_sanitized_root,score_action,data_hash,encode
from runtime.n4_p0r_handle_reader import HandleReaderLease
from runtime.n2_actions import Add
from runtime.n2_controller import AtomicTopologyController
from runtime import n1a

SHA='c23f188ebc7bfcea9b04d53749d9111b48872ac46ac3eec84669263378de5ec7'
def diagnostic(live,g):
    records=[];old_validate=n1a.validate_measurement;old_advance=AtomicTopologyController.advance_to
    def validate(result):
        try:return old_validate(result)
        except Exception as error:
            records.append(dict(kind='UNCHANGED_MEASUREMENT_REJECTED',error=str(error),measurement=deepcopy(result),
                conservation_residual_bits=result['offered_bits']-result['delivered_bits']-result['N_T_bits']))
            raise
    def advance(obj,t):
        try:return old_advance(obj,t)
        except Exception as error:
            records.append(dict(kind='BRANCH_STATE_AT_EXCEPTION',requested_time_s=t,actual_time_s=obj.engine.now,
                error=str(error),engine_state=encode(obj.engine.business_state()),age_state=encode(vars(obj.evaluator.age)),
                age_observations=encode(obj.engine.age_observations),energy_state=encode(vars(obj.evaluator.base.ledger)),
                physical_input_sha256=obj.physical_sha256))
            raise
    fc=ForecastInput.from_current(causal_view(live).observation,T_s=30.,H_s=6.,mode='PERSIST');root=make_sanitized_root(live,fc,binding=g)
    error=None;trace=None;result=None
    with patch.object(n1a,'validate_measurement',validate),patch.object(AtomicTopologyController,'advance_to',advance):
        try:result=score_action(root,Add(('X0_10','D2'),('X1_10','D1'),SETUP),COST,cadence_s=3.)
        except Exception as exc:error=str(exc);trace=traceback.format_exc()
    return dict(error=error,traceback=trace,records=records,result=result,root_sha256=root.view.state_sha256,
        forecast_sha256=fc.sha256,observer_calls_original_once=True,observer_changes_service=False,tolerance_relaxed=False)
def main():
    stage_manifest(SHA);live,_=real_fixture();g=w.guard();before=causal_view(live)
    a=diagnostic(live,g);w.write('conservation_failure_original.json',a)
    with HandleReaderLease(w.old.dependencies()+[g],w.vc) as lease:
        b=diagnostic(bind_live(live.clone(),lease),lease.guard(g));w.write('conservation_failure_handle.json',b)
    assert before==causal_view(live)
    equal=a['records']==b['records'];assert equal and a['error']==b['error']=='BUSINESS_CONSERVATION_MISMATCH'
    # Different wrapper/module names may appear in traceback; actual state and
    # every rejected result field must be exactly equal, without tolerance.
    w.write('conservation_failure_comparison.json',dict(status='STOP_EXISTING_CORE_BOUNDARY_REPRODUCED',
        original_and_optimized_exception_equal=True,rejected_measurement_and_state_every_field_equal=equal,
        original_root_equals_optimized_root=a['root_sha256']==b['root_sha256'],forecast_sha256=a['forecast_sha256'],
        records=a['records'],frozen_kernel_modified=False,full_catalog_diagnostic_executed=False,
        N4_P0_engineering_pass=False,scientific_gate_pass=False))
    stage_manifest(SHA);print('STOP_EXISTING_CORE_BOUNDARY_REPRODUCED',flush=True)
if __name__=='__main__':main()
