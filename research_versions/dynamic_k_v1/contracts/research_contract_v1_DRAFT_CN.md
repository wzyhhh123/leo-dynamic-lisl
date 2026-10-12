# Dynamic LISL 动态 K 研究合同 v1 草案

状态：DRAFT_NOT_FROZEN。N0c 已封存在修订 0003；本轮授权 N1a 固定时域与能耗的工程实现和验收，追加修订 0004。N0a/N0b、0001–0003 保持不变。
本轮仅运行解析单元/集成测试和适用历史回归；不授权生产控制器、训练、主性能实验或旧 F3 主实验恢复。

## 版本与历史边界

版本 ID 为 `dynamic_k_v1`。`version_record.json` 绑定独立的旧文件基线 seal、首份修订记录和本合同/配置的原始字节哈希。
旧 Gate A–F3、K0、PASS/FAIL attempts、旧状态入口与冻结合同原样保留。
10 月 9 日草案中的持续全网连通和每星动态 LCT 能量硬预算不作为本版本默认约束。
旧完整 K* 选择和 42-run 矩阵不作为新方向前置条件。
哈希封存不证明 Gate 通过，也不代替可恢复备份；现存原始研究文件必须保留。

## 已确定研究语义

- 场景：160 星、4 轨道面、每面 40 星；每星 2 个固定同轨终端、2 个动态终端。
- 动态终端总数 320；双端独占给出同时活动链数的资源理论上界 160，不另设人为 Kmax。
- 主指标 K(t)=|E_dyn_active_admissible(t)|：统计真实处于 ACTIVE 且当前允许接纳新业务的动态连接实例。每条双端连接只计一次，不按两个方向或两个端点重复计数；是否恰好有待发业务不改变 K。
- DRAINING 连接不接纳新业务，排除在主 K 之外，以 K_draining(t) 单独记录；已有传输/传播及释放过程仍遵循真实执行模型。不得直接用旧 G_active 的边数替代新的主指标。
- SETUP 资源单独记录：N_setup_terminals(t) 为 RETARGETING 与 ACQUIRING 动态终端数之和；分别记录这两个状态的终端数、实际 SETUP 中的待活动连接实例数，以及为待活动连接预约的不同动态终端数。预约数可能与状态占用数重叠，不相加推算总占用；这些资源不计入主 K。
- 概念动作 HOLD/ADD/DROP/REPLACE 均须经过真实物理执行、双端预约和终端状态时间线；REPLACE 保留真实 BBM/MBB。
- 允许临时网络分区；无路由业务保留在持久队列，路径恢复后继续服务；拓扑变化不得伪造交付或丢弃业务。
- 所有算法绑定共同仿真起点、业务轨迹、T_A/T、轨道/窗口、初始网络和终端状态；评价统一截止到 T。
- 即使业务提前排空，终端状态与能耗仍统计到 T；不设置单包严格交付截止时间。
- 复用聚合 fluid bit 业务、容量、传播与守恒模型；不得把 bit 加权平均直接宣传为 packet 平均。

## 评价与目标

N(t)=sum_f(A_f(t)-D_f(t))，包含 queue 和 in-flight；J_T=integral_0^T N(t)dt。
记录 R_del(T)、已交付业务平均端到端时延、N(T)、J_T 和 E_LCT。
J_T^+=J_T+tau_res*N(T) 为待冻结目标形式；R_del(T)>=R_min 为终点评价要求，不能宣称仅由在线动作掩码保证。
拟议 F_alpha=alpha*J_T^+/(B_total*D_ref)+(1-alpha)*E_LCT/E_ref；alpha、归一化尺度和残余系数均未冻结。
部分交付时 J_T/B_total 不能替代完整平均时延；须在 N1b 新增已交付 fluid 业务年龄统计，不在 N0c 或 N1a 实施。
评价正常到 T、业务是否排空、执行失败须分别表述。

## 统一 [0,T] 计费与初始状态

全部 320 个动态终端均在共同 [0,T] 内按实际状态计费，包括无业务时的待机和提前全部交付后的驻留时间。
以实际输入给出的 t=0 状态及剩余阶段时间作为起点：预先 ACTIVE 的终端从 ACTIVE 开始计费，正在 RETARGETING/ACQUIRING/DRAINING 的终端沿其真实事件继续，IDLE 终端按 IDLE 计费。
不因初始化而虚构 t=0 的 ADD/建链动作，不把既有 ACTIVE 连接重新执行一次 setup；真实发生在 t=0 的动作仍须有真实执行事件证据。
t<0 的预建立/setup 能耗不并入本窗口 E_LCT；若以后研究预建立成本，应另行授权、另列窗口外指标，不回填为虚构的 t=0 动作。
将真实状态区间裁剪到 [0,T]。相邻事件采用半开区间 [t_j,t_(j+1))，事件后的状态用于右侧区间；t=0/T 单点无驻留时长，不重复收费，也不计入 T 之后的能耗。
四状态能耗驻留时间中的 ACTIVE 包含执行态 ACTIVE 与 DRAINING 的时间；另保留五执行态驻留时间以区分 DRAINING，不再对它附加第二份能耗。
正常完成且终端时间线完整时，每个动态终端驻留时间总计 T，全网总计 320T。状态缺失、时间线缺口或提前停止不得补造完整驻留时间或宣称正常完成。
时间比较/积分容差尚未确定，保持 null，不在本轮指定数值。

