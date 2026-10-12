# B4 单次决策内根状态与 forecast hash 复用

## 实现与范围

本轮仅消除同一次 B4 evaluate_root_actions 调用内的重复序列化，不改变10秒预测、候选集/顺序、动作、真实服务推进、目标积分、容差或决策 tie-break。上一轮 ObservationalE2Engine 轻量 clone 继续使用。

修改 rollout_controller.py：在原有 live_hash_before 位置计算一次根 hash；创建 forecast 后计算一次 forecast hash；将二者作为局部参数传入各分支。结束时依然重新计算 live_hash_after 并检查与根 hash 相等。没有把 hash 存为 controller/evaluator 的跨调用状态，没有按时间或对象 ID 建立缓存。

修改 rollout_evaluator.py：每个新 clone 都实际执行 canonical_state_sha256，与传入根 hash 比较；直接复用这个已验证的 clone hash 作为 start_state_sha256，不再对相同 clone 做第二次序列化。每个有效分支完成后仍独立计算 end_state_sha256。

forecast 在本次决策中由 current rates 构造，所有分支使用同一实例；当前 attach_forecast_to_clone/to_trace 创建新 rates 字典，不修改 forecast。其 hash 仅在这个只读生命周期中复用。若以后引入分支修改 forecast 的代码，必须重审该只读前提。

构造器 reuse_decision_hashes=False 保留旧调用次数路径供测试。直接调用 evaluator 而不提供 hash 参数仍走原路径。hash_context 是内部优化接口，不是外部输入：不允许调用者传入任意或跨决策的根 hash。

## 保留的检查

- 每支 clone canonical state 与当前决策起始状态一致。
- 禁止 branch 携带未来自愿动作。
- 每个有效 branch 的 horizon、守恒、非负队列、容量检查。
- 全部 branch 的 start hash 和 forecast hash 一致。
- 全部 rollout 完成后 live canonical hash 必须与进入前相等。
- 每支结束状态 hash 和完整 decision hash 的定义保持不变。

负控制覆盖：克隆状态被损坏时明确拒绝；最后一支结束后 live 被修改仍拒绝；评估异常退出后再次调用无旧上下文；同一时刻重复调用以及时间前进后调用均与旧路径精确一致。

## 调用次数

设包含 HOLD 在内共 n 个分支，其中 v 个有效。原路径 state hash 次数为 3n+v+2，新路径为 n+v+2。forecast hash 为 n+1 → 1。

17个全部有效分支的小型 deterministic fixture 已测试：state hash 70 → 36；forecast hash 18 → 1。起始 clone 检查17次、结束 branch hash17次、live 前后检查2次均保留。

## 160星工程对照

真实160星、Z_MODERATE、rho=0.5、t=0，保留生产源的完整 raw/final proposal IDs 和 hash。仅为本次工程验证，按结构顺序取 HOLD、首个BBM、首个MBB，两个实现各推进相同10秒forecast。生产 candidate universe 未改变，工程子集不产生正式性能结论。

完整 decision 字典及 decision hash、全部 RolloutBranchResult（J、终端事件、outage、起止状态hash等）精确相等；live state 与原历史记录未被修改。实际计数：state hash 14 → 8；forecast hash 4 → 1。

证据：outputs/b4_decision_hash_reuse_20261002T032756_501919Z/report.json。

本轮未测量 B4 总体 wall-time speedup，不把 hash 调用减少比例当成总运行时间改善。未执行完整160星17分支/多epoch的 final pre-P1 gate。

## 冻结完整性

新建 gate_f3_b4_decision_hash_reuse_overlay_v1.json，保存原 controller/evaluator hash、新 hash、精确等价报告hash及 canonical SHA-256。tests/runtime_phase1_overlay.py 按现有证据链规则识别该新增overlay。未修改任何历史overlay、E0/E1/E2/F3 frozen manifest 或容差。

正式P1 preflight 尚有历史 PAUSED_INCOMPLETE 与新overlay接入事项，本轮不放行、不改启动规则。状态与最终全量回归结果见 configs/gate_f3_b4_decision_hash_reuse_status.json。未启动 P1/P2/RL、分支并行或后续优化。
