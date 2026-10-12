"""Append-only N1b candidate and result schema; no historical file mutation."""
import hashlib
import json
from pathlib import Path

V=Path(__file__).resolve().parents[2]
P=V.parents[1]
A=Path(__file__).parent
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='815352309856b9e8aa2c5ffbb4e233dd412b6bc7aa3fd2365ea03e17230411f9'

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def bind(path):
    data=path.read_bytes()
    return dict(path=path.relative_to(P).as_posix(),byte_count=len(data),sha256=hashlib.sha256(data).hexdigest())

def obj(properties):
    return dict(type='object',additionalProperties=False,required=list(properties),properties=properties)

def main():
    static=json.loads((A/'fifo_static_report.json').read_text(encoding='utf-8'))
    assert static['status']=='PASS'
    num=dict(type='number',minimum=0)
    nullable=dict(anyOf=[num,dict(type='null')])
    row=obj(dict(path=dict(type='string'),byte_count=dict(type='integer',minimum=0),
                 sha256=dict(type='string',pattern='^[0-9a-f]{64}$')))
    old=json.loads((V/'schemas/n1a_engineering_result_v1.schema.json').read_text(encoding='utf-8'))
    props=dict(schema=dict(const='dynamic_k_n1b_engineering_result_v1'),scope=dict(const='ENGINEERING_TEST_ONLY'),
        fifo=dict(const='NODE_LOCAL_PER_COMMODITY_FIFO'),scientific_gate_pass=dict(const=False),N2_implemented=dict(const=False),
        bindings=obj(dict(scope=dict(const='ENGINEERING_TEST_ONLY'),candidate_revision_id=dict(const='0005'),
                         implementation_manifest=row,anchors=dict(type='object',additionalProperties=row))),
        delivered_bits=num,delivered_bit_age_integral_bit_s=num,mean_delivered_fluid_delay_s=nullable,
        mean_delay_absolute_error_bound_s=nullable,n1a_result=old,
        age_accounting=obj(dict(delivered_bits=num,delivered_bit_age_integral_bit_s=num,
            mean_delivered_fluid_delay_s=nullable,remaining_bit_age_integral_bit_s=num,
            exact_rational=obj({k:dict(type='string') for k in ('delivered_bits','M_D_bit_s','remaining_bit_age_integral_bit_s')}),
            metric_status=dict(enum=['IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT',
                                    'EXACT_RATIONAL_ENCODED_TRACE_WITH_FLOAT_OUTPUT_ROUNDING']),
            roundoff_mass_envelope_bits=num,temporal_correction_age_bound_bit_s=num,
            delivered_age_absolute_error_bound_bit_s=num,closure_audit=dict(type='array'),roundoff_audit=dict(type='array'))))
    write_new(V/'schemas/n1b_engineering_result_v1.schema.json',
        {'$schema':'https://json-schema.org/draft/2020-12/schema',**obj(props)})
    paths=list((P/'src').rglob('*.py'))+list((V/'runtime').glob('*.py'))
    paths += [V/'tests/test_n1b_fifo.py',V/'tests/test_n1a.py',
              V/'schemas/n1b_engineering_result_v1.schema.json',V/'schemas/n1a_engineering_result_v1.schema.json',
              V/'contracts/N1B_NODE_LOCAL_FIFO_SEMANTICS_CN.md',V/'contracts/N1B_NUMERICAL_PRECISION_CN.md',
              V/'configs/n1b_fifo_semantics_v1.json',A/'fifo_static_report.json',
              A/'check_fifo_semantics.py',A/'prepare_candidate.py',A/'run_acceptance.py',
              V/'tools/version_control.py',V/'acceptance/0004/implementation_manifest.json',
              V/'acceptance/0004/run_regression.py']
    origin=json.loads((V/'version_record.json').read_text(encoding='utf-8'))
    anchors=dict(version_origin=bind(V/'version_record.json'),parent_revision=bind(V/'revisions/0004/record.json'),
                 baseline_seal=origin['baseline_seal'])
    assert anchors['version_origin']['sha256']==ORIGIN and anchors['parent_revision']['sha256']==PARENT
    write_new(A/'implementation_manifest.json',dict(schema='dynamic_k_n1b_candidate_v1',scope='ENGINEERING_TEST_ONLY',
        candidate_revision_id='0005',files=[bind(p) for p in sorted(set(paths))],anchors=anchors,
        configuration_path='research_versions/dynamic_k_v1/configs/n1b_fifo_semantics_v1.json',
        formal_experiments_authorized=False))
    print(json.dumps(bind(A/'implementation_manifest.json'),indent=2))

if __name__=='__main__':main()
