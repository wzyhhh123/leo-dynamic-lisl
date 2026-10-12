# Dynamic K v1：当前研究版本

文档更新：2026-10-12（北京时间）。当前工程阶段为 **N3 Engineering PASS**，实现与验收封存在修订 **0007**；修订 **0008** 仅更新本 README 及文档完整性记录。N4 尚未实施，等待审核及新的授权。

本版本独立于旧 Gate 研究资产，复用冻结的 Gate B/C/D2 内核。当前结果均为 `ENGINEERING_TEST_ONLY`，不构成科学 Gate PASS、性能优越性或统计显著性结论。正式科学合同/参数尚未冻结，未开展主性能实验或训练。

## 当前入口

1. [N3 中文结果报告](acceptance/0007/RESULT_CN.md)：规则、配对指标、解析验算、测试及覆盖边界。
2. [配对 K 状态时间线](acceptance/0007/K_TIMELINES_CN.md)：K_admit、DRAINING、SETUP 和真实动作时序。
3. [N3 闭环合同](contracts/N3_CLOSED_LOOP_BASELINES_CN.md)与[工程语义配置](configs/n3_baseline_semantics_v1.json)。
4. [修订 0007](revisions/0007/record.json)：实现、输入、验收证据、父修订与全部新增文件的哈希绑定。
5. [完整性工具](tools/version_control.py)：只读验证完整文件集合、原始字节哈希及修订父链。

旧 `dynamic_lisl_v2/README.md`、`configs/current.json` 和历史 Gate 文档属于原研究资产，不代表这个独立版本的最新状态。版本起点与各阶段报告保留其形成时的内容，当前导航以本 README 为准。

## 阶段状态

| 阶段 | 状态 | 内容与证据 |
|---|---|---|
| N0a/N0b | 完成 | 5810 个旧研究文件的原始字节基线、独立版本起点与连续修订 |
| N0c | 静态语义补充完成 | 动态 K、固定时域、结果字段与 N1a/N1b 分工；[修订 0003](revisions/0003/record.json) |
| N1a | Engineering PASS | 固定 T、320 动态终端事件积分、四能耗态/五执行态与 J_T/N(T)/交付率；[报告](acceptance/0004/RESULT_CN.md) |
| N1b | Engineering PASS | Node-Local Per-Commodity FIFO、连续 cohort 与已交付 bit 加权端到端时延；[报告](acceptance/0005/RESULT_CN.md) |
| N2 | Engineering PASS | 真实 HOLD/ADD/DROP/REPLACE、BBM/MBB、物理候选及显式释放；[报告](acceptance/0006/RESULT_CN.md) |
| N3 | Engineering PASS | STATIC_HOLD / REACTIVE_DYNAMIC_K 多 epoch 闭环、分区恢复与 catalog 诊断；[报告](acceptance/0007/RESULT_CN.md) |
| N4 | 未实施 | RL 问题定义：观测、动作、奖励、约束及未决科学参数，需另行授权 |
| N5 | 未实施 | 获选算法与正式实验，需科学冻结及运行授权 |

旧 F3 的完整 K* 选择不是新方向的前置条件；其历史失败仍保留。文档修订 0008 不开展新阶段，不改变已有工程验收或科学语义。

## 当前接口与语义

| 模块 | 接口 |
|---|---|
| [runtime/n1a.py](runtime/n1a.py) | `TerminalEnergyLedger`、`FixedHorizonEvaluator`、`validate_measurement`：事件时间积分与固定 T 评价 |
| [runtime/n1b_evaluator.py](runtime/n1b_evaluator.py) | `DeliveredFluidEvaluator`、`validate_n1b`：复用 N1a，加入已交付 fluid-bit 年龄统计 |
| [runtime/n2_controller.py](runtime/n2_controller.py) | `AtomicTopologyController`：真实双端事务、动作回执、释放审计与 clone/checkpoint/restore |
| [runtime/n2_candidates.py](runtime/n2_candidates.py) | `CandidateSource`：独立 ADD/DROP/REPLACE 路径及合法/保留/截断诊断 |
| [runtime/n3_baselines.py](runtime/n3_baselines.py) | `CurrentObservation`、`StaticHold`、`ReactiveDynamicK`、`ClosedLoopBaseline`、`paired_runs`、`validate_n3` |

闭环为：当前业务/队列/终端状态 → 控制器 → N2 原子动作 → 真实 Gate B/C 执行 → D2 网络服务与 FIFO → N1a/N1b 固定 T 指标。没有第二套终端执行器，不直接改邻接矩阵模拟建链。

