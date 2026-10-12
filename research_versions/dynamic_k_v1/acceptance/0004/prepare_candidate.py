"""One-shot preparation of the authorized 0004 candidate; never rewrites history."""
import hashlib
import json
from pathlib import Path

V = Path(__file__).resolve().parents[2]
ROOT = V.parents[1]
A = Path(__file__).parent


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def bind(path):
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), byte_count=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def obj(properties):
    return dict(type='object', additionalProperties=False,
                required=list(properties), properties=properties)


def prepare():
    (A/'before').mkdir(exist_ok=True)
    for source, dest in [('contracts/research_contract_v1_DRAFT_CN.md', 'contract_before.md'),
                         ('configs/research_v1_DRAFT.json', 'configuration_before.json')]:
        snapshot = A/'before'/dest
        if snapshot.exists():
            assert snapshot.read_bytes() == (V/source).read_bytes(), 'Refuse modified candidate restart'
        else:
            with snapshot.open('xb') as f:
                f.write((V/source).read_bytes())
    cp = V/'configs/research_v1_DRAFT.json'
    c = json.loads(cp.read_text(encoding='utf-8'))
    c['authorized_stage'] = 'N1a_FIXED_HORIZON_FOUR_STATE_ENERGY_ENGINEERING_ONLY'
    c['implementation_plan']['N1a'].update(
        implemented=True, authorized=True, acceptance_status='IMPLEMENTED_PENDING_SEPARATE_ACCEPTANCE',
        runtime_module='research_versions/dynamic_k_v1/runtime/n1a.py')
    c['engineering_result_schema_path'] = 'research_versions/dynamic_k_v1/schemas/n1a_engineering_result_v1.schema.json'
    with cp.open('w', encoding='utf-8', newline='\n') as out:
        out.write(json.dumps(c, ensure_ascii=False, indent=2)+'\n')
    f = V/'contracts/research_contract_v1_DRAFT_CN.md'
    s = f.read_text(encoding='utf-8')
    s = s.replace('状态：DRAFT_NOT_FROZEN。本轮授权仅覆盖 N0c 科学合同语义补充及静态验证；N0a/N0b 封存记录保持不变。',
                  '状态：DRAFT_NOT_FROZEN。N0c 已封存在修订 0003；本轮授权 N1a 固定时域与能耗的工程实现和验收，追加修订 0004。N0a/N0b、0001–0003 保持不变。')
    s = s.replace('本合同不授权生产控制器修改、仿真、训练、性能实验或旧 F3 实验恢复。',
                  '本轮仅运行解析单元/集成测试和适用历史回归；不授权生产控制器、训练、主性能实验或旧 F3 主实验恢复。')
    s = s.replace('N1a 仅在后续授权后实现固定时域推进与真实终端状态的能耗/驻留核算，包括提前排空后持续计费；',
                  'N1a 已获本轮授权，通过独立评价层实现固定时域推进与真实终端状态的能耗/驻留核算，包括提前排空后持续计费；')
    s = s.replace('本轮不宣称 N1a、N1b 或任何科学 Gate 通过。',
                  'N1a 工程验收由 acceptance/0004 独立证据说明；不宣称 N1b、N2 或任何科学 Gate 通过。')
    s += '''
## 修订 0004：N1a 独立工程实现

接口位于 runtime/n1a.py：TerminalEnergyLedger.capture/metrics、FixedHorizonEvaluator.advance_to/run/clone/checkpoint/restore、validate_measurement。计费读取 Gate B 完整状态事件日志；D2 advance_to 推进真实业务、传播及终端事件。不修改 Gate B/D2 生产代码。

J_T 按未加权的总未交付业务量在实际业务事件区间积分，不能直接使用历史 commodity.weight 加权目标。测量输出前执行数值范围、驻留总量、能耗公式、业务守恒、完成标志及拓扑时间积分的交叉校验。

工程结果独立使用 schemas/n1a_engineering_result_v1.schema.json，保留 N0c 研究 schema 草案和未执行模板。工程有限 T 与时间/能量/业务容差由调用者显式传入并记录，正式科学参数与其容差仍为 null，不继承 240/600。R_del 在零输入时约定为 1（空集合全部交付），不产生时延样本。

测试前绑定版本起点、基线 seal、父修订 0003，以及候选 0004 的实现/合同/配置清单；结果随后作为 0004 的证据封存。候选清单不将尚未生成的修订记录自身纳入，避免循环哈希。正式实验仍被禁用。年龄加权累计和已交付 fluid 平均时延均为 null，N1b 未实现。
'''
    with f.open('w', encoding='utf-8', newline='\n') as out:
        out.write(s)
    num = dict(type='number', minimum=0)
    count = dict(type='integer', minimum=0, maximum=320)
    states = ('IDLE', 'RETARGETING', 'ACQUIRING', 'ACTIVE', 'DRAINING')
    binding = obj(dict(path=dict(type='string', minLength=1), byte_count=dict(type='integer', minimum=0),
                       sha256=dict(type='string', pattern='^[0-9a-f]{64}$')))
    sample = obj(dict(t_s=num, K_active_admissible=dict(type='integer', minimum=0, maximum=160),
                      K_draining=dict(type='integer', minimum=0, maximum=160),
                      setup_connection_count=dict(type='integer', minimum=0, maximum=160),
                      setup_terminal_count=count, retargeting_terminal_count=count,
                      acquiring_terminal_count=count, setup_reserved_terminal_count=count))
    properties = dict(schema=dict(const='dynamic_k_n1a_engineering_result_v1'),
        scope=dict(const='ENGINEERING_TEST_ONLY'), scientific_gate_pass=dict(const=False),
        dynamic_terminal_count=dict(const=320),
        bindings=obj(dict(candidate_revision_id=dict(const='0004'), scope=dict(const='ENGINEERING_TEST_ONLY'),
                          implementation_manifest=binding, version_origin=binding,
                          parent_revision=binding, baseline_seal=binding)),
        input_trace_sha256=dict(type='string', pattern='^[0-9a-f]{64}$'),
        initial_state_sha256=dict(type='string', pattern='^[0-9a-f]{64}$'),
        tolerances=obj(dict(time_s=num, energy_J=num, business_bits=num)),
        T_s=dict(type='number', exclusiveMinimum=0), injection_end_s=dict(type='number', exclusiveMinimum=0),
        simulated_until_s=num, termination_reason=dict(enum=['REACHED_T', 'ENGINEERING_CHECKPOINT']),
        four_energy_state_dwell_s=obj({k:num for k in states[:4]}),
        five_execution_state_dwell_s=obj({k:num for k in states}),
        per_terminal_execution_dwell_s=dict(type='array', minItems=320, maxItems=320,
            items=obj(dict(terminal_id=dict(type='array', minItems=2, maxItems=2,
                            items=dict(type='string')), dwell_s=obj({k:num for k in states})))),
        K_time_series=dict(type='array', minItems=1, items=sample),
        delivered_bit_age_integral_bit_s=dict(type='null'), mean_delivered_fluid_delay_s=dict(type='null'),
        delivered_fluid_age_implemented=dict(const=False), R_del_T=dict(type='number', minimum=0, maximum=1))
    for name in ('E_LCT_J', 'DeltaE_LCT_J', 'standby_baseline_energy_J', 'offered_bits', 'delivered_bits',
                 'N_T_bits', 'queued_bits', 'in_flight_bits', 'J_T_bit_s'):
        properties[name] = num
    for name in ('evaluation_completed_normally', 'terminal_accounting_covers_0_T',
                 'all_offered_business_delivered'):
        properties[name] = dict(type='boolean')
    schema = {'$schema':'https://json-schema.org/draft/2020-12/schema',
              'title':'N1a engineering measurements only; numeric cross-checks also mandatory', **obj(properties)}
    write_new(V/'schemas/n1a_engineering_result_v1.schema.json', schema)
    paths = sorted((ROOT/'src').rglob('*.py'))
    paths += sorted((V/'runtime').glob('*.py'))
    paths += [V/'tests/test_n1a.py', V/'schemas/n1a_engineering_result_v1.schema.json',
              cp, f, A/'run_n1a_acceptance.py', A/'prepare_candidate.py', A/'run_regression.py']
    origin = json.loads((V/'version_record.json').read_text(encoding='utf-8'))
    anchors = dict(version_origin=bind(V/'version_record.json'), parent_revision=bind(V/'revisions/0003/record.json'),
                   baseline_seal=origin['baseline_seal'])
    assert anchors['version_origin']['sha256'] == 'ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
    assert anchors['parent_revision']['sha256'] == '7c9fa913a72ab740dfff233513c766ded57326fad2906c259d8ba56a3998baeb'
    write_new(A/'implementation_manifest.json', dict(schema='dynamic_k_n1a_candidate_implementation_v1',
        scope='ENGINEERING_TEST_ONLY', candidate_revision_id='0004', anchors=anchors,
        files=[bind(p) for p in sorted(set(paths))], formal_experiments_authorized=False,
        configuration_path=cp.relative_to(ROOT).as_posix()))
    print(json.dumps(bind(A/'implementation_manifest.json'), indent=2))


if __name__ == '__main__':
    prepare()
