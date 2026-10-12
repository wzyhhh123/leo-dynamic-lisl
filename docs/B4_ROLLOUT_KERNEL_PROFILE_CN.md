# B4 Rollout Kernel Profiling

ENGINEERING_PROFILE_ONLY。只执行一个真实160星、Z_MODERATE、rho=0.5、primary router初始decision epoch。HOLD + 16有效候选，10秒forecast。OFF/ON使用同一根状态、同一候选、同一顺序。没有执行registered P1/P2/RL，也没有实施新性能优化。

## 先决条件

lightweight clone seal = PASS；decision-local hash reuse seal = PASS；current P1 preflight = PASS；full regression = 299/299 PASS。新增runtime chain通过现有工程报告绑定当前源码哈希，原frozen manifest与历史attempt不变。

暂停attempt只有在原归档清单、ZIP、原attempt文件集/逐文件hash、telemetry文件集/逐文件hash、5项ledger和无result seal均验证后才被识别为PAUSED_INCOMPLETE。ledger时间戳 .588120Z 与 .58812Z 按精确时刻相等比较，不使用数值容差。原始归档仍保留MANUAL_AUDIT_REQUIRED，不把暂停结果改成PASS或恢复执行授权。

## 等价性

17/17 branch：J_H、validity、Gate B action_result、完整terminal event sequence、完整final canonical state精确一致。最终decision字典、proposal、tie handling和decision hash精确一致。live状态未被修改。所有配置和scientific source hash在profiling前后相同。

## 耗时

OFF observe：277.882 s；ON observe：532.171 s。
17支ON总耗时：532.041 s；mean 31.297 s；median 32.091 s；max 37.467 s。

各类分支统计：{"HOLD": {"count": 1, "mean_s": 5.1719425, "total_s": 5.1719425}, "BBM": {"count": 8, "mean_s": 33.8114832375, "total_s": 270.4918659}, "MBB": {"count": 8, "mean_s": 32.04715130000001, "total_s": 256.3772104000001}}。

下表是扣除嵌套计时的exclusive wall time；inclusive stage timing另存JSON，不能直接相加。

| 项 | 总秒数 | 占ON observe |
|---|---:|---:|
| clone | 1.7204 | 0.32% |
| hash | 1.0407 | 0.20% |
| forecast_hash | 0.0000 | 0.00% |
| root_action | 12.9258 | 2.43% |
| routing | 39.7434 | 7.47% |
| delay | 77.0686 | 14.48% |
| service | 139.6840 | 26.25% |
| qid | 160.3315 | 30.13% |
| objective | 0.7429 | 0.14% |
| event | 98.1651 | 18.45% |
| finish | 0.4034 | 0.08% |
| diagnostic | 0.0013 | 0.00% |
| other | 0.3433 | 0.06% |

root hash前后检查、forecast hash只发生于decision层，JSON的global_hash_timing_s单独保留它们。每支forecast hash为零不表示遗漏，而是当前冻结优化已将它移到分支外复用。

objective项测量补偿累加器调用；objective公式计算与循环开销仍归qid，因此它是objective部分耗时的下界，不能独立断言“完整目标积分很便宜”。service/QID/event整体分组不受这种内部归属影响。cProfile与Python计时hook会产生开销，ON占比用于诊断，不当作未经instrumentation的真实生产占比。finish含为精确对照捕获canonical state的额外开销；other含harness和profile保存开销。

| 分支序号 | 类别 | ON总秒数 | _step次数 | route evaluation | delay调用 | allocation次数 |
|---|---|---:|---:|---:|---:|---:|
| 1 | HOLD | 5.172 | 360 | 1 | 401087 | 361 |
| 2 | MBB | 30.432 | 2914 | 2 | 837325 | 2916 |
| 3 | MBB | 31.741 | 3043 | 2 | 838423 | 3045 |
| 4 | MBB | 30.870 | 2969 | 2 | 838302 | 2971 |
| 5 | MBB | 31.409 | 3051 | 2 | 837359 | 3053 |
| 6 | MBB | 32.207 | 3133 | 2 | 836613 | 3135 |
| 7 | MBB | 35.624 | 3487 | 2 | 834880 | 3489 |
| 8 | MBB | 32.091 | 3029 | 2 | 839399 | 3031 |
| 9 | MBB | 32.002 | 3119 | 2 | 839712 | 3121 |
| 10 | BBM | 35.561 | 3176 | 2 | 808693 | 3178 |
| 11 | BBM | 37.467 | 3449 | 2 | 809451 | 3451 |
| 12 | BBM | 37.079 | 3394 | 2 | 810033 | 3396 |
| 13 | BBM | 25.996 | 2177 | 2 | 812678 | 2179 |
| 14 | BBM | 29.767 | 2515 | 2 | 811949 | 2517 |
| 15 | BBM | 32.221 | 2870 | 2 | 810486 | 2872 |
| 16 | BBM | 36.430 | 3357 | 2 | 810629 | 3359 |
| 17 | BBM | 35.970 | 3222 | 2 | 808792 | 3224 |

完整proposal ID、J_H、final hash、inclusive/exclusive秒数及每支结尾队列/事件/历史规模见branch_timing.json。

## 历史增长性

根状态proxy：{"terminal_log_length": 32, "transition_history_length": 0, "routing_history_length": 0, "service_history_length": 1, "observation_length": 1, "pending_event_count": 8, "terminal_event_queue_length": 8, "in_flight_object_count": 0, "queue_state_size": 0}。
每支结尾proxy也已记录，包括terminal log、transition、route/history、timeseries、pending events、I对象数与queue大小。本轮只有t=0，不能据此拟合T_clone(t)或断言后期历史增长无影响；没有额外跑晚期epoch。

## 结论与停止

PRIMARY_RUNTIME_BOTTLENECK = service_event_QID

NEXT_OPTIMIZATION_CANDIDATE = BRANCH_LEVEL_MULTIPROCESSING

上述候选只用于下一轮讨论，尚未实施。若routing/delay与service/event都显著，应结合OFF总时长和instrumentation开销确定次序，不能仅凭ON单项差异预测加速倍数。

registered P1 executed = false（本轮）；P2 started = false；RL started = false。历史P1曾执行并暂停，证据如实保留。preflight PASS不构成新P1人工授权。

证据目录：outputs\b4_rollout_kernel_profile_20261002T041039_957649Z。

补充判断：service/event/QID合计约74.96%，routing/delay合计约21.95%，clone/hash约0.52%。建议下一步先讨论分支级多进程的隔离、序列化开销及确定性验收，再考虑严格的decision-local跨分支几何/路由复用；两者均未实现。本轮源码检查与注册实验启动授权仍是不同事项。
