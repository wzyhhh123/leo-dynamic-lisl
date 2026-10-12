# N3 动态 K 业务感知闭环工程结果

N3 Engineering PASS。仅验证工程功能与机制，不构成科学 Gate PASS，不构成性能优越性、统计显著性或最优性结论。未运行正式主实验或训练。

## 实现与信息边界

新增 runtime/n3_baselines.py：CurrentObservation / observe_current、StaticHold、ReactiveDynamicK、ClosedLoopBaseline.step/run/clone/checkpoint/restore、paired_runs、validate_n3 和 N3EvidenceBinding。独立合同、配置、schema、专项测试、封存工具与证据均在 dynamic_k_v1 内。N1a/N1b/N2、冻结生产 src、旧测试/合同/manifest/输出和修订 0001–0006 均不修改。完整新增清单由 revisions/0007/record.json 的 changes.added 给出；modified/deleted 为空。

STATIC_HOLD 不主动改变拓扑，继续自然失效和固定 T 服务，不能称为严格固定 K。

反应规则比较当前无路由队列/注入需求的可达性改善；队列 bit、当前 bit/s 分列降序，相同改善优先可用 REPLACE，再 ADD，真实有空闲资源时 MBB 优先 BBM，最后 N2 action_key 字典序。不会破坏已经可达的当前需求作为规则偏好；这不是全网连通物理掩码。无当前 Q/I/注入时按字典序 DROP；其他情况 HOLD。无低利用阈值或科学经济权重。当前无需求不意味着未来无业务，因此该 DROP 规则可能影响不可见的未来业务。

策略仅接收不可变当前观察和 N2 合法保留候选，不接收 trace 对象、未来业务、T 或最终指标。不同未来 trace 但相同当前状态的选择一致测试通过。初态/trace/几何/T/容量/服务内核/epoch/setup 的配对身份完全相同。TEST_ONLY epoch 每次一个原子动作，正式最大并行动作数未冻结。候选全部经 N2 原有物理验证和 Gate B 双端事务，未建立第二套执行器。

## 配对工程指标

表中时间为秒、E/DeltaE 为 J，J_T/M_D 为 bit·s；null 表示没有交付。全部参数仅为工程 fixture。可读的配对 K/DRAINING/SETUP 时间表见 [K_TIMELINES_CN.md](K_TIMELINES_CN.md)。完整 K(t)、逐 epoch 观察、候选掩码、合法/保留/截断计数、选择原因、实际回执/释放、终端事件与前后状态哈希在 attempt02/engineering_examples.json / paired_metrics.json。表格显示值已四舍五入，原始值与精度状态保留在 JSON。

|场景 / 控制器|E_LCT|DeltaE|R_del|J_T|N(T)|已交付平均时延|非 HOLD 接受数|
|---|---:|---:|---:|---:|---:|---:|---:|
|paired_K0_ADD_delivery_idle_DROP / REACTIVE_DYNAMIC_K|6630|230|1|17.5|0|1.75|2|
|paired_K0_ADD_delivery_idle_DROP / STATIC_HOLD|6400|0|0|35|10|null|0|
|paired_REPLACE_MBB_spare_terminals / REACTIVE_DYNAMIC_K|8390|390|1|17.5|0|1.75|2|
|paired_REPLACE_MBB_spare_terminals / STATIC_HOLD|8400|400|0|45|10|null|0|
|paired_no_demand_DROP_draining_energy / REACTIVE_DYNAMIC_K|6560|160|1|0|0|null|1|
|paired_no_demand_DROP_draining_energy / STATIC_HOLD|6720|320|1|0|0|null|0|
|paired_resource_constrained_REPLACE_BBM / REACTIVE_DYNAMIC_K|8345|345|1|27.5|0|2.75|2|
|paired_resource_constrained_REPLACE_BBM / STATIC_HOLD|8400|400|0|45|10|null|0|
|real160_natural_SGP4 / REACTIVE_DYNAMIC_K|6496|96|1|0.0933196431133814|0|0.0933196431133814|2|
|real160_natural_SGP4 / STATIC_HOLD|6400|0|0|3.5|1|null|0|

## 160 星自然 SGP4 多 epoch

冻结 synthetic TLE 使用真实 SGP4 传播、真实距离/c 传播延迟、球体 LOS 和双端 RTN FoR；这是冻结合成星座输入的自然传播，不宣称真实运营卫星或硬件校准。160 星固定边与双动态终端完整保留。

