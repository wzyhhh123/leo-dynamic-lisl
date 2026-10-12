# Production B4 等价验收检查点审计

本文件描述实际代码时序；最终 PASS/FAIL 以新 attempt 的报告为准。历史 `b4_production_multiprocessing_20261002T122028_592605Z` 保持 FAIL，历史暂停 attempt 保持 PAUSED_INCOMPLETE。

## 实际调用顺序

`P1RunExecutor._decision(epoch,index)` 在入口记录 H_pre_call，随后调用 `engine.advance_to(epoch)`。`advance_to()` 先按原有 event loop 积分到目标时刻，再调用 `settle_current_time()`；即使目标时刻等于当前时刻，也会执行 settlement。之后 `_decision()` 检查时间、读取 `controller_visible_state` 并记录 H_decision_root，再调用原 candidate source 和 proposer。

候选生成完成后调用原 `controller.observe()`。B4 在 observe 内部计算所有 hypothetical branches 并按原冻结顺序选优，返回 action；紧接着记录 H_post_observe。随后才创建真实 action 记录。若 action 为 REPLACE，原代码调用 `schedule_action()` 和 `settle_current_time()` 完成本时刻 Gate B 接受/拒绝及物理 transition 启动；若为 HOLD，不创建真实重构动作。动作回调、audit 和原 timing record 完成后记录 H_post_decision。

正式 `run()` / `run_engineering_prefix()` 在调用 `_decision()` 之前还可能推进并结算一次；因此 H_pre_call 的含义严格为 `_decision()` 入口，不能假定它是整个 epoch 推进之前的状态。新工程验收保留了既有真实 network advance 和 settlement 调用，没有移动这些调用。

## 四类检查点

| checkpoint | 实际位置 | 应匹配的控制器字段 |
|---|---|---|
| H_pre_call | `_decision()` 入口，内部 advance 前 | 无；仅作 serial/parallel 对应比较 |
| H_decision_root | advance/settlement 和 state 读取后，candidate generation 前 | live_state_sha256_before |
| H_post_observe | observe 返回后，真实 Gate B action 前 | live_state_sha256_after |
| H_post_decision | 本 epoch 真实 action 执行、原 audit/timing 完成后 | 真实执行器当前 canonical state |

每种模式分别要求 H_decision_root = H_post_observe，并要求两个 controller live hashes 分别匹配这两个检查点。serial 与 parallel 的四种对应检查点分别完全相等。没有 H_pre_call = H_decision_root 的要求。

## 状态链与只读边界

每个 epoch 从上一 epoch 的 POST_DECISION 经真实 `advance_to(next_epoch)` 和 event settlement 到下一个决策状态。新验收比较推进后状态、下一 epoch 的 DECISION_ROOT 及完整 Q/I/D、图、terminal/event 证据。所有采样仅调用现有 canonical hash 和 snapshot 读取接口；checkpoint sink 只追加审计记录，不调整 queue、事件、路由、候选或 worker 计算。

新 attempt 覆盖 t=0,2,4,6,8,10。通过完整 multi-epoch 对照后才进行最终回归和 preflight。registered P1/P2/RL 未授权执行。
