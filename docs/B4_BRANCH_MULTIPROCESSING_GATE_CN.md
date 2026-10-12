# B4 分支级多进程工程 Gate：失败封存

**B4_BRANCH_MULTIPROCESSING_GATE = FAIL。** 本轮按“任何异常立即停止”规则停在4-worker启动检查，未运行4-worker分支，未启动8-worker，也未接入正式P1。

## 已完成结果

真实160星、Z_MODERATE、ρ=0.5、primary router、t=0、HOLD+8BBM+8MBB。真正串行B4耗时 **277.271s**；1-worker进程池 **278.699s**；2-worker进程池 **146.588s**。2 worker相对1 worker加速 **1.901×**，并行效率 **0.951**。1-worker相对真正串行多 **1.428s**，该差异包含IPC、序列化和系统波动，不能全归因于单项开销。

1与2 worker都通过17/17分支精确比较：分支结果、Gate B动作、事件顺序、终端/预约/事件版本、active/admit图、Q/I/D、累计目标、outage和最终canonical状态一致；最终controller decision字典及tie处理一致。live前后hash相同。单worker观测RSS峰值分别约0.113GB和0.109GB；它们是采样RSS，不是连续峰值。

## 停止原因

4-worker池 warm-up 中，短小的ping任务返回的**不同PID少于4个**，触发 `WORKER_STARTUP_COUNT_MISMATCH`。ProcessPoolExecutor可以尚未把所有进程调度到这些很短的任务；因此这个断言失败尚不能证明4-worker的科学结果会错，也不能声称4-worker更慢或更快。用户合同要求异常即FAIL+STOP，故未调整warm-up、未重试、未改网格。

4 worker：未测；8 worker：未启动；完整1/2/4/8网格的最快worker数：**未知**。在已完成的1/2组中，2 worker较快，不能称为整个网格的最优。

## 审计状态

本轮使用 `ENGINEERING_PROFILE_ONLY` run_id，保留serial reference、逐支结果与状态、IPC/RSS/CPU指标和失败traceback。源程序未接入注册P1；历史frozen manifests与paused attempt证据未修改。

启动前P1 preflight = PASS；本轮focused Windows spawn测试 = PASS。失败后遵守STOP规则，**没有运行最终full repository regression或再次preflight**，所以不能报告本轮验收所需的“full regression 100% PASS”。上一轮299/299回归属于此前代码状态。

registered P1 executed（本轮）= false；P2 started=false；RL started=false。多进程生产接入=false。后续如继续，需要新的人工决定先修正warm-up进程计数的工程验收方法，再从独立新attempt重新验证；本轮不能标PASS。

证据目录：outputs\b4_branch_multiprocessing_20261002T110603_454356Z。
