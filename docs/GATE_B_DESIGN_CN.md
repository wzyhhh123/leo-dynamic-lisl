# Gate B：独立双 dynamic-LCT 状态机设计

当前范围：仅物理终端资源和生命周期。每星 D1/D2 各一个，fixed FWD_INTRA/BWD_INTRA 是分离的只读端口清单，不参与 dynamic occupancy。没有 traffic、commodity queue、routing、matching、MPC、RL 或主性能实验；不修改旧 sender-only executor。

## 数据模型

实现：`src/dynamic_lisl/terminal_executor.py`，仅使用 Python 标准库，适配现有 Conda pytorch。

- `Terminal` 保存 terminal_id、phase、双端具体 current_peer/target_peer、reservation_id、event_version、orientation/frame、terminal_free_time、retarget/acquisition timestamps、active_link_start、visibility_end。
- `Link` 以具体 terminal pair 绑定，保存 link_id、visibility_end、DRAINING、两个方向的 synthetic TX completion，以及 MBB release-owner。
- `Reservation` 同时绑定两个终端及其 event_version，保存双端 retarget 时间、acquisition 时间、visibility_end 和 LINK_UP 后释放计划。
- 全部时间为相对执行器起点的秒。测试 orientation 是合成局部单位向量；重定向完成时更新，期间保留最后已到达方向。此字段不是 FOV/slew/姿态跟踪模型。
- terminal_free_time 是既有 TX 排空后的最早资源释放时刻，不表示 ACTIVE 端口可以被免费使用；必须同时检查 phase 与 reservation。DRAINING 时终端 visibility_end 优先记录目标窗口，旧链窗口始终由 Link 独立保存。

## 命令和原子性

`submit([Connect(...), Keep(...), Disconnect(...)])` 在完整执行器副本上检查并执行整批预约。全部成功才替换当前状态；失败不修改端口、链路、预约、事件堆、计数器或日志。批次按显式列表顺序解释，不是无序交换求解器。空批次等价 HOLD；pending 事件继续执行。

CONNECT 显式指定端点 `(satellite_id, D1|D2)`、双方 synthetic retarget duration、acquisition duration 和有限 visibility_end。要求预测 ready 严格小于 end，否则整批拒绝。Gate B 假定命令时目标已进入有效窗口；未来 Gate C 提供窗口起点/FOV/运动约束，不由本模块推断。

同一 terminal-pair 已 ACTIVE 时使用 KEEP，时间戳、事件版本、setup 和事件队列不变。对该绑定再次 CONNECT 会拒绝，避免无意重复 setup。

## BBM

占用端口换 peer：双端预约 → 旧连接双方 DRAINING → 完成已开始 TX → 双方 LINK_DOWN → retarget → 双方 acquisition → LINK_UP。

新请求可能冲突于两条旧连接：两条旧连接各自排空、各自双边断开，新连接双方从各自实际 free 时刻独立开始 retarget。早完成一端等待另一端，保持 RETARGETING，双方都完成后一起进入 ACQUIRING。

`t_ready = max(t_free_a + tau_a, t_free_b + tau_b) + tau_acq`。

同 peer 更换一个或两个终端也产生新 setup。为禁止同卫星对并行链，先排空旧物理绑定，再开始新绑定；未占用的新端口在等待期间可为 IDLE，但已 reservation，绝不算真实空闲。

DRAINING 禁止两个方向的新 TX；只允许原先已开始的 TX 完成。synthetic completion_time 包含最后信号到达对端，不只发送器串行化结束。每方向最多一个进行中的 TX，反向可同时存在。本模块不计算 bit rate 或负载。

## MBB

`Connect(..., release_after=(old_terminal_pair,...))` 仅在两个新端口都真实 IDLE 且未预约时合法。旧连接被 release-owner 锁定，setup 期间仍 ACTIVE、允许 TX。新链 LINK_UP 后才令旧链 DRAINING，排空后释放。

只有一端空闲不算 MBB；不能借 fixed 端口；不能对同一卫星对 MBB 出第二条并行链。第三方不能拆除/重构已被 release-after 计划锁定的旧绑定。新 setup 中止则解除该锁，旧链保留；旧链自然失效则正常释放，不伪造连续性。

Gate B 验证的是端口物理生命周期，不保证网络全局连通。合同中的 active/admit 图 transition safety 和公共安全检查属于 Gate C 接入前置条件，不能用本 Gate 的 PASS 替代。

## 事件与失效

同刻优先级：visibility expiry → TX_DONE → LINK_DOWN → retarget → LINK_READY；同优先级用递增序号确定顺序。这不是网络连通性零时刻认证。

setup 期间不能主动改 target 或用 DISCONNECT 取消目标。外生 `expire_visibility(a,b)` 在当前时刻中止目标，双边清理 reservation/target 并递增 event_version。若旧链尚在排空，保持 DRAINING 到原 TX 完成，不重新开放新 TX。已开始 BBM 的旧连接不会因新目标 abort 自动复活。

所有 setup 事件检查 reservation ID 与两个 event_version；无效事件仅写 STALE_EVENT，不能 LINK_UP。物理 link ID 也不复用，旧 LINK_DOWN/TX_DONE/expiry 不能影响后来绑定。自然可见性到期双边断开；突发失效可中断原 TX，在日志记 interrupted_tx，本 Gate 不引入 packet/drop 语义。

## 不变量与 acceptance

每个公共动作/事件后执行不变量：每星正好两个 dynamic 端口；无 fixed 借用；current_peer 双向对称；同一 physical link 两端 phase 一致；端口最多一个 current 和一个 target；预约双向且版本匹配；ACQUIRING 双端时间一致；同卫星对无并行 active/pending dynamic links（仅允许 pending 替换正在 DRAINING 的旧链）。

测试覆盖正常建链、occupied BBM、双空闲 MBB、预约冲突、双边释放、DRAINING 拒绝 TX、expiry abort、stale event、重复 KEEP、同 peer 换终端、批次原子失败、另一 dynamic/fixed 端口独立，另覆盖双旧链排空、同刻事件、双向 TX 和负向不变量。

## 运行与证据

在 `dynamic_lisl_v2` 中运行：

```powershell
python tools/check_gate_b.py
```

每次新建 `outputs/gate_b_<timestamp>/`：

- `report.json`：PASS/FAIL、逐测试结果、acceptance 映射、重复运行一致性、不变量检查数。
- `traces.json`：每测试的事件迁移、完整终端快照、最终状态与命令输入。
- `inputs.json`：synthetic 输入定义、测试源文件/code hash、接受的几何资产 hash、Python 版本。
- `hashes.json`：所有输出文件 SHA256；测试配置参数在带 hash 的测试源文件中，已提交命令同时写入日志。
- `unittest_run_1.txt` / `unittest_run_2.txt`：两遍确定性运行记录。

输出目录不覆盖。失败运行保留 FAIL，后续成功运行另建目录。当前合成测试仅使用 6 星资源清单，不执行 160/240/720 网络实验。
