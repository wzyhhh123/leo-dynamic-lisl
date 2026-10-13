# Dynamic LISL v2

文档更新：2026-10-12（北京时间）。这是独立研究目录；当前主线为 **dynamic_k_v1**，N0 完成，N1a/N1b/N2/N3 均为 **Engineering PASS**。N4 尚未实施，等待审核与新的授权。

## 当前入口

1. [dynamic_k_v1 README](research_versions/dynamic_k_v1/README_CN.md)：当前阶段、接口、研究语义和版本保护。
2. [N3 中文结果报告](research_versions/dynamic_k_v1/acceptance/0007/RESULT_CN.md)：控制器规则、配对指标、测试及范围限制。
3. [配对 K 时间线](research_versions/dynamic_k_v1/acceptance/0007/K_TIMELINES_CN.md)：真实拓扑动作及 SETUP/ACTIVE/DRAINING 状态。
4. [N3 闭环合同](research_versions/dynamic_k_v1/contracts/N3_CLOSED_LOOP_BASELINES_CN.md)与[工程语义配置](research_versions/dynamic_k_v1/configs/n3_baseline_semantics_v1.json)。

实现及验收封存在修订 0007；0008 更新独立版本 README，0009 更新本项目入口及其精确路径文档保护条款。两次文档修订均不开展新研究阶段。

## 研究进度

| 阶段 | 状态 | 已完成内容 |
|---|---|---|
| N0a/N0b | 完成 | 5810 个旧研究文件的原始字节 SHA-256 基线、独立版本起点和连续修订 |
| N0c | 静态语义补充完成 | 动态 K、固定时域、计费规则与 N1a/N1b 分工 |
| N1a | Engineering PASS | 固定 T、320 动态终端事件积分、四能耗态/五执行态与 J_T/N(T)/交付率 |
| N1b | Engineering PASS | Node-Local Per-Commodity FIFO、连续 cohort 与已交付 bit 加权时延 |
| N2 | Engineering PASS | 真实 HOLD/ADD/DROP/REPLACE、BBM/MBB、物理候选及显式释放 |
| N3 | Engineering PASS | STATIC_HOLD / REACTIVE_DYNAMIC_K 多 epoch 闭环、分区恢复及 catalog 诊断 |
| N4 | 未实施 | RL 问题定义，需另行授权 |
| N5 | 未实施 | 获选算法与正式实验，需科学合同/参数冻结及运行授权 |

当前结果均为 `ENGINEERING_TEST_ONLY`，不构成科学 Gate PASS、性能优越性或统计显著性结论。未开展 MADRL/MAPPO/GNN/PPO、联合批次动作、超参数搜索或主性能实验。

## 动态 K 闭环

当前业务/队列/终端状态 → 非学习控制器 → [AtomicTopologyController](research_versions/dynamic_k_v1/runtime/n2_controller.py) → 真实 Gate B/C 执行 → D2 服务与本地 FIFO → 固定 T 能耗、业务和已交付时延评价。

- `K_admit(t)` 仅统计可接纳新业务的真实 ACTIVE 动态链路；DRAINING 和 SETUP 独立计量。不设置固定 K 或额外 Kmax，允许临时分区并保留队列和在途业务。
- 终端功率为 IDLE 5 W、RETARGETING/ACQUIRING 40 W、ACTIVE/DRAINING 45 W。320 个动态终端按实际事件时间差积分；提前排空仍统计到 T，初始 ACTIVE 连接不虚构 t=0 前的 setup。
- FIFO 使用每个节点、每个 commodity 的本地到达次序，同时到达按 bit 量比例混合，跨跳保留原始注入时间。没有交付时平均时延为 `null`，不以 `J_T/D(T)` 代替。
- `STATIC_HOLD` 不主动改拓扑，仍推进自然失效，不能称为严格固定 K。`REACTIVE_DYNAMIC_K` 只用当前观察和合法保留候选，以确定性规则选择可达性改善或无需求 DROP，不读取未来业务和最终指标。
- T_A、T、tau_res、R_min、alpha、D_ref、E_ref、正式决策周期/搜索预算与最终并行动作上限继续为 `null`。工程参数不作为科学默认值，不继承旧 240/600 时域。

N3 专项 20/20，N1a/N1b/N2 原测试 25/25、24/24、27/27；历史回归 131/132，保留旧 F3 失败，无新增回归；独立版本保护 22/22。这些是 0007 的既有工程证据，本次仅更新文档。

