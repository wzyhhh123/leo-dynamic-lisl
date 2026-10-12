# Production B4 multiprocessing integration / checkpoint alignment

**B4_PRODUCTION_MULTIPROCESSING_INTEGRATION = PASS**。本次独立工程 attempt 为 `outputs\b4_final_compatibility_20261003T221327_994529Z\multi_epoch`，t=0/2/4/6/8/10 的完整 serial-vs-production-8-worker 验证全部精确通过。上一 FAIL 和暂停 attempt 原样保留，没有改判。

四种对应 checkpoint hashes 全部相等；每种模式内 H_decision_root = H_post_observe，分别匹配 controller 的 live-before/live-after。H_pre_call 只与另一模式的同名 checkpoint 比较。实际顺序见 `B4_PRODUCTION_MULTIPROCESSING_CHECKPOINT_AUDIT_CN.md`。

每 epoch 精确比较 raw/final IDs、order/hash、所有分支结果与证据、J_H、合法性及原因、Gate B、terminal/reservation/event versions、active/admit graph、Q/I/D、累积目标与诊断、action/proposal、tie metadata 和决策字典。POST_DECISION 到下一个 DECISION_ROOT 使用真实 network evolution；状态随时间变化，非重复初始快照。

生产官方 P1 runner 的 B4 构造参数为 8 workers；串行参考显式保留。persistent pool 在本 controller 生命周期内只创建一次，branch mutable scientific state 每 task 从当前根状态独立构造；退出后无遗留 worker。run 和 engineering-prefix 的 finally 路径关闭 pool。异常不会触发自动换候选或自动串行重试。

| epoch / s | serial observe / s | 8-worker observe / s | speedup | exact |
|---:|---:|---:|---:|---|
| 0 | 299.557 | 58.775 | 5.10× | YES |
| 2 | 686.481 | 135.459 | 5.07× | YES |
| 4 | 532.270 | 99.755 | 5.34× | YES |
| 6 | 533.226 | 99.170 | 5.38× | YES |
| 8 | 545.678 | 102.255 | 5.34× | YES |
| 10 | 549.765 | 103.262 | 5.32× | YES |

六个 epoch 总 observe 提速 **5.26×**。每 epoch candidate source、proposer、network advance、Gate B 和 epoch total 的原始 timing 见 `epoch_evidence.json`；此数值只针对本工程 prefix，不能当作整场 P1 的提速保证。

focused/multiprocessing/runtime tests **56/56 PASS**；完整仓库回归 **318/318 PASS**；正式 registration 路径 seal tests **4/4 PASS**；最终 default P1 preflight **PASS**。测试阶段只使用 outputs 下的待验收候选 runtime 元数据，最终 preflight 使用正式的新 registration；旧 runtime chain 和旧 overlay 未修改。

新 overlay canonical SHA-256：`65b5fbc35eed1c07b77e017412454e27225180a78fb3a1eb1c6f6cb8497c233a`。registered P1 executed=false，P2 started=false，RL started=false。到此停止，等待人工授权正式 P1。
