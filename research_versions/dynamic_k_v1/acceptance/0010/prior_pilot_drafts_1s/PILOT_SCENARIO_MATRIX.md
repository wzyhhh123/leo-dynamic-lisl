# PILOT_SCENARIO_MATRIX

状态：PILOT_ONLY / DRAFT_FOR_REVIEW / NOT_RUN。日期：2026-10-12。目标是探索观察到突发以后，单动作滚动预测是否提供进一步研究的价值；不评价 GNN，不构成正式论文性能矩阵。依赖实施修订 0007，当前记录链 0009，版本起点及独立哈希见 `PILOT_PARAMETER_MANIFEST_DRAFT.md`。

## 相同物理与服务输入

所有场景共享 160 星：`X0_1…X0_40,X1_1…X1_40,X2_1…X2_40,X3_1…X3_40`，每星两个动态终端，共 320 个。固定边只取下述 z_ref 的 160 条轨内环边，不照抄其三条动态初始桥。冻结 synthetic TLE 用真实 SGP4 推进，属于受控合成星座条件，不声称运营星座测量。

|输入，均相对于研究根目录|原始字节 SHA-256|
|---|---|
|`data/raw/sgp4_x720/manifest.json`|`61a42d76f4fe25d2e613435f9a26fc092a5943a177675f1081ff2d52c2ff4b7d`|
|`data/raw/sgp4_x720/hashes.json`|`b0dad2adfb3cbacbf0e03a4fd2f1877e64478965f86b95ee40770cdee9934fbc`|
|`data/raw/sgp4_x720/constellation.tle`|`6ffcbc0d57c54e54fc274acb518e1436eaf4d70df56570b862ba42fe32345050`|
|`outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json`|`59644ec7acc56f6a2efe098347874a6caf2eaf8540008c0bcb2a6509b37efa34`|
|`outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl`|`c4f166e05319f7c9a50459f853c5d68f3b67816452c3a85acabd8020e9be0a0a`|
|`configs/hardware_gate_c_simplified_v1.json`|`66ca6881b739aad87ccd850a89f0dcddb9bb35684f48fcdee2e0aece33fadd19`|

全 2742 条已登记终端对窗口输入 N2，禁止沿用 N3 运行中的三个受控终端对作为完整候选宇宙。当前几何、资源、窗口、Gate B/C 合法性仍逐 epoch 检查；既有 t=0 的 1996 ADD 数量是在旧测试 setup 下的历史证据，不能当作新 0.5/0.5/0.5 的实测合法数。

每个有向边容量统一 C=10^6 bit/s，跨 commodity 使用原 equal-weight max-min；每节点同 commodity 使用已验收的 Node-Local FIFO。延迟为实际 SGP4 距离/c。`geometry_refresh_s=None`，与既有 N3 真实 fixture 一致；路由在冻结引擎的拓扑变更条件下重算，服务传播延迟按段采样。若要另加周期几何刷新，必须作为明示的新草案修改，不能默改本设置。

## 明确 OD 与负载

两个连续流体 commodity，权重均为 1：

|ID|源|目的|作用|
|---|---|---|---|
|f_bg|X0_1|X1_1|稳定背景负载，经初始桥|
|f_hot|X0_10|X1_10|热点业务；初始有桥时与背景共享跨轨瓶颈|

所有业务以真实连续注入表示，半开区间 [start,end)，不是在中点注入整段 bit。t=0 的 Q/I/A/D 均为 0，无未知历史 cohort。

|负载组|f_bg bit/s|f_hot bit/s，真实 trace 的分段定义|总注入 A(20)，bit|
|---|---:|---|---:|
|STABLE|200,000，0≤t<20|400,000，0≤t<20|12,000,000|
|SHORT|200,000，0≤t<20|400,000，[0,8)；1,200,000，[8,10)；400,000，[10,20)|13,600,000|
|SUSTAIN|200,000，0≤t<20|400,000，[0,8)；1,200,000，[8,20)|21,600,000|

t≥20 真实率均为 0；继续服务、终端事件和能耗到 T=30。真实 trace 的分段只在实验管理器中保存，用于实际注入和事后误差审计；不把这些开始/结束时刻、场景标签或未来总 A 传给 MPC。

稳定时初始桥两 commodity 合计 0.6C；突发时 1.4C，且热点单独 1.2C。热点直连最多给热点 C，因此即使 ADD 成功也可能继续积压；不能把“增加一条链路”当成所有业务即时排空。以上为静态负载/容量关系，不是 D2 已运行的队列结果。

## 两种初态 × 三种负载

|场景 ID|初始动态状态|真实负载|预期检验内容，均待执行|
|---|---|---|---|
|U-STABLE|K_admit=0，所有动态终端 IDLE|STABLE|无跨轨路由业务等待；ADD/setup/恢复及稳定保持|
|U-SHORT|同 U|SHORT|已建立桥后短暂热点，持久预测是否过度付出 setup/能耗|
|U-SUSTAIN|同 U|SUSTAIN|持续热点下是否继续增加/调整服务路径|
|C-STABLE|K_admit=1，B_base 已 ACTIVE|STABLE|已有可达路径的能耗/保持/释放代价|
|C-SHORT|同 C|SHORT|可达但短暂拥塞，与纯可达性反应规则区分|
|C-SUSTAIN|同 C|SUSTAIN|可达但持续拥塞，检查容量改善而非 K=0 建链|

