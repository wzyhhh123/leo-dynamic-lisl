# Gate E0：拓扑重构机制验证预注册合同

状态：`FROZEN_BEFORE_E1_E2`。本合同只冻结比较方法、判断规则和后续参数域；E0 不执行科学扫描，不寻找 reversal，不设计 topology controller。

## 1. 研究问题与边界

Gate D2 已证明 scripted terminal proposal 能经 Gate C、Gate B、`G_active/G_admit`、共同路由器和服务层传播到 `Q/I/D`。Gate E 回答的问题是：**改变当前 persistent LISL topology 何时值得支付真实重构代价？** 核心机制是假如忽略 setup 和 transition consequence，瞬时看似有利的 SWITCH 是否会在真实执行后劣于 HOLD。

Gate E 分为 E0（冻结合同与验证 harness）、E1（小型可解释机制实验）和 E2（冻结的 160 星几何验证）。E0 PASS 不要求观察到 reversal；注册域内未观察到时必须报告 `NO_REVERSAL_OBSERVED_IN_REGISTERED_DOMAIN`。

## 2. Paired counterfactual 状态合同

每个实验从确定的决策状态 `S0=S(t0)` 开始。`S0` 至少包含 active binding、双 dynamic-terminal 状态、`Q/I/D`、terminal-pair windows、`G_active/G_admit`、traffic cursor、未来传播事件和待执行 action cursor。`t0` 处先处理完同刻真实事件，再深拷贝。

各分支必须共享 geometry、terminal state、`Q/I/D`、未来 traffic、traffic trace hash、capacity、scheduler 和 routing configuration。唯一允许改变的是本次注册的重构 action 及其执行时刻。分支前 canonical state hash 和 future trace hash必须一致。

## 3. 分支语义

- **HOLD**：在评价窗内不主动执行本次 topology replacement；自然 visibility expiry、traffic profile change 和传播完成仍正常发生。
- **REAL-SWITCH**：在 `t0` 执行注册的 terminal-pair action，完整经过 Gate C 和 Gate B 的 DRAINING、LINK_DOWN、RETARGETING、ACQUIRING、LINK_UP。不得给目标函数加入人工 setup/switch/outage penalty。
- **IDEAL-SWITCH**：使用与 REAL 完全相同的 terminal pair、target topology、release-after 和 natural expiry，但把 retarget/acquisition duration 设为零。它仍受静态 Gate C feasibility、终端数、FoR、visibility、capacity 与共同 routing/service 约束，只删除迁移所需时间。
- **DELAYED-SWITCH(delta)**：同一 action 在 `t0+delta` 执行，注册比例 `delta/T_demand ∈ {0,0.25,0.5}`。到时不再合法则报告 `INFEASIBLE_AT_EXECUTION_TIME`，不得替换 candidate。
- **MBB-SWITCH**：仅在初态确有双边 IDLE terminal、FoR 合法且 action 含真实 `release_after` 时使用；不得制造额外终端。

同 peer 换 terminal 仍是新物理连接。REAL 与 IDEAL 的 target signature 必须相同。

## 4. 目标与配对效应

沿用 D0 的加权未完成业务面积：

`J_b = sum_f integral_[t0,T_D(b)] N_f(b,t) dt`。

每个分支共享相同 future arrival horizon，并在其自身 drain 或共同 censor limit 结束。E0 harness 从总累计 `J` 中减去 `t0` 以前的 prefix，得到决策后的 `J_b`。定义：

- `Delta J_real = J_real - J_hold`；
- `Delta J_ideal = J_ideal - J_hold`；
- `r_b = (J_b-J_hold)/J_hold`。

负值表示 SWITCH 优于 HOLD，正值表示 HOLD 优于 SWITCH。`J_hold<=0` 时 relative effect 不定义，标记 `UNDEFINED_ZERO_HOLD_OBJECTIVE`，不得除零或改变指标。

## 5. Decision reversal

数值 deadband 冻结为 `epsilon_r=1e-9`：

- `r_ideal < -epsilon_r` 且 `r_real > epsilon_r`：`SETUP_INDUCED_DECISION_REVERSAL`；
- `r_ideal > epsilon_r` 且 `r_real < -epsilon_r`：`REVERSE_DIRECTION_REVERSAL`；
- 任一 `|r|<=epsilon_r`：`NUMERICALLY_TIED`；
- 其他情况：`NO_REVERSAL`。

deadband 只处理浮点符号，不是工程显著性阈值。E0 不运行 reversal search。

## 6. Break-even 合同

固定 `S0`、target、traffic、`rho`、`T_demand` 和 `L_remain`，仅改变 `tau_setup`，定义 `Delta J(tau)=J_switch(tau)-J_hold`。注册 grid 为 `{0,0.5,1,2,4,8,16}` s。

