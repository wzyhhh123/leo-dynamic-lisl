# F3-v2 集中审批清单（10月工程进度补充）

状态：DRAFT_NOT_FROZEN。此清单引用现有42-run计划，不修改其ID、配置或次序；不授权正式性能运行。独立工程实现已由此前 Full Engineering Implementation 请求授权，计划中的“本次计划不授权实现”只描述计划更新本身，不能解释为已有工程授权被撤销。

## 一次审阅的科学事项

|审批组|待冻结的内容|建议与替代方案|未审批的影响|
|---|---|---|---|
|HF_SCIENCE|主周期5 s、单epoch最多4个资源独立REPLACE、HOLD；whole-transition STRICT_CONNECTED；B3 whole-graph V_v2 × min eta；B4 H10、current-rate persistence、末端min(10,600-t)|保持现有草案作为审阅版本；B3 min eta需要接受短寿命成员主导评分的局限，不声称精确网络收益|工程fixture可测试，不能成为正式算法/科学验收|
|HF_K|K0-v1.1 0:30:570共20点、18/20、原K集合和occupancy band、截断寿命；联合兼容仅diagnostic；K1预建链初始化及初始age|按结构合同完整审计后取最小合格K；UNKNOWN须补足求解证书，不能借最大matching容量界宣布Z_K可行|K*未定；不能构造正式K1或宣告主实验preflight READY|
|HF_SEARCH|共享raw/singleton/batch构造、结构排序和截断覆盖政策；beam/pool/展开/validation/rollout预算|原W4/M32/184/184/33、raw32/32/64、singleton16/8+8均待审批。新增建议：先在自然场景作不读J的old-binding/terminal-conflict覆盖审计，再确定显式多样性规则。替代：保留字典截断并预注册、披露单链退化风险|仅批准batch4上限不能保证pool有四链动作；不能据最终J调预算|
|HF_B2|per-binding LINK_UP计龄、初始age=0、H4/H8和threshold0|保留最小防抖对照；不增加额外策略，不按表现选最佳hold|不阻塞B3/B4核心工程，但正式B2比较需冻结|
|HF_MATRIX|现有42个deterministic run、所有ID/次序、CORE/STABLE/SPARSE/FACTORIAL/HOLD/ROUTER及固定图case|保留全部42项；同动作权限的B4-B3为主比较，2×2 cadence/batch实验复用已注册anchor；只作paired描述统计|仍是草案，不能运行或把工程结果填进论文结果表|
|HF_RESOURCE|10月24–29可用机器窗口、一个B4 episode/8worker、内存与执行上限；成本-only探测资源范围|原20 h/day、20%余量、净96 h是待确认资源提案。实测K*/production pool成本不足，不能提前批准总耗时预测|10月31日完成日期无法可靠保证；Oct11/16/20/23提前风险复核|

科学冻结须生成新的独立合同与canonical SHA，不覆盖历史草案/FAIL/PASS。未测成本、未获K1证书不能靠批准草案消除。

新增审阅输入：[工程solver与实际评分结果](F3_V2_ENGINEERING_SOLVER_AND_SCORING_RESULT_CN.md)。t0/K24单点已获得exact解析界证书，但完整K0和K*未完成。B3真实8节点fixture已观察到短寿命成员主导min eta、联合理想收益较高却得分较低；建议审批时明确接受这一启发式局限，或先提出独立科学修订，不以结果静默改代码。42项审阅manifest、固定case绘图接口已准备，均不是FROZEN，也没有正式结果。

Oct9新增自然输入证据：[真实K4候选覆盖与成本](F3_V2_NATURAL_SOURCE_COVERAGE_RESULT_CN.md)。7596合法候选→raw64分布49/9/6/0→singleton16全部同一old，最终无size2/3/4；另有整批安全size4 MBB witness。source完成耗时455.081 s，不能仅凭已有clone提速批准预算。**HF_SEARCH必须一起冻结候选结构多样性与runtime scouting/Gate C evaluation计算预算**；建议保留uncapped K0审计，runtime用明确有界scouting并报告遗漏，两者分离；具体数值由计算资源及结构验收确定。规则改变前不实现、不将该单点变成K选择硬门槛。

