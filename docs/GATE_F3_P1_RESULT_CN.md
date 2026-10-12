# Gate F3-1 P1 执行前阻塞报告

## 正式状态

`GATE_F3_P1_EXECUTION_BLOCKED_BY_CANDIDATE_SOURCE_NOT_FROZEN`

P1 未启动，12 个注册 run 均未执行；P2、R1–R4 和 RL 均未启动。该状态不是性能结果，也不改变 Gate F3-0 已冻结的实验合同。

## 已完成的 preflight

历史 `tools/check_gate_f3_experiment_human_freeze.py` 已在任何性能运行前执行一次并 PASS，证据保存在 `outputs/gate_f3_p1_20260925T050259_813979Z/historical_f3_0_checker_report.json`。运行该历史 checker 后，`configs/gate_f3_experiment_status.json` 已恢复为执行前的逐字节版本；恢复前后 SHA-256 均为 `64267208fbc9308ea485b8f475af7964b96e47474e679b031d9e88b82549153c`。

冻结 F3 canonical SHA、execution manifest canonical SHA、traffic registry、hotspot manifest、OD manifest、alpha-star 及全部父资产 hash 均通过。P1 仍恰好包含 12 个唯一、`PLANNED_NOT_EXECUTED` 的 run_id，且交叉组合仍为 160 星、Z_MODERATE、shortest-propagation、hotspot-migration、三个 rho 与 B0/B1/B3/B4。

## 阻塞原因

现有 `MultiEpochControllerRunner` 要求调用方提供 `candidate_source(state, context)`。现有 `FrozenTerminalPairProposer` 只对已经构造好的 `CandidateSpec` 做 Gate C/terminal/safety hard filtering、8/8 分层、top-K=16 和冻结排序；它不负责从自然 terminal-pair windows 构造动作宇宙。

正式代码中没有生产 candidate source。Gate F1/F2 的 160 星 sanity 都只手工注入一个预先选定的 `CandidateSpec`。因此当前没有冻结规则可唯一决定：

1. 每个 epoch 从哪些自然 Gate C windows 生成候选；
2. 一个新 terminal pair 对应哪个 `old_physical_binding`；
3. 双端空闲、可 genuine MBB 时应释放哪一条旧 binding，以及 `release_after` 如何产生；
4. 两个新端点分别占用不同旧链时是否允许一次动作拆两条链；
5. 在禁止主规模 all-pairs exhaustive search 的前提下，进入公共 top-K proposer 之前怎样做有界、结果盲的 candidate-universe materialization；
6. proposal ID 与去重规则如何保证四个 controller 在相同状态得到完全相同的候选集合和顺序。

这些选择会改变 B1/B3 的解析评分候选、B4 的 rollout branches、实际 BBM/MBB 比例和最终 J。把其中任一规则写进 P1 thin harness 都会新增科学动作空间，而用户合同明确禁止 harness 自带另一套 candidate proposer。因此不能把它当作普通文件映射或报告逻辑补齐。

另有一个需要同时冻结的时间边界：F3 合同规定 2 s cadence、240 s 停止 arrival、仿真 drain 到完成或 600 s，但没有明确 controller 在 240 s 后的 drain 期间是否继续周期决策。两种解释都会改变排空时间与 J；现有 runner 需要显式 `decision_end_s`，不能无依据选择 240 或 600。

## 解除阻塞所需的最小 human freeze

在不修改 B0/B1/B3/B4、Gate B/C/D 或 F3-0 manifests 的前提下，新增一个独立 F3-P1 execution overlay，冻结：

- deterministic candidate-universe materializer；
- old-binding 与 terminal-pair 的配对及 MBB `release_after` 规则；
- pre-top-K 的有界生成/剪枝规则和 canonical proposal ID；
- controller 在 arrival horizon 后的 decision-epoch 终止规则。

该 overlay 必须在看到任何 P1 性能结果前冻结并 hash。之后才能实现纯 manifest-driven thin harness，并从相同 canonical initial state 执行 12 个注册 run。

## 完整性边界

没有生成 `final_metrics.json`、paired analysis 或 opening figure，因为没有合法的 performance observation。`runs/` 与 `run_ledger.jsonl` 保持为空，避免把诊断或假设性执行误记为注册样本。

