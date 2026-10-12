# F3-v2 K0结构证据汇总工程入口

状态：ENGINEERING_ONLY。新增模块为 `src/dynamic_lisl/f3_v2/k0_ledger.py`；入口为 `tools/prepare_f3_v2_k0_ledger_review.py --input-manifest <项目内JSON路径>`。本入口不运行matching、builder、uncapped source、controller、traffic或K* selection。

## 输入与覆盖

合同只读现有 `configs/gate_k0_contract_v1_1_DRAFT.json`，保护原文件。固定12个K、20点0:30:570、两次replay，应有480条记录。合同值、18/20及全部原门槛必须一致，不接受在工具里传入更宽阈值。CLI只读取manifest明确列出的snapshot和solver/physical/inventory/lifetime支持文件，要求精确相对路径和SHA，拒绝缺失/篡改/路径越界。

`snapshot_record()`接收结构执行器实际输出的solver和uncapped库存，检查EXACT K、terminal degree、无parallel satellite pair、Gate C/resource通过、counts/IDs和MBB/BBM计数一致。它不替代底层solver或Gate B/C证书的独立验证。时耗允许在两次replay不同；比较结构状态、指标、输入hash及diagnostic的canonical hash，不能把wall-time差异当作物理差异。构造状态和batch diagnostic必须使用不含耗时的规范内容。

支持artifact存在/hash正确本身也不是科学gate通过的证明；故本入口无论汇总多少记录，始终输出 `Gate_K0_PASS=false`、`full_audit_complete=false`、`human_authorization_verified=false`、`K_star=null`。正式K0 producer、逐gate独立验证和人工批准后的selection仍须完成，不能把汇总工具当最终Gate K0验收器。

## 缺失及统计语义

所有240个K/time strata均保留。每point缺少一个replay记MISSING_REPLAY；结构hash不同记REPLAY_MISMATCH；求解预算耗尽保留UNKNOWN，不生成假metrics或当作无合格K；EXACT_INFEASIBLE与UNKNOWN区分。出现已证明的某点拓扑不可行，可以排除该K，但无拓扑的MBB比例保持不可用，不填0冒充观测。

全部20个exact point及replay齐全才汇总该K的capacity、all-plane、connected/nonbridge、replace>=16、8MBB+8BBM及20点median。中位数为中间两项均值，MBB分母0时比例null且该predicate不通过。占用band15%–50%、K4排除和min-admissible原则原样保留；本入口只报告admissibility review，不取最小K、不自动创建K1。

batch compatibility仍仅diagnostic，不加入admissibility。截断寿命摘要为L_usable_within_horizon，报告min/P10/median/P90/max、<=setup/10s/20s比例、右删失计数；线性(n−1)q分位数明确作为诊断，未新增选择门槛。观测截止600不是自然失效，右删失physical end保持null。

## 工程测试和剩余边界

10项小型单元测试覆盖20-point合同、阈值漂移、两replay/时耗归一、18与17点边界、median、空库存、UNKNOWN/已证不可行/缺replay、480条literal记录、输入/指标篡改、capped库存拒绝、censor寿命及支持hash损坏。literal记录不代表160星K×20审计已执行。

另有3项planning-chain测试：保留旧计划直接链接，新增显式两级parent链；未登记hash、错parent、缺失/篡改report/seal/prior bytes、跳中间parent和科学源码路径均拒绝。只允许用户明确请求改动的四份计划，不给runtime或科学合同增加successor许可。

下一步仍需把真实结构producer、K0每point独立证书验证与本汇总接口串起来；完整正式K0/K1执行、K*选择、生产候选政策及性能实验等待集中科学冻结和对应授权。本轮不改Gate A–E/F3-v1/K4/K0历史证据。


## Oct9工程更新：逐点生产器及内容关联

上述初版的“producer尚未接入”记录保留。当前已有独立 k0_snapshot.py/k0_support.py 及固定8星验收入口，见 F3_V2_K0_SNAPSHOT_ENGINEERING_CN.md。磁盘loader在path/hash之后还重算matching、图/bridge、寿命摘要、成员identity并用原Gate B重构预建立状态，拒绝hash正确的空support。原10项ledger测试的literal汇总仍不是自然审计；support loader测试现明确拒绝空文件，实际生产链由新增snapshot测试覆盖。

新8星t=0/30/570双replay/独立tiny oracle和t0四链MBB witness已验。完整自然K×20、逐点预算编排、Gate C窗口provenance/uncapped完整性/独立全局证书及human freeze仍未完成，不升级本ledger的Gate_K0_PASS=false和K_star=null。所有完整正式审计、K1及性能授权边界不变。
