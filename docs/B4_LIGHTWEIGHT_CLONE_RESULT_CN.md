# B4 轻量克隆工程结果

状态：B4_LIGHTWEIGHT_CLONE_ENGINEERING_PASS。仅完成本轮克隆优化，不代表 P1 readiness 或完整多 epoch runtime gate PASS。

## 实际改动

- 新增 src/dynamic_lisl/rollout_clone.py：只共享已审计的只追加历史记录，所有历史列表独立；其余字段深复制。
- 在 src/dynamic_lisl/gate_f3_p1_execution.py 的 ObservationalE2Engine.clone 中接入；保留 clone_legacy_reference 测试对照及分支 reporting false/空列表行为。
- 新增 tests/test_b4_lightweight_clone.py 和 tools/check_b4_lightweight_clone.py。
- D2 和 rollout_evaluator 最终与原冻结哈希精确一致；没有修改 controller 决策逻辑、路由、Gate B/C、传播闭合、容差、时域、候选与 frozen manifests。

字段审计见 B4_LIGHTWEIGHT_CLONE_AUDIT_CN.md。所有历史保留；特别是 transition_episodes / pending_clearance 的可变别名仍深复制。共享记录不得由外部调用者原地修改，这不是无条件通用 deepcopy。

## 精确等价性与性能

真实 160 星、Z_MODERATE、rho=0.5、初始时刻，生产源产生 64 个 raw candidates 和 16 个 final proposals。按结构顺序选 HOLD/首个 BBM/首个 MBB；不按性能筛选。每支用相同10秒 current-rate forecast。

两路径的 branch result（含 J、event sequence、outage、hash）、Q/I/D、routes、active/admit 图、服务状态、统计与补偿项、结束 canonical state 精确一致；live 的状态及历史没有被修改。小型测试另比较完整 controller decision（含 decision hash）。生产160星本轮没有执行全部17分支决策或多epoch控制，不能声称已通过最终 pre-P1 gate。

5次克隆耗时的中位数：legacy 0.131762 s，lightweight 0.029137 s，克隆环节加速 4.52 倍。

| 分支 | 原路径总耗时/s | 新路径总耗时/s | 结果 |
|---|---:|---:|---|
| HOLD | 2.393 | 2.301 | 精确一致 |
| BBM_REQUIRED | 19.034 | 19.021 | 精确一致 |
| MBB_STRUCTURALLY_FEASIBLE | 16.373 | 16.523 | 精确一致 |

分支总耗时每种仅一次，受系统噪声影响；不用于断言总体 speedup。克隆节省不能直接外推为 B4 总耗时同比下降，真实10秒服务推进仍占较大部分。本轮未启动进一步优化。

## 回归与阻塞

最终完整单元回归：288项，287 PASS，1 FAIL。唯一失败是既有 test_preflight_accepts_read_only_runtime_abort_record：历史 PAUSED_INCOMPLETE attempt 尚未被 P1 preflight 接受。该问题在本轮之前的传播闭合修复报告中已记录。冻结哈希相关失败已消除；没有放宽检查或改预期哈希来通过测试。

第一次接入曾触及D2/evaluator，产生中间哈希失败；最终收紧为 F3-only 接入并恢复原字节哈希。中间日志和工程报告仍保留，最终证据以本节路径为准。

最终工程证据：outputs\b4_lightweight_clone_20261002T031207_519998Z。

未执行 registered P1/P2/RL。没有修复独立的 pause-state preflight，也没有启动 hash 复用、分支并行或 router 优化。