运行 catalog 范围：THREE_EXPLICIT_TERMINAL_PAIRS_FROM_REGISTERED_160_SAT_CATALOG；已登记总窗口 2742 条，受控运行选用其中 3 条，其他 2739 条作为工程输入范围未用于闭环候选生成，这不是候选保留预算截断。各 epoch 都标明供应 catalog 的记录数及其物理输入哈希；其“物理无候选”状态仅指该输入范围。完整 catalog 诊断独立执行，下节给出其覆盖与边界。

TEST_ONLY：T=4，注入 [0,1]，1 bit/s，容量 10 bit/s，setup=(0.2,0.2,0.2) s；epoch=(0,0.2,0.4,1.25,2,3)。这些数值没有写入正式科学默认配置。

REACTIVE_DYNAMIC_K：0.0s ADD, 0.2s HOLD, 0.4s HOLD, 1.25s DROP, 2.0s HOLD, 3.0s HOLD。

STATIC_HOLD：0.0s HOLD, 0.2s HOLD, 0.4s HOLD, 1.25s HOLD, 2.0s HOLD, 3.0s HOLD。

真实反应策略非 HOLD 接受 2 次，确实演示动态 K；setup 期间不增加 K，真实 LINK_UP 才增加，DROP 使 DRAINING 退出主 K，释放后 IDLE 按 5 W 继续计费到 T。

160 星已交付平均时延误差界：1.79045674780626e-15 s；年龄状态：IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT。沿用 N1b 有条件 IEEE 数值闭合界，不把该例称为解析精确。原始 M_D=0.09331964311338135 bit·s，J_T=0.09331964311338137 bit·s。

|时段 / 时刻|STATIC_HOLD 的 K|REACTIVE 的 K|REACTIVE 的物理状态|
|---|---:|---:|---|
|0 至 0.4 s 前|0|0|两终端依次 RETARGETING/ACQUIRING|
|0.4 至 1.25 s 前|0|1|实际 LINK_UP 后 ACTIVE|
|1.25 至 T=4 s|0|0|实际 DROP/释放后 IDLE|

此例没有未完成的 Gate B TX，释放的 DRAINING 与 LINK_DOWN 同时发生，DRAINING 驻留为零，未人为延长或省略执行流程。另一个配对 fixture 专门验证两终端 DRAINING 0–2 s 的 45 W 计费。此例增量能耗为 2×(40−5)×0.4 + 2×(45−5)×(1.25−0.4)=96 J，总计 6496 J。

## 全登记 catalog 诊断

完整 2742 条记录各有窗口哈希与只读 ADD 物理探测，遗漏 0 条；t=0 完整 CandidateSource 考虑 1996 个当前 ADD 窗口，未来开始窗口在各自左端点探测。没有保留预算截断。该完整物理诊断在 attempt01 实际执行并单项通过；后续验收绑定其独立原始 SHA-256，重新验证所有窗口映射与原输入/源码快照，不重复该未受接口格式修正影响的诊断。不将证据复核宣称为再次运行完整物理扫描。

t=0 各动作计数：`{"ADD": {"budget": null, "considered": 1996, "legal": 1996, "retained": 1996, "status": "RETAINED", "truncated": 0}, "DROP": {"budget": null, "considered": 0, "legal": 0, "retained": 0, "status": "NO_LEGAL_PHYSICAL_ACTION", "truncated": 0}, "HOLD": {"budget": null, "considered": 1, "legal": 1, "retained": 1, "status": "RETAINED", "truncated": 0}, "REPLACE": {"budget": null, "considered": 0, "legal": 0, "retained": 0, "status": "NO_LEGAL_PHYSICAL_ACTION", "truncated": 0}}`。

有真实初始连接的完整当前 catalog DROP/REPLACE 诊断：`{"ADD": {"budget": null, "considered": 1996, "legal": 1965, "retained": 1965, "status": "RETAINED", "truncated": 0}, "DROP": {"budget": null, "considered": 1, "legal": 1, "retained": 1, "status": "RETAINED", "truncated": 0}, "HOLD": {"budget": null, "considered": 1, "legal": 1, "retained": 1, "status": "RETAINED", "truncated": 0}, "REPLACE": {"budget": null, "considered": 3961, "legal": 3960, "retained": 3960, "status": "RETAINED", "truncated": 0}}`。

全部记录原因计数：`{"ACCEPTED": 2424, "FOR_FAIL_LOCAL": 140, "FOR_FAIL_REMOTE": 178}`。

补充只读诊断 [catalog_boundary_audit.json](catalog_boundary_audit.json) 已逐一复现 318 个 FoR 左边界拒绝：采样角度超过 90° 的最大值为 8.97746649286546e-05°；全部向窗口内推进最多 0.001 s 后，当前 FoR 检查通过。这解释数值求根边界与严格实时掩码的差异，不声称推进后 ADD 的全部条件自动满足，也不证明连续窗口全域。没有修改 N2 角度容差或将拒绝改成接受。

