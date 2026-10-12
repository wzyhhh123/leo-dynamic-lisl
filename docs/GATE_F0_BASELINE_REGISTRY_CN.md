# Gate F0：Baseline Registry

## Registry 状态

本文件只冻结 baseline 定义与信息边界。所有 baseline 的 `implemented=false`，本轮没有执行性能实验。

| ID | 名称 | 信息等级 | 决策定义 | 科学作用 |
|---|---|---|---|---|
| B0 | STATIC / HOLD | CURRENT_STATE_ONLY | 每个共同 epoch 都 HOLD；自然 expiry/物理失效照常发生 | 判断 dynamic topology control 是否必要 |
| B1 | IGNORE-SETUP DYNAMIC | CURRENT_STATE_ONLY | 决策时按 setup=0 评价 instantaneous target topology；选中的合法 action 仍走真实 Gate B/C setup | 测试忽略 transition consequence 的代价 |
| B2 | HYSTERESIS / MINIMUM-HOLD | CURRENT_STATE_ONLY | 在 B1 或注册的简单 benefit signal 上增加 minimum hold 和/或 improvement threshold | 判断简单防抖是否足够 |
| B3 | SETUP-AWARE GREEDY | CURRENT_STATE_ONLY | 使用 current benefit、真实 setup、usable lifetime 与 current queue/load 做单步决策 | 判断 setup/lifetime awareness 是否已足够 |
| B4 | PROPOSED ROLLOUT / MPC PLACEHOLDER | SHORT_HORIZON_FORECAST | terminal proposal → conflict filter → 真实 Gate B/C + route/service/Q/I/D rollout → HOLD 与 candidate 比较 | 拟议方法占位；本轮不实现 |
| B5 | SMALL EXACT ORACLE | ORACLE_SMALL_FIXTURE_ONLY | tiny fixture exhaustive legal actions + exhaustive registered horizon evaluation | 验证 greedy/MPC approximation quality |

Optional S0 seeded-random legal action 只可作为 sanity baseline，不是核心科学 baseline；启用前必须冻结 seed policy。

## B0 细则

B0 从不主动重构，但不能冻结 geometry、阻止 LINK_EXPIRE 或抹去自然失效。它必须与其他 controller 使用相同时间线、router、traffic 和 drain rule。

## B1 细则

B1 只在**决策评价**中令 (	au_{m setup}=0)。选择完成后：

1. 目标必须是当前 candidate universe 中的 concrete terminal pair；
2. safety 只能拒绝物理非法或违反 frozen hard safety 的 action；
3. safety 不得因为真实 setup 后经济性差而替换 candidate；
4. accepted action 必须用真实 Gate B/C 执行。

## B2 细则

minimum-hold 与 improvement threshold 的数值/grid 不得根据 performance 结果回填。本 Gate 只注册参数族，具体 grid 进入 human-freeze 清单。

## B3 细则

B3 可以计算 current-state myopic signal，但不得 multi-step rollout，不得读取 future traffic realization。setup、ready、remaining/usable lifetime 必须使用真实 candidate metadata。

## B4 细则

B4 的 rollout 必须调用统一仿真链：Gate B/C、(G_{m admit})、common router、service、Q/I/D。禁止用人工 topology score 替代 network rollout。每个 candidate 与 HOLD 用相同 state clone 和 forecast；forecast source、horizon、top-K 尚待人工冻结。

## B5 细则

B5 只用于小规模 fixture，不能出现在 160/240/720 scalability ranking。它可获得 `ORACLE_SMALL_FIXTURE_ONLY` 范围内的注册 future，但必须清楚标注，不得与普通 baseline 的 information class 混比。

## Routing crossing

每个 controller 先在 primary `DeterministicShortestPropagationDelayRouter` 下完成相同点集。Robustness 使用当前实现 `DeterministicLoadAwareRouter`，但必须重放相同 topology/trace/parameters/initial state/epochs/candidates。禁止给 proposed 使用 load-aware、给 baseline 使用 shortest 后直接比较。

## RL 边界

RL/PPO 不属于 required baseline，也不是拟议方法的默认组成。只有 rollout 成本过高、短 horizon 明确遗漏关键长期依赖，或非学习方法出现有证据的结构限制时，才重新评估 RL。

## 未冻结参数

- B2 minimum-hold grid；
- B2 improvement-threshold grid；
- B4 candidate top-K；
- B4 rollout horizon；
- B4 forecast source；
- Optional random seed policy（仅在启用 S0 时）。

这些参数解决前，registry 定义有效，但不能开始公平性能比较。