## 结果 schema 草案与未执行模板

`schemas/research_result_v1_DRAFT.schema.json` 定义字段形状，`schemas/research_result_v1_DRAFT.template.json` 为未执行模板，均不是运行结果或 Gate 证据。
预留实际时刻的主 K、K_draining、SETUP 连接/状态终端/预约终端时间序列；采样周期不冻结，不得用旧名义 K 回填。
预留四能耗态及五执行态累计驻留时间、E_LCT/DeltaE、评价是否正常完成、终端计费是否覆盖到 T、业务是否全部交付以及终止原因。
评价正常完成与业务全部交付为独立结果：正常到 T 时可仍有积压，业务提前排空也不意味着已评价到 T。未执行时这些结果字段为 null，不伪造 false/0 作为测量值。
业务是否全部交付依据同一业务范围的守恒、交付量及 queue/in-flight 剩余量核对；数值容差仍未决。字段类型符合 schema 不证明上述数值关系成立。
schema 同时预留已交付 fluid bit 总量、已交付 bit 的年龄加权累计量及其平均时延；N1a 不填造这些尚未实现的年龄追踪结果。

## N1a / N1b 边界

N1a 已获本轮授权，通过独立评价层实现固定时域推进与真实终端状态的能耗/驻留核算，包括提前排空后持续计费；不实现已交付 fluid 业务年龄搬运、奖励、控制算法或主实验。
N1b 才在后续授权后实现已交付 fluid 业务年龄追踪：业务年龄在排队、传输及传播过程中保留，交付时按已交付 bit 加权，平均值在已交付量为正时由年龄加权累计量除以已交付量得到；无交付时为 null，不冒称 packet 平均。
具体年龄搬运数据结构与数值实现尚未确定，不在 N0c 选择或实现。N1a 工程验收由 acceptance/0004 独立证据说明；不宣称 N1b、N2 或任何科学 Gate 通过。

## Liu-anchored parameterized four-state LCT power profile v1

| 能耗状态 | 每动态终端功率 |
|---|---:|
| IDLE | 5 W |
| RETARGETING | 40 W |
| ACQUIRING | 40 W |
| ACTIVE | 45 W |
| DRAINING | 映射 ACTIVE，45 W |

来源：Liu et al., JOCN 2024，DOI 10.1364/JOCN.527910；Table 3 的 PAT 40 W 与激光源 5 W 为参考。
IDLE 5 W、PAT 的重指向/捕获阶段映射，以及 ACTIVE 45 W 的组合均是本研究建模约定，不是四状态单端硬件实测数据。
粗/精指向已包含在 PAT 总口径内；不重复加 Payload/Processor、整星基础功耗。
Gate B 的 DRAINING 执行语义保持不变，仅在能耗层映射。
E_LCT=sum_ik integral_0^T P(s_ik(t))dt，覆盖全部 320 个动态终端；MBB 同时占用的不同终端分别计费，不再按整条链路重复收费。
驻留时间总计应为 320T；在一致待机基线前提下保留 DeltaE=E_LCT-320*T*P_idle。
本版本不建模太阳能、电池 SOC/DOD 或整星能源预算。

## 未决参数与后续门槛

T_A、T、tau_res、R_min、alpha、D_ref、E_ref 均为 UNRESOLVED；不继承历史 240/600 s。
窗口外预建立/setup 成本另列、不并入 [0,T]；主 K 排除 DRAINING，其数量与 SETUP 资源单列。已交付 fluid 年龄搬运的具体数值实现仍未决。
决策周期、并行动作规模、候选预算、基线参数及求解算法均未定。
Graph-MAPPO 仅为候选；N0 不实施 MADRL/MAPPO/GNN、奖励或训练框架。
后续顺序 N1a 固定时域/能耗 → N1b 已交付 fluid 年龄 → N2 动态动作 → N3 分区回归/非学习基线 → N4 RL 问题定义 → N5 获选算法/注册实验。各阶段须独立授权与验收。

## 修订 0004：N1a 独立工程实现

接口位于 runtime/n1a.py：TerminalEnergyLedger.capture/metrics、FixedHorizonEvaluator.advance_to/run/clone/checkpoint/restore、validate_measurement。计费读取 Gate B 完整状态事件日志；D2 advance_to 推进真实业务、传播及终端事件。不修改 Gate B/D2 生产代码。

J_T 按未加权的总未交付业务量在实际业务事件区间积分，不能直接使用历史 commodity.weight 加权目标。测量输出前执行数值范围、驻留总量、能耗公式、业务守恒、完成标志及拓扑时间积分的交叉校验。

工程结果独立使用 schemas/n1a_engineering_result_v1.schema.json，保留 N0c 研究 schema 草案和未执行模板。工程有限 T 与时间/能量/业务容差由调用者显式传入并记录，正式科学参数与其容差仍为 null，不继承 240/600。R_del 在零输入时约定为 1（空集合全部交付），不产生时延样本。

测试前绑定版本起点、基线 seal、父修订 0003，以及候选 0004 的实现/合同/配置清单；结果随后作为 0004 的证据封存。候选清单不将尚未生成的修订记录自身纳入，避免循环哈希。正式实验仍被禁用。年龄加权累计和已交付 fluid 平均时延均为 null，N1b 未实现。