完整占用 catalog 的 3961 个 REPLACE 中，唯一不合法的候选是替换到同一条已经存在的绑定；[occupied_catalog_rejection_detail.json](occupied_catalog_rejection_detail.json) 用相同绑定复现 DUPLICATE_LINK，拒绝前后状态哈希一致。DROP 的唯一候选合法；其余 3960 个 REPLACE 在原完整诊断中合法。

范围仅为已登记的 160 星 catalog 及受控探测时刻，不证明所有连续时刻、未登记终端对、全部旧连接释放子集、完整卫星可见性全空间或硬件物理模型。沿用数值窗口/删失语义和 N2 当前/ready 几何检查。预算被截断与物理无候选分开审计。

## 解析验算与测试

20 项 N3 专项通过：HOLD 自然失效、配对多 epoch、K=0 ADD、真实 setup、DROP DRAINING 与能耗下降、BBM/MBB、分区 Q/I 恢复、不可达残余、连续部分交付、本地 FIFO、输入公平性、当前信息隔离、预算诊断、确定性排序、固定时域尾段、完整结果校验、checkpoint/restore/replay、完整 catalog 与 160 星运行。

解析 K=0 fixture：STATIC_HOLD 在 T=4 时 E=1600×4=6400，D=0、N=10、J_T=35，平均时延 null。反应策略 t=0 ADD、t=1 ACTIVE、t=3 DROP：DeltaE=2×(40−5)×1+2×(45−5)×2=230，E=6630；交付 10 bit，M_D=J_T=17.5，平均时延 1.75。

无需求释放 fixture：两个终端 DRAINING 0–2，DeltaE=2×(45−5)×2=160，E=6560；同初态 HOLD E=6720。部分交付 fixture T=2.25：D=5、N=5、M_D=9.375、平均 1.875、J_T=16.875；其余截止年龄为 7.5，不把未交付部分计入平均。

N1a 25/25、N1b 24/24、N2 27/27 原测试原预期通过。同真实动作下 N1a/N1b 完整结果精确一致。历史基础回归 96/97（保留已知旧 F3 失败，名称及 traceback 与 0006 完全一致）；另 35/35 Gate C 通过，新增回归 0。独立版本保护 22/22 通过，包含篡改、读失败、漏文件、并发变化、原始换行、增删改名和历史资产保护。

首轮候选实现的测试错误/失败与源码字节快照保留在 attempt01，不删除失败证据；最新验收证据目录为 attempt02。其中 N3 接收成功回执 reason=null 的格式处理错误已修正；分区 fixture 选用显式容量以确保自然断路时 Q 与 I 同时为正。所有修正仅限本轮新增 N3 文件，未修改历史测试预期或生产内核。

报告辅助脚本直接启动时出现 Python CLI 编码识别错误；文件原始 SHA-256 与实现绑定完全一致，严格 UTF-8 解码、AST 和显式编译均通过。execute_utf8_bound_helper.py 先完整验证已固定的实现 manifest，再执行原始 UTF-8 辅助源码，未修改已验收文件或降低保护。详见 [HELPER_EXECUTION_NOTE_CN.md](HELPER_EXECUTION_NOTE_CN.md)。

## 封存、边界及 N4 条件

独立起点 ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691 与父修订 0006 的 417e46baf6d3d7c8846af61131952739275c9b22bd1d468cc28e649b3c82dd18 开始前完整验证通过，登记文件 5906、排除 202、未登记差异为空。封存工具重新核对全部原始字节和文件集合，要求旧/已有版本资产修改、删除、改名全为空，只允许新增版本命名空间文件，并绑定新合同、配置、实现、验收、catalog、报告和父记录。

preseal_change_audit.json 记录封存前完整校验；0007 记录绑定报告，因此本报告不自引用修订哈希，也不在封存后重写。最新 SHA-256 和封存后独立信任锚完整验证结果在本轮最终回复给出；该最后验证失败必须 STOP，不能绕过。

T_A、T、tau_res、R_min、alpha、D_ref、E_ref、正式决策周期、搜索预算及最终并行动作上限保持 null。没有固定 K 或 Kmax、最低交付率硬掩码、STRICT_CONNECTED/BOUNDED_OUTAGE 默认拒绝。未实现 RL、MADRL/MAPPO/GNN/PPO 或联合动作、超参搜索、论文主性能矩阵。

已具备进入 N4 问题定义的工程接口条件；需先审核 N3 并另行授权，明确观测、动作、奖励、约束和未决科学参数。旧 F3 catalog 覆盖失败仍保留，N3 登记 catalog 工程诊断不能替代其历史验收或科学 Gate。完成 N3 后停止等待审核。
