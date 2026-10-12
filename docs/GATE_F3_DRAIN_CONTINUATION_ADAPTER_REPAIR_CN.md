# Gate F3 Drain Continuation Adapter Repair

## 正式状态

**Gate F3 Drain Continuation Adapter Repair = PASS**

本轮只修复 F3 执行/排空适配层，没有执行任何注册 P1 run，也没有启动 P2 或 RL。此前三次 BLOCKED attempt 及其原始证据保持不变。

## 问题与修复边界

历史第三次 P1 attempt 在 **240.16470503331377 s** 返回时仍有 **0.03552987114996607 bit** 未完成工作。D2 的内部返回条件是：

    residual <= max(state_tolerance_bits, conservation_abs_tolerance_bits)

冻结值为 **max(0.01, 1.0) = 1.0 bit**。因此 D2 可以合法地把控制权交还给调用者，但该返回不满足 F3 的 **0.01 bit** COMPLETE 条件，也不满足只能在 **600 s** 判定的 CENSORED 条件。

新增的 F3 专用适配器在每次 D2 返回后重新读取真实 time、Q 和 I：

- Q + I <= 0.01 bit：COMPLETE；
- time >= 600 s 且 Q + I > 0.01 bit：CENSORED；
- 其他情况：继续调用现有 D2 production evolution，处理路由、容量分配、传播、Gate B 事件、自然到期和队列状态。

它不扣减、归零或 clamp 残余工作，也没有创建第二套 service simulator。若一次 continuation 既不推进物理时间，也不改变 canonical scientific state，则明确停止并返回：

    GATE_F3_DRAIN_ADAPTER_BLOCKED_BY_NO_PROGRESS_INTERFACE

## 控制时序

冻结 drain 决策节拍没有变化：**240, 242, 244, ..., 598 s**。适配器只推进到下一个既有 decision boundary，由原 P1 executor 继续走正常 controller 路径；600 s 不产生控制决策。

## 验证

专项 10 个 deterministic fixtures 全部通过，覆盖合同中的 A–J。真实 D2 两节点夹具得到：

- D2 在 t=1.0 s、残余 0.05 bit 时按自身 1 bit 阈值返回；
- F3 将该状态判为 CONTINUE_DRAIN；
- 适配器沿原 propagation agenda 推进到 t=1.1 s；
- 最终残余为 0 bit，F3 判为 COMPLETE；
- 守恒误差、容量超限和负队列计数均为 0。

全量回归为 **257 tests PASS**。F3-0、F3 execution manifest、F3-0.1 overlay 的 canonical SHA 均保持冻结值；D2 文件 SHA-256 仍为 **5b674ee226ac07aba136fc7c207f6abe727a4d63ad9097c1291afa6217750fd4**。B0/B1/B3/B4、Gate B/C、candidate source、routers、traffic 和冻结 tolerance 的哈希未变。三次历史 BLOCKED attempt 的 artifact hash 清单全部复核通过。

## 产物

- src/dynamic_lisl/f3_drain_continuation.py
- tests/test_gate_f3_drain_continuation_adapter.py
- tools/check_gate_f3_drain_continuation_adapter_repair.py
- configs/gate_f3_drain_continuation_adapter_repair_status.json
- outputs/gate_f3_drain_continuation_adapter_repair_20260925T084633_694138Z/

正式复核命令：

    python tools/check_gate_f3_drain_continuation_adapter_repair.py

该命令仅运行合成专项测试、全量回归和哈希审计，不运行注册 P1 experiment。

## 后续状态

**new P1 execution attempt readiness = READY**

这表示修复层已经具备重新执行条件；本轮没有重启 rho=0.5/B0，注册 P1 执行数仍为 0。**P2 started = false**，**RL started = false**。

