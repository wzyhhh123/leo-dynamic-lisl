"""One-shot N2 candidate, pinning unchanged upstream runtime and geometry input."""
import hashlib
import json
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='c2567b66fe880035853aba2b81463ece42443973d5b5178ae0b28e77a6c44769'
def write_new(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def bind(p):
    data=p.read_bytes()
    return dict(path=p.relative_to(P).as_posix(),byte_count=len(data),sha256=hashlib.sha256(data).hexdigest())
def obj(p):return dict(type='object',required=list(p),properties=p,additionalProperties=False)
def main():
    row=obj(dict(path=dict(type='string'),byte_count=dict(type='integer',minimum=0),sha256=dict(type='string',pattern='^[0-9a-f]{64}$')))
    count=dict(type='integer',minimum=0,maximum=320)
    n1b=json.loads((V/'schemas/n1b_engineering_result_v1.schema.json').read_text(encoding='utf-8'))
    properties=dict(schema=dict(const='dynamic_k_n2_engineering_result_v1'),scope=dict(const='ENGINEERING_TEST_ONLY'),
        bindings=obj(dict(scope=dict(const='ENGINEERING_TEST_ONLY'),candidate_revision_id=dict(const='0006'),implementation_manifest=row,
                         anchors=dict(type='object',additionalProperties=row))),
        physical_input_sha256=dict(type='string',pattern='^[0-9a-f]{64}$'),n1b_result=n1b,
        K_admit=count,K_draining=count,setup_terminal_count=count,reserved_terminal_count=count,
        dynamic_terminal_states=dict(type='array',minItems=320,maxItems=320,items=dict(type='object')),
        dynamic_K_time_series=dict(type='array',minItems=1,items=dict(type='object')),
        action_receipts=dict(type='array',items=dict(type='object')),release_audit=dict(type='array',items=dict(type='object')),
        scientific_gate_pass=dict(const=False),formal_experiments_executed=dict(const=False),N3_implemented=dict(const=False))
    write_new(V/'schemas/n2_engineering_result_v1.schema.json',{'$schema':'https://json-schema.org/draft/2020-12/schema',**obj(properties)})
    paths=list((P/'src').rglob('*.py'))+list((V/'runtime').glob('*.py'))
    paths+=[V/'tests/test_n2_actions.py',V/'tests/test_n1a.py',V/'tests/test_n1b_fifo.py',
        V/'contracts/N2_ATOMIC_TOPOLOGY_ACTIONS_CN.md',V/'configs/n2_action_semantics_v1.json',
        V/'schemas/n2_engineering_result_v1.schema.json',V/'schemas/n1b_engineering_result_v1.schema.json',
        V/'schemas/n1a_engineering_result_v1.schema.json',V/'acceptance/0004/implementation_manifest.json',
        V/'acceptance/0005/implementation_manifest.json',V/'tools/version_control.py',A/'prepare_candidate.py',
        A/'run_acceptance.py',A/'run_historical_regression.py',
        P/'configs/hardware_gate_c_simplified_v1.json',
        P/'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',
        P/'outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json']
    paths += [P/'data/raw/sgp4_x720'/name for name in ('manifest.json','hashes.json','constellation.tle')]
    origin=json.loads((V/'version_record.json').read_text(encoding='utf-8'))
    anchors=dict(version_origin=bind(V/'version_record.json'),parent_revision=bind(V/'revisions/0005/record.json'),baseline_seal=origin['baseline_seal'])
    assert anchors['version_origin']['sha256']==ORIGIN and anchors['parent_revision']['sha256']==PARENT
    write_new(A/'implementation_manifest.json',dict(schema='dynamic_k_n2_candidate_v1',scope='ENGINEERING_TEST_ONLY',
        candidate_revision_id='0006',configuration_path='research_versions/dynamic_k_v1/configs/n2_action_semantics_v1.json',
        files=[bind(p) for p in sorted(set(paths))],anchors=anchors,formal_experiments_authorized=False))
    print(json.dumps(bind(A/'implementation_manifest.json'),indent=2))
if __name__=='__main__':main()