160 星自然 SGP4、TEST_ONLY T=4 s 的同输入配对示例：

| 控制器 | K(t) | 交付率 | J_T (bit·s) | 已交付平均时延 (s) | E_LCT / DeltaE (J) |
|---|---|---:|---:|---:|---:|
| STATIC_HOLD | 0 | 0 | 3.5 | null | 6400 / 0 |
| REACTIVE_DYNAMIC_K | 0→1→0 | 1 | 0.0933196 | 0.0933196 | 6496 / 96 |

反应策略实际执行 ADD 和 DROP，BBM/MBB REPLACE 有独立工程 fixture。闭环采用三对明确登记的终端输入；完整 2742 条登记 catalog 另行诊断，无漏探测。覆盖不代表未登记全空间、连续所有时刻、全部释放子集或真实硬件校准。详见 N3 报告及[数值边界诊断](research_versions/dynamic_k_v1/acceptance/0007/catalog_boundary_audit.json)；结果保留 N1b 精度状态和有条件误差界。

## 历史 Gate 资产

[docs/README.md](docs/README.md) 和 [configs/current.json](configs/current.json) 是旧研究导航与冻结索引，不是 dynamic_k_v1 最新状态入口。原 Gate 合同、测试预期、manifest、原始数据和实验输出保留，不用新版本工程 PASS 追认历史 Gate。

旧索引记录 A 的当前 satellite-only 接受状态、B/C/D0/D1/D2/E0/E1/E2 的验收，以及 F0 的人工冻结项和 F1 基础设施 PASS / 科学评分合同阻塞状态。具体范围以各冻结合同和结果为准；详细 PAT/tracking/link budget 仍不在 simplified Gate C v1 内，FoR/setup 数值为 sensitivity-only，5000 km 是 diagnostic cutoff。旧 F3 失败证据继续保留，不能声称旧 F 系列全部科学验收通过。

## 当前只读验证

使用既有 Conda `pytorch`，在本目录执行。两个哈希应来自独立保存的交付记录，不从待验证文件现场计算后当作可信输入。

```powershell
$OriginSha256 = '<独立保存的 version_record.json SHA-256>'
$RevisionSha256 = '<独立保存的最新修订 SHA-256>'
& 'D:/Program_Files/anaconda3/envs/pytorch/python.exe' -B research_versions/dynamic_k_v1/tools/version_control_readme_v1.py verify --project-root 'D:/Document/leo_routing_attitude/dynamic_lisl_v2' --expected-version-sha256 $OriginSha256 --expected-revision-sha256 $RevisionSha256
```

从 0009 起，此入口沿用完整基线、父链和原始字节核对，并加入[仅限本次 README.md 的登记条款](research_versions/dynamic_k_v1/contracts/ROOT_README_DOCUMENTATION_CHANGE_CN.md)。原校验器未改写，也未将 README 排除；原入口不支持此条款，会拒绝包含 0009 的历史。

`tools/check_gate_d2.py` 等仍是历史 Gate 验收工具，不能作为当前动态 K 的最新入口。重新运行会产生新证据，需适用授权并按版本机制登记；不要原地重跑封存的一次性生成器或覆盖已有 `acceptance/`、`outputs/` 证据。

## 目录

| 目录 | 作用 |
|---|---|
| `research_versions/dynamic_k_v1/` | 当前 README、runtime、合同、配置、基线、修订及验收证据 |
| `src/dynamic_lisl/` | 冻结物理/服务内核，新版本复用 |
| `tests/` | 原 Gate 确定性测试，保留历史预期 |
| `tools/` | 原 Gate 验收与诊断入口 |
| `configs/` | 原研究索引、合同和 schema |
| `data/raw/sgp4_x720/` | 冻结合成 TLE |
| `docs/` | 原 Gate 合同、设计和历史结果 |
| `outputs/` | 受封存保护的原研究证据 |
| `archive/` | 历史归档 |

根目录 `provenance.json` 只记录最初拷贝。当前 dynamic_k_v1 状态以独立版本 README、具体修订和验收证据为准，旧 `current.json` 保留原样。父目录旧 sender-only 生产执行器没有被修改或引用。本次只更新文档及完整性机制，不进入 N4，不运行仿真、训练或新实验。
