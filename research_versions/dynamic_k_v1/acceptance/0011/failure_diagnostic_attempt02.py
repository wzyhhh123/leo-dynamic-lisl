"""Correct only the read-only logger's opaque native-model serialization.

Attempt01 already captured exactly identical rejected conservation inputs, but
its extra state logger could not encode native Satrec objects. Preserve it.
"""
import workflow as w
import failure_diagnostic as first
from runtime.n4_p0r_handle_reader import HandleReaderLease
from runtime.n4_p0 import causal_view
from equivalence import bind_live
original_encode=first.encode
def safe_encode(value):
    if isinstance(value,dict) and 'delay' in value and 'router' in value:
        value=value | dict(delay=None,router=None)
    return original_encode(value)
first.encode=safe_encode
def main():
    first.stage_manifest(first.SHA);live,_=first.real_fixture();g=w.guard();before=causal_view(live)
    a=first.diagnostic(live,g);w.write('conservation_failure_original_attempt02.json',a)
    with HandleReaderLease(w.old.dependencies()+[g],w.vc) as lease:
        b=first.diagnostic(bind_live(live.clone(),lease),lease.guard(g));w.write('conservation_failure_handle_attempt02.json',b)
    assert before==causal_view(live)
    assert a['error']==b['error']=='BUSINESS_CONSERVATION_MISMATCH'
    assert a['records']==b['records'] and a['root_sha256']==b['root_sha256']
    measurement=a['records'][0]['measurement']
    w.write('conservation_failure_comparison_attempt02.json',dict(status='STOP_EXISTING_CORE_BOUNDARY_REPRODUCED',
        error=a['error'],original_and_optimized_exception_equal=True,rejected_measurement_and_state_every_field_equal=True,
        root_sha256=a['root_sha256'],forecast_sha256=a['forecast_sha256'],failure_time_s=measurement['simulated_until_s'],
        offered_bits=measurement['offered_bits'],delivered_bits=measurement['delivered_bits'],remaining_bits=measurement['N_T_bits'],
        residual_bits=a['records'][0]['conservation_residual_bits'],business_tolerance_bits=measurement['tolerances']['business_bits'],
        state_exclusions=['delay/native Satrec model object and router implementation object; physical input SHA retained'],
        frozen_kernel_modified=False,tolerance_relaxed=False,full_catalog_diagnostic_executed=False,
        N4_P0_engineering_pass=False,scientific_gate_pass=False))
    first.stage_manifest(first.SHA);print('STOP_EXISTING_CORE_BOUNDARY_REPRODUCED',flush=True)
if __name__=='__main__':main()
