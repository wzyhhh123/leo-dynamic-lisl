# Gate F3 Runtime Telemetry + Engineering Profile Support

## 状态

**Gate F3 runtime telemetry/profile support = PASS**

本轮没有运行 registered P1，没有运行长 profile，没有启动 P2、R1-R4、B2 或 RL。历史目录 outputs/gate_f3_p1_execution_20260925T090650_595069Z 及其 RUNTIME_ABORT_RECORD.txt 保持只读，整棵证据树在验收前后逐文件哈希一致。

## Passive progress telemetry

新增 PassiveProgressRecorder。正式 P1 runner 默认关闭 telemetry；传入 --progress-dir 后启用。progress 目录必须位于科学 attempt root 之外，因此 progress 文件不会进入 scientific artifact hash。

每个实际发生的 controller decision epoch 写两条记录：

- EPOCH_START：只记录已有的 run/epoch/time/phase 元数据，在 controller state、candidate source、proposer 和 observe 前写出；
- EPOCH_END：复用正常路径已经得到的 proposal、action、queue/in-flight 和外围计时结果。

progress_latest.json 使用临时文件加 os.replace 原子覆盖。max_horizon_progress_pct 只是 sim_time_s/600 的最大时域进度，不是完成概率。

Telemetry 不调用 controller.observe、ScientificSnapshotEvaluator、router、equal_weight_fair_share、Gate B/C evaluation 或 engine.advance_to。缺少的字段不为日志额外计算。

## Timing instrumentation

现有调用次数和顺序不变，只用 time.perf_counter 在外围记录：

- candidate source；
- final proposer；
- B1/B3/B4 controller observe；
- network advance；
- Gate B action execution；
- epoch total wall time。

这些 timing 数据不进入 controller input、candidate ranking、proposal identity 或科学状态。

## ENGINEERING_PROFILE_ONLY B1 harness

tools/profile_gate_f3_b1_runtime.py 使用 production 的 160 星、Z_MODERATE、shortest propagation router、rho=0.5、hotspot migration、production candidate source、top-K=16 proposer、真实 B1、Gate B/C 和 Q/I/D。

它强制使用非注册 run id ENGINEERING_PROFILE_ONLY-B1-RHO0p5-SHORT_PREFIX，只运行 --sim-end-s 指定的短前缀，允许范围为 0–240 s。输出包括：

- progress.jsonl
- progress_latest.json
- cprofile.prof
- cprofile_top50.txt
- epoch_runtime.csv
- report.json

该输出只用于工程性能定位，不是 P1 科学结果。

## 等价性与验收

非注册小型真实 Gate B/D2 fixture 比较 telemetry OFF 与 ON，确认以下内容完全一致：

- selected action；
- proposal ID 与 proposal-set hash；
- terminal event sequence 与 MBB transition type；
- active/admit graph event evolution；
- Q/I/D；
- unfinished work；
- 除 wall runtime 外的最终 metrics；
- conservation/capacity/nonnegative queue 结果；
- candidate source、proposer 和 controller.observe 调用次数。

专项测试 4 项 PASS，全量回归 261 项 PASS。F3 contract、execution manifest、candidate/drain overlay 及冻结科学模块哈希均未改变。

## PowerShell 手动命令

在项目目录运行 20 s 工程 profile：

    python tools\profile_gate_f3_b1_runtime.py --sim-end-s 20 --output-dir outputs\manual_b1_profile

查看 profile 当前进度：

    Get-Content -LiteralPath outputs\manual_b1_profile\progress_latest.json

查看 cumulative-time top 50：

    Get-Content -LiteralPath outputs\manual_b1_profile\cprofile_top50.txt

未来经人工授权启动新的正式 P1，并把 telemetry 写入科学 attempt 目录之外：

    python tools\run_gate_f3_p1_execution.py --progress-dir outputs\manual_p1_progress_next

在另一个 PowerShell 终端查看最新 epoch：

    Get-Content -LiteralPath outputs\manual_p1_progress_next\progress_latest.json

持续查看追加日志：

    Get-Content -LiteralPath outputs\manual_p1_progress_next\progress.jsonl -Wait

显式关闭 telemetry、保持兼容默认行为：

    python tools\run_gate_f3_p1_execution.py --disable-progress

