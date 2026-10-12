# Gate F3 In-Flight Propagation Closure Repair

## 状态

**Gate F3 in-flight propagation closure repair = PASS**

本修复只处理 D2 延迟速率积分在最后传播事件处留下的正浮点尾项。没有修改 F3 COMPLETE 阈值（0.01 bit）、D2 内部返回阈值（1 bit）、traffic、routing、controller、Gate B/C、setup、decision cadence 或 frozen manifests；没有执行 registered P1。

## 修复语义

仅当同一个 `(directed edge, commodity)` 同时满足以下条件时闭合：

1. 当前 source service rate 为 0；
2. 当前 delayed arrival rate 为 0；
3. propagation agenda 中不存在该 key 的未来事件。

此时剩余 `in_flight` work 在当前最后到达事件处原子转入接收端：若接收端是 commodity destination，则计入 delivered；否则计入接收节点 queue。随后该 in-flight entry 置零。闭合不使用“小于某阈值”的判断。

闭合前后逐 commodity 检查 `A-D-Q-I`。误差变化不得超过 8 ULP，闭合后的误差仍须满足原冻结 conservation tolerance；否则立即报错。

## 验证

聚焦回归 26/26 PASS，覆盖目的端闭合、中间节点闭合、active service 禁止闭合、future event 禁止闭合、自然事件驱动闭合、确定性重放、Gate D2 原测试和 F3 0.01 bit drain 合同。

完整仓库回归为 279/280 PASS。唯一失败与本修复无关：旧 P1 preflight 只识别 BLOCKED/ABORTED attempt，尚不识别已经按用户要求暂停并存档的 `PAUSED_INCOMPLETE` attempt。因此当前 P1 preflight 仍为 NOT_READY，本轮没有修复这项独立的执行记录问题。

历史暂停证据包保持不变，SHA-256 为：

`9f16af068e5576979e52006e37dba8c2c7509e6261153486f446c8208e6c0336`

## 后续边界

本修复没有重启 P1。后续应先单独处理 pause-state preflight，再在新的人工授权下运行一个非注册/最小 B0 drain verification；通过后才重新授权 registered P1。
