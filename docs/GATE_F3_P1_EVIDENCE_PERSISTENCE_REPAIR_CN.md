# Gate F3-1a：P1 失败证据持久化修复

## 正式状态

`Gate F3 P1 Evidence Persistence Repair = PASS`

本轮只修复新 P1 执行/报告适配器的证据落盘顺序，没有启动或重放任何登记 P1 实验。历史 `rho=0.5/B0` 失败仍保持 `FAILED`，其结果封印仍为 `NO`。

## 修复内容

运行后验收现在先为每项不变量生成独立记录，保存 observed value、expected/limit、tolerance、margin、max violation 和可获得的首个失败信息。当前明确记录：

- traffic identity；
- work conservation；
- capacity；
- queue nonnegative；
- drain status；
- COMPLETE/CENSORED semantics；
- raw BBM、raw MBB 和 raw total cap；
- final proposer top-K；
- 1 s reporting timeseries consistency；
- 600 s decision boundary。

新的执行顺序为：完成模拟、收集最终状态、构造所有明细、原子写入 invariant report、metrics、final-state evidence、action/transition/candidate/timeseries、写入 artifact hashes，随后才计算 aggregate pass。若存在失败，再写入 `failure_summary.json` 并抛出包含具体 `failed_checks` 的异常。

没有改变任何 tolerance，没有 clamp 队列，没有屏蔽 invariant，也没有改写 COMPLETE/CENSORED 规则。

## 验证

专用 unit fixture 不使用任何登记 P1 run_id。验证了：

- 全部 PASS 时报告在正常返回前存在；
- 单项失败时 invariant report 与 failure summary 在异常后仍存在；
- 多项失败时全部失败名均被保留；
- raw value 和原 tolerance 均被保留；
- final-state evidence 与 artifact hashes 在 aggregate exception 前已写入；
- 冻结科学代码和历史两次 blocked P1 证据未改变。

完整回归共运行 247 项测试，全部通过。正式证据目录为：

`outputs/gate_f3_p1_evidence_persistence_repair_20260925T080626_875393Z`

较早的两个 repair checker 目录分别暴露了测试发现路径问题（第一次发现 0 项、第二次缺少子进程 `PYTHONPATH`），均不作为正式 PASS 证据；最终 checker 使用项目 `src` 路径执行了真实的 247 项完整回归。

## 边界

本修复没有也不能恢复历史失败运行中已经丢失的 invariant 明细，因此不对历史失败原因作追溯判断。新的 P1 尝试已具备可诊断执行条件，但仍须单独人工授权；本轮没有重启 P1，P2 和 RL 仍未启动。