## 必须先看清的新结构证据

[raw覆盖审计](../outputs/f3_v2_raw_batch_coverage_20261008T144825_051246Z/report.json)是固定20节点工程构造，不读取traffic/Q/J：uncapped合法物理候选144，四条old binding各36；截断32全部来自第一条old；最终16个非HOLD proposal均为singleton。同时存在通过真实整批安全验证的四成员witness。这证明该排序**可能**在beam之前失去批量动作覆盖，并不证明真实K*场景已经如此。当前代码/原科学候选政策未据此调整。

可审批的下一步是自然结构覆盖检查及候选政策设计审阅，不是自动把coverage加入K*硬门槛或根据控制器收益挑新的排序。选择新的结构多样性规则后，须新增独立overlay、资源上界、tiny coverage和deterministic验收；所有B1/B3/B4共用。

## 独立正式运行授权

HF_RUN仍单独进行：只有科学合同冻结、K0/K1完成、新版本生产候选/自然场景/8-worker验收、完整当前回归、逐run实测预算和manifest/preflight全部通过后，人工才可授权指定manifest hash和完整run ID序列。当前P1-v2/P2/RL均未启动。此前K4小候选池工程PASS和旧B4-v1 multiprocessing PASS均不能替代上述关口。

工程可继续做参数化正确性测试、成本/结构诊断和证据工具；正式K*选择、科学冻结及正式实验等待上述集中审批，不逐小参数中断。


## HF_K 补充：逐点拓扑状态的初始化约定

新增工程生产器将每个 K/t 视为独立结构快照：先从该时刻双端 IDLE 状态，用原 Gate C 实际 setup 验证所有候选及所选链接；再用原 Gate B 构造该点的假设预建立 K 条物理绑定，用于 uncapped REPLACE 和整批安全诊断。分别保存 forward setup 资格、predicted ready 和预建立 terminal/event state；不声称 setup 已经在采样时刻前真实发生，更不允许生产控制器免费重构。

该约定名为 INDEPENDENT_PREESTABLISHED_AT_SNAPSHOT_WITH_FORWARD_GATE_C_CERTIFICATE，目前只是显式工程参数，未批准为正式 K0 科学合同。建议集中审批时明确：K0 是独立快照结构容量审计，还是继承 t=0 拓扑并真实演化的轨迹审计。后者需要另外定义控制/到期后的预算处理，会改变审计问题，不能默默替代。K1 的 t=0 初始化与 B2 初始 age 另行保留；不把此工程约定变成冻结或新的 K 硬门槛。

逐点小网络证据与校验范围见 F3_V2_K0_SNAPSHOT_ENGINEERING_CN.md。支持文件的哈希及内容一致性、tiny oracle 和双 replay 已具备工程入口；完整自然 K×20、输入窗口 provenance、独立全局证书、计算上限和结构运行审批仍须完成。正式 K* 未选择，P1-v2/P2/RL 未启动。

## 当前集中审阅入口（保留上述历史进度描述）

请使用 [一次性审批包](F3_V2_CONSOLIDATED_APPROVAL_PACKET_CN.md) 和 `configs/f3_v2_consolidated_human_review_DRAFT.json` 审阅当前六组建议。HF_SEARCH现已有具体256次scouting/覆盖/结构种子草案，仍未批准或实现；自然输入provenance的77项检查已经完成，上文“仍须完成”中的这一项由新证据替代。完整自然K0/K1、最终生产验收、实测episode预算和正式运行授权仍缺失。

本补充未改变旧科学合同、参数或实验矩阵；原清单bytes已存档。集中审批问题仍待人工回复，不重复发送小参数提问。