- `K_admit(t)` 是可接纳新业务的真实 ACTIVE 动态链路数。DRAINING 不计入主 K，DRAINING 连接及 SETUP/预约终端单独统计。不设置固定 K 或额外 Kmax，上限来自双端资源、可见性及物理约束。
- 功率为 IDLE 5 W、RETARGETING 40 W、ACQUIRING 40 W、ACTIVE/DRAINING 45 W。按 320 个动态终端的事件时间线在统一 [0,T] 积分，增量能耗扣除 `320 × T × 5 W`。
- 提前排空仍推进到 T；t=0 已建立连接按实际 ACTIVE 状态计费，不虚构 t=0 前的 setup。允许临时分区，无路由业务等待，队列和在途业务保留。
- 同一节点、同一 commodity 按本地到达顺序 FIFO；同时到达按 bit 量比例混合。原始注入时间跨跳保留，连续注入不使用区间中点近似。
- 平均已交付时延为 `delivered_bit_age_integral_bit_s / delivered_bits`，单位秒。没有交付时返回 `null`，不以 `J_T/D(T)` 代替。结果保留 N1b 数值精度状态和有条件误差界，不将 IEEE 闭合修正案例标为解析精确。

`STATIC_HOLD` 不主动改变拓扑，但自然失效、终端事件、业务服务和能耗继续发生，因此不是严格固定 K 控制器。

`REACTIVE_DYNAMIC_K` 只读取当前观察和 N2 合法保留候选，选择改善当前无路由队列/注入需求可达性的动作；分别按改善的队列 bit、当前注入 bit/s 降序排序，相同改善优先 REPLACE，再 ADD，资源允许的 MBB 优先 BBM，最后确定性字典序。无收益动作且当前 Q/I/注入均无正需求时 DROP，否则 HOLD。策略不读取未来业务、评价 T、最终指标或未来动作；当前无需求 DROP 可能影响不可见的未来业务，规则不宣称科学最优。

每个工程 epoch 提交一个原子动作，这是 TEST_ONLY 运行约定，最终并行动作上限未冻结。物理无合法候选、合法候选被预算截断与工程输入 catalog 范围分别审计。

## N3 工程结果与覆盖范围

N3 专项 20/20，N1a/N1b/N2 原测试 25/25、24/24、27/27；16 份 N3 结果通过 schema 校验。历史回归 131/132，保留旧 F3 失败，名称及 traceback 与 0006 一致，无新增回归。独立版本保护测试 22/22。

160 星自然 SGP4 配对运行使用相同初态、traffic trace、几何、服务内核和 TEST_ONLY T=4 s；闭环采用三对明确登记的终端输入，完整 catalog 诊断独立执行。

| 控制器 | K(t) | 交付率 | J_T (bit·s) | 已交付平均时延 (s) | E_LCT / DeltaE (J) |
|---|---|---:|---:|---:|---:|
| STATIC_HOLD | 0 | 0 | 3.5 | null | 6400 / 0 |
| REACTIVE_DYNAMIC_K | 0→1→0 | 1 | 0.0933196 | 0.0933196 | 6496 / 96 |

反应策略实际在 t=0 发起 ADD，t=0.4 完成 setup 后才增加 K，在 t=1.25 发起 DROP；BBM/MBB REPLACE 另有针对性工程 fixture。这里只展示功能与机制，不作统计性能比较。

完整已登记 catalog 的 2742 条窗口均有探测记录，t=0 的 1996 个 ADD 候选合法；已占用连接时另验证 DROP/REPLACE 路径。全部记录中 2424 次接受、318 次 FoR 拒绝，其数值左边界原因已[逐项复现](acceptance/0007/catalog_boundary_audit.json)，没有放宽角度容差。完整诊断在 attempt01 实际执行并单项通过，后续绑定其独立哈希、复核输入和记录映射，不是再次执行完整物理扫描。

覆盖限于已登记的 160 星 catalog 及受控时刻，不代表未登记全空间、连续所有时刻、全部释放子集或真实硬件校准。闭环的三对终端输入范围与预算截断分别记录。[配对指标](acceptance/0007/paired_metrics.json)、[完整工程证据](acceptance/0007/attempt02/engineering_examples.json)和[验收汇总](acceptance/0007/attempt02/acceptance_summary.json)保留原始数值、动作回执及状态哈希；首轮接口格式错误及源码快照也保留在 attempt01。

## 文件与信任入口