`B_base=(X0_1,D2)↔(X1_1,D1)`，`B_hot=(X0_10,D2)↔(X1_10,D1)`。初态 C 只包含 B_base，其余 318 终端 IDLE，没有预约和未完成 Gate B TX；轨 2/3 仍可分区，不强求全网连通。B_base 作为明确的工程预建立初始物理 checkpoint，t=0 按实际 ACTIVE 计费，不提交控制 ADD，不生成虚构 t=0 RETARGETING/ACQUIRING 或负时间能耗。初始 checkpoint 构造与冻结 Gate B 不变量须在后续独立工程测试中证明；本轮未构造或执行。

静态 t=0 最短传播路由显示 f_hot 经 B_base 时为 19 跳，路径 `X0_10→X0_9→…→X0_1→X1_1→X1_2→…→X1_10`，合计 0.07582903736974946 s；f_bg 使用 B_base 单跳约 0.004431 s。加 B_hot 后热点具备约 0.000900 s 的直接路径，两个桥的终端互不冲突。两对在 t=0..30 的整数时刻均通过现有物理 guard；实际动作仍以 live/ready 及窗口校验为准，不能据静态图直接改邻接矩阵。

## 四臂配对规则

每个场景分别运行 STATIC_HOLD、原样 N3 REACTIVE_DYNAMIC_K、MPC-ZERO、MPC-PERSIST；同一个已校验 origin checkpoint 深拷贝四份，真实 trace、容量、geometry/catalog、setup、决策 epoch、T、服务/年龄/能耗内核完全相同。初态 U/C 是跨场景差异，不能在同一配对内更换初态。

STATIC_HOLD 不主动改拓扑，仍处理自然失效；不是严格固定 K。REACTIVE_DYNAMIC_K 保持修订 0007 原规则：改善当前不可达需求、无当前 Q/I/注入时 DROP、否则 HOLD。它没有拥塞扩容规则，C 组可能始终 HOLD；如发生，必须原样披露，不能改进规则后继续叫原 N3。U-STATIC 的不可达是参考机制，不用其显著差距证明 MPC 优于其他有效控制器。

四臂共享相同候选生成及小域保留方法，STATIC/REACTIVE 不获得预测结果。不同控制轨迹导致后续物理合法集合不同，应记录这种真实差异，而不是强行共用过期候选。

## 全合法枚举与小域预测子集

先调用原 N2 `CandidateSource.generate`，不设 retention_budgets，获取该时刻全供应 catalog 中由 N2 已定义原子生成路径产生的合法集合与拒绝记录。这个“全部”不覆盖未登记终端对、任意多个旧链路释放组合或联合动作：REPLACE 仍仅为最小冲突集合，或新端空闲时单个旧链路替换。

后续独立 PILOT selector 至多保留 HOLD 1、ADD 2、DROP 2、REPLACE 2：

- ADD：按预先指定 OD 的直连目标 B_hot、B_base 的顺序优先；同目标 action_key 排序，再用其余合法 ADD 的 action_key 填充。仅使用当前合法性和公开 OD，不读取未来负载，不从预测结果倒选候选。
- DROP：当前指定 link_id/完整 LinkRef，按 action_key 取前两项，不隐式释放第三方链路。
- REPLACE：先在合法 BBM 中取一个，再在合法 MBB 中取一个；各模式内目标 B_hot、B_base 优先，其余 action_key。某模式没有合法候选时，余槽按相同目标/字典序补充；不伪造 MBB 空闲资源。
- HOLD 始终保留；无合法某类就记录零，不为凑齐类型制造动作。

在当前两条优先目标上只有一个有效终端对；如果其他当前窗口导致同 OD 多终端对，明确记录优先目标命中与未保留原因。共享候选域用于两个 MPC 和两条原基线；不是全局最优搜索，不用旧 F3-v2 的 REPLACE-only 排序。

逐类型保存 `proposed_unique_count,physical_legal_count,retained_count,scored_count,truncated_count,rejection_reasons`；额外记录 catalog 行数/原始哈希、N2 replacement_coverage、排序键、被预算排除的 action_key 和选择回执。N2 的 considered 可能含去重前计数，不能误写为唯一候选数。明确区分 PHYSICALLY_NONE、LEGAL_BUT_NOT_RETAINED、SCORED_INVALID 和 INPUT_CATALOG_OMISSION。若未来发现枚举成本太高，停止报告，不能先裁剪物理宇宙再假报完整合法数。

主场景不保证实际选出每种动作，尤其 REPLACE 在两桥都有空闲资源时可能无收益。另以独立工程 fixture 验证合法 ADD/DROP/BBM/MBB 的真实执行与分支评分；不将 fixture 的强制动作当成四臂控制器的自然选择。六场景及上述系数预先锁定为待审核草案，执行后不得挑场景或改 burst 来制造 MPC 胜出。
