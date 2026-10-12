"""N1b wrapper; unchanged N1a metrics are retained as a separate result object."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import math

from .bindings import EngineeringBinding
from .n1a import FixedHorizonEvaluator, require, finite
from .n1b_fifo import DeliveredAgeLedger, rational
from .n1b_observer import ObservedD2Engine


class N1bEvidenceBinding(EngineeringBinding):
    def verify(self):
        tool=Path(__file__).resolve().parents[1]/'tools/version_control.py'
        spec=importlib.util.spec_from_file_location('n1b_binding_vc',tool)
        vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
        root=self.project_root
        path=vc.safe_path(root,self.manifest_path)
        info=vc.file_info(path)
        require(info['sha256']==self.expected_manifest_sha256,'N1B_CANDIDATE_ANCHOR_MISMATCH')
        m=vc.read_json(path)
        require(m['schema']=='dynamic_k_n1b_candidate_v1' and m['candidate_revision_id']=='0005'
                and m['formal_experiments_authorized'] is False,'N1B_UNAUTHORIZED_BINDING')
        seen=set()
        for row in m['files']+list(m['anchors'].values()):
            require(row['path'] not in seen,'DUPLICATE_N1B_BINDING');seen.add(row['path'])
            require(vc.file_info(vc.safe_path(root,row['path']))=={k:row[k] for k in ('byte_count','sha256')},
                    'N1B_FILE_BINDING_MISMATCH:'+row['path'])
        c=vc.read_json(vc.safe_path(root,m['configuration_path']))
        require(all(v is None for v in c['scientific_parameters'].values())
                and c['algorithm_selection'] is None and c['formal_experiments_authorized'] is False,
                'N1B_UNRESOLVED_SCIENCE_BOUNDARY_VIOLATION')
        return dict(scope='ENGINEERING_TEST_ONLY',candidate_revision_id='0005',
            implementation_manifest=dict(path=self.manifest_path,**info),anchors=m['anchors'])


class DeliveredFluidEvaluator:
    def __init__(self,engine,*,T_s,time_tolerance_s,energy_tolerance_J,
                 business_tolerance_bits,n1a_binding,n1b_binding):
        require(isinstance(engine,ObservedD2Engine),'READ_ONLY_D2_OBSERVER_REQUIRED')
        n1b_binding.verify()
        self.binding=n1b_binding
        self.age=DeliveredAgeLedger(engine)
        self.base=FixedHorizonEvaluator(engine,T_s=T_s,time_tolerance_s=time_tolerance_s,
            energy_tolerance_J=energy_tolerance_J,business_tolerance_bits=business_tolerance_bits,
            evidence_binding=n1a_binding)

    def advance_to(self,t):
        self.binding.verify()
        core=self.base.advance_to(t)
        self.age.consume(self.base.engine)
        age=self.age.metrics()
        reported=core['delivered_bits']; physical=age['delivered_bits']
        require(not reported or physical>0,'DELIVERED_COUNTER_WITHOUT_KNOWN_AGE')
        self.age._roundoff(rational(reported)-rational(physical),dict(state='REPORTED_DELIVERY',time=t))
        age=self.age.metrics()
        mean=age['delivered_bit_age_integral_bit_s']/reported if reported else None
        mean_bound=(age['delivered_age_absolute_error_bound_bit_s']/reported
                    +abs(mean-age['mean_delivered_fluid_delay_s'])+math.ulp(mean)/2) if reported and physical else None
        if mean_bound is not None:mean_bound=math.nextafter(mean_bound,math.inf)
        result=dict(schema='dynamic_k_n1b_engineering_result_v1',scope='ENGINEERING_TEST_ONLY',
            bindings=self.binding.verify(),fifo='NODE_LOCAL_PER_COMMODITY_FIFO',
            delivered_bits=reported,delivered_bit_age_integral_bit_s=age['delivered_bit_age_integral_bit_s'],
            mean_delivered_fluid_delay_s=mean,mean_delay_absolute_error_bound_s=mean_bound,
            n1a_result=core,age_accounting=age,scientific_gate_pass=False,N2_implemented=False)
        validate_n1b(result)
        return result

    def run(self):return self.advance_to(self.base.T)

    def clone(self):return deepcopy(self)

    def checkpoint(self):return self.clone()

    @classmethod
    def restore(cls,checkpoint):
        require(type(checkpoint) is cls,'INVALID_N1B_CHECKPOINT')
        return checkpoint.clone()


def validate_n1b(r):
    require(r['schema']=='dynamic_k_n1b_engineering_result_v1' and r['scope']=='ENGINEERING_TEST_ONLY'
            and r['scientific_gate_pass'] is False and r['N2_implemented'] is False,'N1B_RESULT_SCOPE')
    from .n1a import validate_measurement
    validate_measurement(r['n1a_result'])
    finite(r['delivered_bits'],'delivered_bits')
    finite(r['delivered_bit_age_integral_bit_s'],'delivered_age')
    require(r['delivered_bits']==r['n1a_result']['delivered_bits'],'N1B_DELIVERY_MISMATCH')
    if r['delivered_bits']:
        finite(r['mean_delivered_fluid_delay_s'],'mean_delay',maximum=r['n1a_result']['simulated_until_s'])
        require(r['mean_delivered_fluid_delay_s']==r['delivered_bit_age_integral_bit_s']/r['delivered_bits'],
                'N1B_MEAN_RATIO_MISMATCH')
        finite(r['mean_delay_absolute_error_bound_s'],'delay_bound')
    else:
        require(r['mean_delivered_fluid_delay_s'] is None and r['mean_delay_absolute_error_bound_s'] is None
                and r['delivered_bit_age_integral_bit_s']==0,'ZERO_DELIVERY_MEAN_MUST_BE_NULL')
    a=r['age_accounting']
    bound=a['delivered_age_absolute_error_bound_bit_s']
    finite(bound,'age_bound')
    finite(a['remaining_bit_age_integral_bit_s'],'remaining_age')
    require(r['delivered_bit_age_integral_bit_s']==a['delivered_bit_age_integral_bit_s'],
            'N1B_AGE_MISMATCH')
    finite(a['delivered_bits'],'physical_delivered')
    finite(a['roundoff_mass_envelope_bits'],'roundoff_mass')
    finite(a['temporal_correction_age_bound_bit_s'],'temporal_age_bound')
    require(abs(a['delivered_bits']-r['delivered_bits'])<=a['roundoff_mass_envelope_bits'],
            'N1B_DELIVERY_ENVELOPE_VIOLATION')
    residual=abs(r['n1a_result']['J_T_bit_s']-a['delivered_bit_age_integral_bit_s']-a['remaining_bit_age_integral_bit_s'])
    require(residual<=2*bound+64*math.ulp(max(1.,r['n1a_result']['J_T_bit_s'])),
            'N1B_CONDITIONAL_AGE_AREA_IDENTITY_VIOLATION')
