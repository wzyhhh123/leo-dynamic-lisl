# Gate B 验收结果

**PASS**。现有 Conda `pytorch` 环境实跑 34 项 deterministic unit/regression tests，连续两遍均通过，完整事件日志与最终状态一致；每遍 402 次 invariant assertions。没有执行 160/240/720 主性能实验，没有进入 Gate C。

最新证据目录：`outputs/gate_b_20260921T064554_915646Z`。

## 交付

| 文件 | 用途 |
|---|---|
| src/dynamic_lisl/terminal_executor.py | 独立状态/连接/预约模型和事件执行器 |
| tests/test_terminal_executor.py | 34 项合成资源生命周期测试 |
| tools/check_gate_b.py | 两遍复现、机器报告和 hash 输出 |
| docs/GATE_B_DESIGN_CN.md | 状态、动作、原子性、时序、不变量与限制 |
| configs/gate_a_acceptance_v0.3.json | 本轮明确接受的几何输入与原文件 hash |
| configs/gate_b_status.json | 当前 Gate B PASS 及报告路径 |

`report.json` 含逐测试结果和 14 类 acceptance 映射，覆盖用户要求的全部检查。`traces.json` 含每个测试的终端状态迁移、提交命令、最终状态和断言次数。`inputs.json` 记录测试输入来源/code hash、几何资产 hash、时间语义及运行环境。`hashes.json` 记录输出 hash；已独立核验。

## 核心时间线示例

BBM 测试初态为 A.D1—B.D1 ACTIVE，两方向最后接收时间分别为 5 s、7 s。t=0 请求 A.D1—C.D1，双方 retarget 2 s/1 s，acquisition 3 s。

| t (s) | 事件/状态 |
|---:|---|
| 0 | 新目标双端预约；A—B 两端 DRAINING，拒绝新 TX；C 开始 retarget |
| 1 | C 完成 retarget，等待 A |
| 5 | A→B 原 TX 完成，旧链仍等待另一方向 |
| 7 | B→A 完成；旧链双端 LINK_DOWN，A 开始 retarget，B 释放 |
| 9 | A 完成 retarget；A/C 双端进入 acquisition |
| 12 | A.D1—C.D1 双端 LINK_UP |

ready = max(7+2, 0+1)+3 = 12 s。

MBB 测试初态 A.D1—B.D1 ACTIVE，旧 TX 最后接收为 9 s。t=0 使用真正空闲的 A.D2、C.D2，retarget 2 s/3 s、acquisition 1 s，并声明 LINK_UP 后释放旧链：

| t (s) | 事件/状态 |
|---:|---|
| 0–4 | 新 D2 绑定 setup，旧 D1 绑定继续 ACTIVE，可接纳 TX |
| 4 | 新链先 LINK_UP，然后旧链进入 DRAINING |
| 9 | 旧链 TX 排空，双端 LINK_DOWN；新链继续 ACTIVE |

没有复制终端或借用 fixed 端口。另一动态端口和 fixed 端口清单的独立性另有测试。

## 验收范围

通过的检查包含：双端原子预约/冲突、两条旧链独立排空、BBM/MBB、MBB 依赖锁与失败保留旧链、DRAINING 拒绝新 TX、双边释放、setup 禁止改 target、visibility abort、同刻 expiry 优先、stale LINK_READY/LINK_DOWN、event_version、重复 KEEP、同 peer 单端/双端换 terminal、禁止并行链、批次失败完全回滚、full-duplex 合成 TX、负向不变量检测。

合成 orientation/duration/visibility/TX 时间不代表硬件标定或真实业务。fixed 仅验证资源分离，不认证固定轨道环。全网 active/admit 连通、FOV/slew、正式 geometry 接入属于后续 Gate C；本 PASS 不覆盖这些条件。

## 复现

在 `dynamic_lisl_v2` 的 PyCharm `(pytorch)` 终端执行：

```powershell
python tools/check_gate_b.py
```

不要用 `python -O` 禁用断言。入口每次创建新输出目录，不覆盖历史。当前 Gate A 使用记录已按用户决定更新：relative Walker / SGP4 / candidate & visibility consistency 满足当前 satellite-only 使用要求，absolute TEME orientation 是 documented common-mode offset，不阻塞 Gate B。原历史审计和 TLE 已核验未变。
