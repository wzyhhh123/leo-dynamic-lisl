# Gate F3-0.1：Production Candidate Source 与 Drain Decision Human Freeze v1

## 范围与父合同

本文件是 Gate F3-0 的增量 overlay，只解决 P1 执行接口中尚未冻结的生产候选源与 drain 期决策边界。父 F3 canonical SHA-256 为 `118d3a61175b08b6ba53f4d92504b52ab879659682799d26c1965baf7bb600a6`，execution manifest canonical SHA-256 为 `0222d30e69ec9f565e1d55d5e74391934d63d7357cc7f1d652532f6a30ac945a`。

本 Gate 不执行任何注册 P1 run，不产生 controller performance observation，不修改 F3-0 manifests、B0/B1/B3/B4、Gate B/C/D 或历史 P1 blocked evidence。

## 生产候选源

生产候选源冻结为 `DETERMINISTIC_ONE_FOR_ONE_PHYSICAL_REPLACEMENT_V1`。一个动作只允许把一条现存 ACTIVE dynamic physical binding 替换为一个 concrete terminal pair，不允许主动拆除两条旧动态链。

相同 canonical current state、决策时刻、topology regime 与 Gate C catalog 必须生成逐字节一致的有序候选 identity。候选源不得读取 controller identity、queue/load、`V_v2`、B4 `J_H`、未来真实业务、最终 J 或性能标签。允许读取当前 terminal/link/reservation 状态、当前 Gate C window、绝对时间、window end、plane gap、冻结 setup 参数和 regime safety metadata。

## OLD(t)

`OLD(t)` 只包含右连续决策状态中实际存在、ACTIVE、非 DRAINING、未被 `release_after` owner 锁定、端点不存在不兼容 reservation、且未到期的 dynamic physical links。按 canonical terminal-pair key 排序。自然到期链路不生成 synthetic old binding。

## Target 与冲突

raw target 只来自既有冻结 Gate C terminal-pair interval catalog 中当前窗口包含 `t` 的记录；不重新执行 satellite all-pairs geometry search，也不合成 catalog 外链路。

对每个 `b_old`，若新端点被 `b_old` 之外的 dynamic link 占用，或属于不兼容 reservation，则拒绝，理由为 `MULTI_OLD_BINDING_CONFLICT` 或 `RESERVED_TERMINAL_CONFLICT`。精确当前 binding 拒绝为 `NO_OP_CURRENT_BINDING`。已经存在相同物理链、或会形成同时存在的同 satellite-pair parallel dynamic link，拒绝为 `PARALLEL_SATELLITE_PAIR_CONFLICT`。

## BBM_RAW 与 MBB_RAW

`BBM_RAW` 要求新 pair 不等于旧 pair、复用旧 binding 至少一个 terminal，其余新端点真实 IDLE 且未预约，并且不触碰第二条旧 binding。其 `old_physical_binding=b_old`，`release_after=()`。该标签只是 source structural stratum，真实 BBM 仍由 Gate B 决定。

`MBB_RAW` 要求两个新 terminal 均真实 IDLE、未预约、不触碰任何当前 binding，`b_old` 可延迟释放，且 target satellite pair 不会形成 parallel physical satellite link。其 `old_physical_binding=b_old`，`release_after=(b_old,)`。Gate B 必须先 LINK_UP，再释放旧 binding；source 不替 Gate B 宣称真实 MBB 已完成。

setup 期间不得取消或抢占现有 target。与所有 reservation 完全不相交的新候选仍可产生，不因无关 setup 全局强制 HOLD。

## 有界 materialization 与 identity

进入既有 `FrozenTerminalPairProposer` 前，raw caps 冻结为：

- `BBM_RAW <= 32`；
- `MBB_RAW <= 32`；
- raw total `<=64`。

32 等于冻结下游每层 quota 8 的四倍，是结果盲工程预算，不从性能调参，F3-v1 性能开始后不得修改。

两个 raw stratum 分别按以下顺序排序：remaining lifetime 降序、plane gap 升序、canonical old binding 升序、canonical new terminal pair 升序。随后各取前 32；不足则全保留。不得用 traffic、queue、utilization、`V_v2` 或 rollout `J_H` 排序。

action identity 为 `(decision_time_s, canonical_state_sha256, canonical_old_binding, canonical_new_terminal_pair, canonical_release_after)`。ID 为 canonical JSON 的 SHA-256 派生值。完全重复 identity 合并；同一 target 搭配不同 old binding 是不同动作。

bounded materializer 后仍调用原 `FrozenTerminalPairProposer`。Gate C legality、setup/window、terminal conflict、regime safety、8/8 quota、spillover、top-K=16 与最终排序均保持原语义；本 overlay 不建立第二套 final proposer。

## Setup 参数来源

唯一生产来源冻结为 `configs/hardware_gate_c_simplified_v1.json::audit_setup_fixture`：双端 retarget 分别 1 s，acquisition 1 s，ready offset 为 `max(1,1)+1=2 s`。该值沿用 Gate C/E2 synthetic sensitivity fixture，不是商业硬件标定值。

## Drain 决策

controller 在 drain 期间继续运行。arrival horizon 为 240 s，absolute drain limit 为 600 s，cadence 为 2 s。

在 240 s，先使用右连续 `lambda_f(240)=0`，结算既有同时间物理/服务事件；若 unfinished work 仍超过冻结零阈值，再执行正常 periodic decision。之后在 backlog 存在时继续 242、244、…、598 s 决策。600 s 不产生新决策。

若系统在两个 periodic epoch 之间排空，在物理/服务结算后立即 COMPLETE，不等待下一 epoch。相同规则适用于 B0/B1/B2/B3/B4。由于主目标 J 覆盖 drain，240 s 冻结控制动作会额外引入未注册 post-arrival policy，因此本选择在任何 P1 性能结果产生前冻结。

## 验收边界

必须验证 deterministic replay、controller-blind fairness、BBM/MBB、multi-old/no-op/parallel/reservation/release-owner/draining、无关 setup、32/32/64 caps、identity/dedup、原 proposer top-K/8-8，以及 238/240/242/early-complete/600 时刻规则。160 星 sanity 只报告候选数量、hash、ID、Gate C legality和必要的 Gate B execution probe，不输出跨控制器 J、delay、best controller 或 improvement。

