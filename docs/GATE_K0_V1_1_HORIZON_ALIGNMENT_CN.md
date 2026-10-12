# Gate K0-v1.1 时间窗口对齐与合同修订草案

**DRAFT_NOT_FROZEN。仅完成合同修订和输入覆盖检查，等待人工批准。**

原 K0-v1 合同及 FAIL attempt 原样保留。原合同 canonical SHA-256：`27aedae08055cc89e083f5856d85edcf4ecafb12a7e9e1ac7b5ba89456a10225`。本次目录：`outputs/gate_k0_v1_1_revision_20261008T100242_809128Z`。本次草案指纹：`8c75083fbb09a0782023787a12a944a87b381cfaed92109ff0ab924bd569451f`；指纹只用于识别草案，不表示冻结。

## 时间与物理输入

建议审计点改为 0,30,…,570 s，共 20 点。删除的是新版本审计 schedule 的 t=600 采样要求，未删除任何历史物理记录。20 点是结构采样，不覆盖全部 2 s controller epochs，也不能证明采样间全部拓扑持续可行。

原 Gate C 终端对窗口仍为 0–600 s，包含 2742 条记录，其中 1992 条右删失。160 星的 ID/plane mapping、parent visibility interval、单位/frame/epoch 和冻结输入 hash 均纳入覆盖检查。最后审计点 570 s：双端空闲的冻结 fixture retarget=(1,1) s、acquisition=1 s，因此 ready=572 s，小于观察截止 600 s。各点候选及自然短窗口拒绝数见 coverage_preflight.json；保留所有自然不可行窗口，没有人为删除它们。

Gate C 使用 `start <= t < end`，Gate B 检查 `ready < end`，Gate C 进一步使用原 `1e-9 s` lifetime epsilon。覆盖检查只证明这些判断可以依据已有资产实施，不保证每个候选合法，也不保证任何 K 有足够 matching capacity。沿用原资产的数值扫描/边界精度，不新增连续完整性或硬件能力证明；5000 km 仍是 diagnostic cutoff。

## 截断 usable lifetime

`L_usable_within_horizon = max(0, min(t_physical_end,600) - t_ready)`。

自然窗口结束已知时，t_physical_end 使用原记录的真实 end。窗口右删失时，t_physical_end 保持未知/null，指标仅用 600 s 观察上限计算，并保留 RIGHT_CENSORED_AT_600。数字 end=600 本身不决定删失，必须读取 right_censored 标志。此指标不是完整 physical lifetime；不同未知自然寿命可能在截断后相同。

ready 必须取现有 Gate C `connect_command` 对实际 Gate B 状态试执行输出的 predicted_ready。其物理关系为 `max(free_i+ret_i,free_j+ret_j)+acq`；occupied-terminal BBM 会考虑旧 TX/draining，genuine MBB 使用真实空闲端口及 release-after plan。同 peer 换终端等依赖继续由 Gate B 判定，KEEP 不产生新 setup。不能把全部 REPLACE 都简化为 t+2。

若 drain 导致 ready 达到/超出右删失 end=600，原 Gate C 拒绝其在已观察窗口内建成；报告为 bounded audit 内不可认证，不声称其在真实 600 s 之后物理不可能。合法性先独立检查；max(0,…) 的指标截断不能掩盖 ready>=end 的非法动作。

Builder 修改清单见 lifetime_contract_comparison.json：第三、第四优先级分别改为最大化总/最小 L_usable_within_horizon；第一、第二和第五优先级保持不变。matching 输入和 REPLACE legality 保持 Gate B/C 判定；selected Z_K 与 replacement targets 的 min/P10/median/P90/max、<=setup/10/20 s 比例改为明确的截断指标，阈值值不变，并附 censor counts。20 点汇总中 median 取排序后中间两值均值。本轮没有执行 builder 或 inventory。

## 阈值迁移（等待批准）

| 条件 | 原分子/分母 | 原比例 | 建议分子/分母 | 建议比例 | 严格程度 |
|---|---:|---:|---:|---:|---|
| K0-A matching capacity | 21/21 | 100.000000% | 20/20 | 100.000000% | SAME_PROPORTION |
| K0-B all-plane participation | 21/21 | 100.000000% | 20/20 | 100.000000% | SAME_PROPORTION |
| K0-C connected and bridge_count < edge_count | 18/21 | 85.714286% | 18/20 | 90.000000% | STRICTER_PROPORTION |
| K0-D uncapped legal REPLACE >= 16 | 18/21 | 85.714286% | 18/20 | 90.000000% | STRICTER_PROPORTION |
| K0-E raw MBB >= 8 AND raw BBM >= 8 | 18/21 | 85.714286% | 18/20 | 90.000000% | STRICTER_PROPORTION |

18/21=85.714286%，18/20=90%，提高 4.285714 个百分点，比例门槛更严格；可失败点从 3 减为 2。采样域同时移除了原先无法认证的 t=600，因此不声称新旧 admissible sets 存在包含关系。21/21→20/20 仍要求全部采样点通过，比例均为 100%，时间覆盖域改变。

K0-E 的 median MBB fraction band 仍为 [0.10,0.90]，仅样本数从 21→20；K0-F 完整审计重放仍为 2 次，本次草案检查不是完整重放。K 候选、15%–50% occupancy band、raw legal REPLACE>=16、MBB/BBM>=8、最小 admissible K 选择规则全部继承。K=4 保留 VERY_SPARSE_HISTORICAL_REFERENCE，不参与 primary selection。

## 保护、范围与下一步

所有既有项目文件在独立 hash-only 通道记录前后 SHA-256，涵盖 A–E、Gate C 物理窗口、K0-v1/FAIL、F3-v1、历史 Z_MODERATE/Z_SPARSE/K4、B4 production overlay 和生产源码。性能内容不解析、不进入草案。仅运行新合同一致性测试（含少量 synthetic Gate B/C readiness 检查）；未运行完整 matching、Z_K construction、uncapped inventory、MBB/BBM 全量扫描、K* selection、controller 或性能实验。

若覆盖、合同测试、历史 hash 均通过，只记录 K0_V1_1_CONTRACT_REVISION_READY_FOR_HUMAN_REVIEW。它不等于 Gate K0 PASS 或 K* SELECTED。

现有物理资产足以支持这个有限窗口定义，无需重算或延长窗口；不改变原 traffic 0–240 s、最大 drain 600 s、2 s cadence、10 s rollout、600 s 不决策规则。下一步必须先人工冻结 v1.1 并授权完整 K0；exact matching 与 deterministic exact/controlled lexicographic solver 仍需实现和验收，不能把输入覆盖通过当成整个 K0 已可直接完成。完成本草案后 STOP，不进入 K1/P1/P2/RL。