- `baselines/<UTC 时间戳>/files.json`：创建新资产前的全部研究文件原始字节 SHA-256 和大小。
- 同目录 `exclusions.json`：缓存、IDE、虚拟环境、字节码和锁文件的逐文件排除原因；outputs/tmp 研究证据不因 gitignore 排除。
- `record.json`：两轮采集核对、UTC/北京时间、Git 状态（当前无 HEAD）和旧冻结记录引用。
- `seal.json`：绑定前三个文件的哈希，不包含自哈希。
- `version_record.json`：绑定 baseline seal、首份修订、初始合同与配置。
- `revisions/0001/record.json`：版本起点授权、原因、初始新增文件列表与合同/配置绑定；不把自身哈希递归写入自身。
- `revisions/0008/record.json`：本次文档更新的父记录、授权与 README 修改前后哈希；合同和配置继续绑定 0007 的原文件。
- `acceptance/0001/`：N0 完整性控制测试的原始输出；后续阶段证据在各自编号目录中。

起点与历史修订记录保留其形成时的描述，不是可覆盖的当前配置索引。当前源码和验收仍绑定 0007 的实现 manifest，README 更新没有修改这些文件。

必须在仓库外独立保留交付时的 **version_record.json SHA-256 与最新 revision record SHA-256**。
只读取目录中可一起被改写的清单与 seal，不能认证原始基线；历史末尾修订被删除也需由独立保存的最新修订哈希发现。
哈希不证明人工授权真实性、科学正确性或 Gate PASS，也不提供文件恢复备份。

## 只读验证

使用既有 Conda pytorch，参数中的哈希应来自独立保存的交付记录，不从待验证文件现场计算后当作可信输入。

```powershell
$OriginSha256 = '<独立保存的 version_record.json SHA-256>'
$RevisionSha256 = '<独立保存的最新 revision record SHA-256>'
& 'D:/Program_Files/anaconda3/envs/pytorch/python.exe' -B research_versions/dynamic_k_v1/tools/version_control.py verify --project-root 'D:/Document/leo_routing_attitude/dynamic_lisl_v2' --expected-version-sha256 $OriginSha256 --expected-revision-sha256 $RevisionSha256
```

运行位置为 dynamic_lisl_v2；也可传 `--project-root`。验证不写报告或修改文件。
验证清单/seal/版本记录/修订父链、合同配置绑定、全部现存文件集合与哈希。
未登记新增、删除、内容/换行修改均失败；内容相同的删除/新增另列 POSSIBLE_RENAME，不把重复内容猜成唯一重命名。
读取失败、路径越界、符号链接/重解析点、重复 JSON key、扫描期间变化均拒绝。

## 后续修订

不得覆盖现存基线、版本起点或历史修订。下一修订使用连续编号目录和全新的 record.json，父记录绑定上一编号的路径/大小/哈希。
修订结构沿用 0001，逐文件列 added、modified（before/after）、deleted（before），并记录明确的人类授权、原因与当前合同/配置哈希。
新版本资产可按登记修订变化；旧路径默认受保护，仅 src/、tools/ 的明确登记实现变更可接受。旧测试、Gate 合同/manifest、历史输出和数据不可改写。
在修改前独立保存父版本/修订哈希；修改后登记并封存新的修订记录，再验证并独立保存其哈希。仅写一段变更说明不满足登记要求。
若需新的授权范围，应另立版本/保护合同，不通过篡改旧基线排除规则放行。

已封存的 `acceptance/0001–0007/` 是历史证据，不要原地运行一次性生成器来覆盖报告。复测需新的证据目录、相应修订与适用授权。本次仅更新文档，不重新运行仿真、训练或性能测试。

## 后续实验绑定

`experiments/record_template.json` 只是拒绝执行的空模板，不是实验结果。
每个正式实验必须绑定具体 revision record、baseline seal、合同、配置，以及由冻结配置登记的完整源码/输入/验收文件 manifest。
`verify-experiment --record <相对路径> --expected-experiment-sha256 <外部保存的哈希>` 同时要求上述两个版本哈希。
该入口只核对绑定、参数冻结及授权记录，**不运行实验**；后续 N5 运行入口还必须集成完整项目验证、科学验收和真正的人类运行授权，不能将哈希验证 PASS 视为运行授权。
T_A、T、tau_res、R_min、alpha、D_ref、E_ref，以及正式决策周期、搜索预算和最终最大并行动作数仍为 `null`。工程 fixture 的 T、setup、容量、epoch 和预算不进入科学默认配置，不继承旧 240/600 时域，不加入最低交付率或 STRICT_CONNECTED/BOUNDED_OUTAGE 默认硬掩码。

下一阶段为 N4 RL 问题定义，需另行审核和授权。目前不启动 MADRL/MAPPO/GNN/PPO、联合批次动作、超参数搜索或主性能实验。
