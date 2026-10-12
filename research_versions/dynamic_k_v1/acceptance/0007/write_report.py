"""Create the Chinese engineering report from accepted evidence, append-only."""
import argparse,json
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);args=parser.parse_args()
    dest=A/args.attempt;assert dest.parent==A
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    summary=read(dest/'acceptance_summary.json');assert summary['status']=='PASS'
    examples=read(dest/'engineering_examples.json')['examples'];coverage=read(dest/'catalog_coverage.json')
    pairs={k:v for k,v in examples.items() if isinstance(v,dict) and 'STATIC_HOLD' in v}
    real=examples['real160_natural_SGP4_controlled_catalog_paired_multi_epoch'];pairs['real160_natural_SGP4']=real['paired_results']
    metrics=dict(scope='ENGINEERING_TEST_ONLY',scientific_performance_claimed=False,
        paired_scenarios={k:{name:dict(metrics=value['metrics'],fixture_identity=value['fixture_identity'],
            non_HOLD_accepted_count=value['non_HOLD_accepted_count'],
            actions=[dict(time_s=row['time_s'],action=row['selected_action'],reason=row['selection']['reason'],
                gate_receipt=row['actual_gate_receipt']) for row in value['decision_audit']],
            release_audit=value['n2_result']['release_audit']) for name,value in pair.items()} for k,pair in pairs.items()})
    with (A/'paired_metrics.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(metrics,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    lines=['# N3 动态 K 业务感知闭环工程结果','',
        'N3 Engineering PASS。仅验证工程功能与机制，不构成科学 Gate PASS，不构成性能优越性、统计显著性或最优性结论。未运行正式主实验或训练。',
        '', '## 实现与信息边界','',
        '新增 runtime/n3_baselines.py：CurrentObservation / observe_current、StaticHold、ReactiveDynamicK、ClosedLoopBaseline.step/run/clone/checkpoint/restore、paired_runs、validate_n3 和 N3EvidenceBinding。独立合同、配置、schema、专项测试、封存工具与证据均在 dynamic_k_v1 内。N1a/N1b/N2、冻结生产 src、旧测试/合同/manifest/输出和修订 0001–0006 均不修改。完整新增清单由 revisions/0007/record.json 的 changes.added 给出；modified/deleted 为空。',
        '', 'STATIC_HOLD 不主动改变拓扑，继续自然失效和固定 T 服务，不能称为严格固定 K。',
        '', '反应规则比较当前无路由队列/注入需求的可达性改善；队列 bit、当前 bit/s 分列降序，相同改善优先可用 REPLACE，再 ADD，真实有空闲资源时 MBB 优先 BBM，最后 N2 action_key 字典序。不会破坏已经可达的当前需求作为规则偏好；这不是全网连通物理掩码。无当前 Q/I/注入时按字典序 DROP；其他情况 HOLD。无低利用阈值或科学经济权重。当前无需求不意味着未来无业务，因此该 DROP 规则可能影响不可见的未来业务。',
        '', '策略仅接收不可变当前观察和 N2 合法保留候选，不接收 trace 对象、未来业务、T 或最终指标。不同未来 trace 但相同当前状态的选择一致测试通过。初态/trace/几何/T/容量/服务内核/epoch/setup 的配对身份完全相同。TEST_ONLY epoch 每次一个原子动作，正式最大并行动作数未冻结。候选全部经 N2 原有物理验证和 Gate B 双端事务，未建立第二套执行器。',
        '', '## 配对工程指标','',
        '表中时间为秒、E/DeltaE 为 J，J_T/M_D 为 bit·s；null 表示没有交付。全部参数仅为工程 fixture。完整 K(t)、逐 epoch 观察、候选掩码、合法/保留/截断计数、选择原因、实际回执/释放、终端事件与前后状态哈希在对应 engineering_examples.json / paired_metrics.json。','',
        '|场景 / 控制器|E_LCT|DeltaE|R_del|J_T|N(T)|已交付平均时延|非 HOLD 接受数|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    fmt=lambda x:'null' if x is None else format(x,'.15g')
    for scenario,pair in pairs.items():
        for name,value in pair.items():
            m=value['metrics']
            lines.append('|'+scenario+' / '+name+'|'+'|'.join(fmt(m[k]) for k in
                ('E_LCT_J','DeltaE_LCT_J','R_del_T','J_T_bit_s','N_T_bits','mean_delivered_fluid_delay_s'))+
                '|'+str(value['non_HOLD_accepted_count'])+'|')
    lines+=['','## 160 星自然 SGP4 多 epoch','',
        '冻结 synthetic TLE 使用真实 SGP4 传播、真实距离/c 传播延迟、球体 LOS 和双端 RTN FoR；这是冻结合成星座输入的自然传播，不宣称真实运营卫星或硬件校准。160 星固定边与双动态终端完整保留。',
        '', '运行 catalog 范围：'+real['catalog_scope']+'；已登记总窗口 '+str(real['registered_catalog_rows'])+' 条。完整 catalog 诊断独立执行，下节给出其覆盖与边界。',
        '', 'TEST_ONLY：T=4，注入 [0,1]，1 bit/s，容量 10 bit/s，setup=(0.2,0.2,0.2) s；epoch=(0,0.2,0.4,1.25,2,3)。这些数值没有写入正式科学默认配置。']
    for name,r in real['paired_results'].items():
        sequence=', '.join(str(a['time_s'])+'s '+a['selected_action']['kind'] for a in r['decision_audit'])
        lines+=['',name+'：'+sequence+'。']
    d=real['paired_results']['REACTIVE_DYNAMIC_K'];age=d['n2_result']['n1b_result']['age_accounting']
    lines+=['','真实反应策略非 HOLD 接受 '+str(d['non_HOLD_accepted_count'])+' 次，确实演示动态 K；setup 期间不增加 K，真实 LINK_UP 才增加，DROP 使 DRAINING 退出主 K，释放后 IDLE 按 5 W 继续计费到 T。',
        '', '160 星已交付平均时延误差界：'+fmt(d['metrics']['mean_delay_absolute_error_bound_s'])+' s；年龄状态：'+str(age.get('measurement_status',age.get('precision_status','参见 age_accounting')))+'。沿用 N1b 有条件 IEEE 数值闭合界，不把该例称为解析精确。',
        '', '## 全登记 catalog 诊断','',
        '完整 '+str(coverage['registered_rows'])+' 条记录各有窗口哈希与只读 ADD 物理探测，遗漏 '+str(coverage['omitted_registered_rows'])+' 条；t=0 完整 CandidateSource 考虑 '+str(coverage['current_t0_windows'])+' 个当前 ADD 窗口，未来开始窗口在各自左端点探测。没有保留预算截断。该完整物理诊断在 attempt01 实际执行并单项通过；后续验收绑定其独立原始 SHA-256，重新验证所有窗口映射与原输入/源码快照，不重复该未受接口格式修正影响的诊断。不将证据复核宣称为再次运行完整物理扫描。',
        '', 't=0 各动作计数：`'+json.dumps(coverage['t0_diagnostics'],ensure_ascii=False,sort_keys=True)+'`。',
        '', '有真实初始连接的完整当前 catalog DROP/REPLACE 诊断：`'+json.dumps(coverage['occupied_current_catalog_diagnostics'],ensure_ascii=False,sort_keys=True)+'`。',
        '', '全部记录原因计数：`'+json.dumps(coverage['all_record_reason_counts'],ensure_ascii=False,sort_keys=True)+'`。',
        '', '范围仅为已登记的 160 星 catalog 及受控探测时刻，不证明所有连续时刻、未登记终端对、全部旧连接释放子集、完整卫星可见性全空间或硬件物理模型。沿用数值窗口/删失语义和 N2 当前/ready 几何检查。预算被截断与物理无候选分开审计。',
        '', '## 解析验算与测试','',
        '20 项 N3 专项通过：HOLD 自然失效、配对多 epoch、K=0 ADD、真实 setup、DROP DRAINING 与能耗下降、BBM/MBB、分区 Q/I 恢复、不可达残余、连续部分交付、本地 FIFO、输入公平性、当前信息隔离、预算诊断、确定性排序、固定时域尾段、完整结果校验、checkpoint/restore/replay、完整 catalog 与 160 星运行。',
        '', '解析 K=0 fixture：STATIC_HOLD 在 T=4 时 E=1600×4=6400，D=0、N=10、J_T=35，平均时延 null。反应策略 t=0 ADD、t=1 ACTIVE、t=3 DROP：DeltaE=2×(40−5)×1+2×(45−5)×2=230，E=6630；交付 10 bit，M_D=J_T=17.5，平均时延 1.75。',
        '', '无需求释放 fixture：两个终端 DRAINING 0–2，DeltaE=2×(45−5)×2=160，E=6560；同初态 HOLD E=6720。部分交付 fixture T=2.25：D=5、N=5、M_D=9.375、平均 1.875、J_T=16.875；其余截止年龄为 7.5，不把未交付部分计入平均。',
        '', 'N1a 25/25、N1b 24/24、N2 27/27 原测试原预期通过。同真实动作下 N1a/N1b 完整结果精确一致。历史基础回归 96/97（保留已知旧 F3 失败，名称及 traceback 与 0006 完全一致）；另 35/35 Gate C 通过，新增回归 0。独立版本保护 22/22 通过，包含篡改、读失败、漏文件、并发变化、原始换行、增删改名和历史资产保护。',
        '', '首轮候选实现的测试错误/失败与源码字节快照保留在 attempt01，不删除失败证据；最新验收证据目录为 '+args.attempt+'。其中 N3 接收成功回执 reason=null 的格式处理错误已修正；分区 fixture 选用显式容量以确保自然断路时 Q 与 I 同时为正。所有修正仅限本轮新增 N3 文件，未修改历史测试预期或生产内核。',
        '', '## 封存、边界及 N4 条件','',
        '独立起点 ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691 与父修订 0006 的 417e46baf6d3d7c8846af61131952739275c9b22bd1d468cc28e649b3c82dd18 开始前完整验证通过，登记文件 5906、排除 202、未登记差异为空。封存工具重新核对全部原始字节和文件集合，要求旧/已有版本资产修改、删除、改名全为空，只允许新增版本命名空间文件，并绑定新合同、配置、实现、验收、catalog、报告和父记录。',
        '', 'preseal_change_audit.json 记录封存前完整校验；0007 记录绑定报告，因此本报告不自引用修订哈希，也不在封存后重写。最新 SHA-256 和封存后独立信任锚完整验证结果在本轮最终回复给出；该最后验证失败必须 STOP，不能绕过。',
        '', 'T_A、T、tau_res、R_min、alpha、D_ref、E_ref、正式决策周期、搜索预算及最终并行动作上限保持 null。没有固定 K 或 Kmax、最低交付率硬掩码、STRICT_CONNECTED/BOUNDED_OUTAGE 默认拒绝。未实现 RL、MADRL/MAPPO/GNN/PPO 或联合动作、超参搜索、论文主性能矩阵。',
        '', '已具备进入 N4 问题定义的工程接口条件；需先审核 N3 并另行授权，明确观测、动作、奖励、约束和未决科学参数。旧 F3 catalog 覆盖失败仍保留，N3 登记 catalog 工程诊断不能替代其历史验收或科学 Gate。完成 N3 后停止等待审核。','']
    with (A/'RESULT_CN.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print(json.dumps(dict(report=str(A/'RESULT_CN.md'),paired_scenarios=len(pairs)),ensure_ascii=True))
if __name__=='__main__':main()
