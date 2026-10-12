# Dynamic LISL 动态 K 研究合同 v1 草案

状态：DRAFT_NOT_FROZEN。当前授权仅覆盖 N0a 文件基线与 N0b 版本骨架。
本合同不授权生产控制器修改、仿真、训练、性能实验或旧 F3 实验恢复。

## 版本与历史边界

版本 ID 为 `dynamic_k_v1`。`version_record.json` 绑定独立的旧文件基线 seal、首份修订记录和本合同/配置的原始字节哈希。
旧 Gate A–F3、K0、PASS/FAIL attempts、旧状态入口与冻结合同原样保留。
10 月 9 日草案中的持续全网连通和每星动态 LCT 能量硬预算不作为本版本默认约束。
旧完整 K* 选择和 42-run 矩阵不作为新方向前置条件。
哈希封存不证明 Gate 通过，也不代替可恢复备份；现存原始研究文件必须保留。

## 已确定研究语义

- 场景：160 星、4 轨道面、每面 40 星；每星 2 个固定同轨终端、2 个动态终端。
- 动态终端总数 320；双端独占给出同时活动链数的资源理论上界 160，不另设人为 Kmax。
- K(t)=|E_dyn_active(t)|，由策略和物理资源决定；DRAINING 与旧 G_active 的统计定义须在 N1/N2 接口合同中另行明确。
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
部分交付时 J_T/B_total 不能替代完整平均时延；须新增业务年龄统计，不在 N0 实施。
评价正常到 T、业务是否排空、执行失败须分别表述。

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
起点前预建立/setup 能耗处理、K 的 DRAINING 口径、已交付时延的权重与年龄搬运规则尚待冻结。
决策周期、并行动作规模、候选预算、基线参数及求解算法均未定。
Graph-MAPPO 仅为候选；N0 不实施 MADRL/MAPPO/GNN、奖励或训练框架。
后续顺序 N1 能耗/固定时域 → N2 动态动作 → N3 分区回归/非学习基线 → N4 RL 问题定义 → N5 获选算法/注册实验。