相邻可执行 grid 点异号形成 bracket；不得假设 `Delta J(tau)` 单调。只有单个独立 bracket 才允许 deterministic bisection/refinement，宽度不超过 `0.01 s`。多个区间报告 `MULTIPLE_BREAK_EVEN_INTERVALS`；无 crossing 报告 `NO_BREAK_EVEN_IN_SCANNED_RANGE`；`ready>=visibility_end` 报告 `INFEASIBLE_SETUP_EXCEEDS_WINDOW`。不得扩大范围追找 crossing。

## 7. 参数域

机器真值见 `configs/gate_e0_sweep_manifest.json`：

- `rho ∈ {0.2,0.5,0.8,1.0,1.2}`；`rho=1` 是 reference splittable multicommodity capacity scale，不等于 shortest-path 实际 100% utilization；
- `kappa1=tau_setup/T_demand ∈ {0.05,0.2,0.5,1.0}`；
- `kappa2=tau_setup/L_remain ∈ {0.05,0.2,0.5,0.8}`。

E1 可构造精确 ratio。E2 不修改真实 visibility window，只按自然 `kappa2` 分层：low `(0,0.1]`、medium `(0.1,0.35]`、high `(0.35,0.7]`、very-high `(0.7,1)`。空 bin 报 `NO_ELIGIBLE_CASE`。

## 8. Result-blind scenario selection

机器真值见 `configs/gate_e0_scenario_selection_manifest.json`。选择只能读取 Gate C legality、BBM/MBB、transition connectivity、remaining lifetime、terminal occupancy、hop/path difference、shared edges、第三方 OD 与 `kappa2` stratum。严禁读取任何 `J`、Delta J、delay、delivery ratio、reversal 或 performance score。

每个 class/bin 按 `(t0, old_edge, new_edge, terminal_ids, scenario_id)` 字典序选前一个。找不到时报告 `NO_ELIGIBLE_CASE`。四类为 E-A BBM/no-route、E-B BBM/connected reroute、E-C genuine MBB、E-D shared-congestion externality。

## 9. 第三方外部性

预注册 focus commodity 集 `F_focus`，其余为 `F_third`。按 commodity 分解：

`Delta J_third = sum_(f in F_third) (J_f_switch-J_f_hold)`。

若 focus 改善而 third-party 变差，必须同时报告，不能只展示目标流收益。该量仍来自网络演化，不能另加到总目标而双重计数。

## 10. 路由稳健性

primary router 固定为 Gate D 的 deterministic shortest-propagation-delay router。E0 另实现 independent `DeterministicLoadAwareRouter`，它只能读取当前 `G_admit`、当前 edge utilization、当前 node queue 和当前 offered load；禁止读取 controller identity、future action 或 future traffic。路由器必须确定性并在所有 paired branches 使用同一配置。不得因某种路由更容易产生 reversal 而改变 primary。

## 11. Manifest、版本与无结果

`gate_e0_sweep_manifest.json` 和 `gate_e0_scenario_selection_manifest.json` 在 E1/E2 前生成、hash 并冻结。修改必须建立新版本、说明原因并保留旧文件。合法无结果包括：`NO_BREAK_EVEN_IN_SCANNED_RANGE`、`MULTIPLE_BREAK_EVEN_INTERVALS`、`NO_ELIGIBLE_CASE`、`NO_REVERSAL_OBSERVED_IN_REGISTERED_DOMAIN`、`CENSORED_AT_DRAIN_LIMIT`。无结果不等于 harness FAIL。

## 12. E0 correctness acceptance

E0 必须验证：

1. zero-setup REAL 与 IDEAL 的 `J`、target 和 topology/service timeline（忽略 transition bookkeeping/action label）一致；
2. clone 前 canonical state、`Q/I/D` 和 future trace hash 一致；
3. 两个 HOLD replay 的 `J` 与 canonical output 完全一致；
4. REAL/IDEAL 使用同一 target；
5. 目标中不存在 `setup_cost_weight`、`switch_penalty`、`outage_penalty`；
6. classifier、break-even bracket/refinement、result-blind selection 和 load-aware router 正确；
7. Gate A–D frozen hashes unchanged。

## 13. E0 禁止事项与完成状态

E0 禁止根据 `J` 搜索最好/最差 candidate、扩大 sweep、修改注册网格、matching/b-matching、greedy/hysteresis topology controller、MPC/rollout、RL/PPO、240/720 星主性能实验和 superiority claim。

全部验收后只记录：

```text
Gate E0 mechanism-validation contract = PASS
Gate E1 started = false
Gate E2 started = false
Gate F started = false
```

随后停止，等待人工审查 manifest。
