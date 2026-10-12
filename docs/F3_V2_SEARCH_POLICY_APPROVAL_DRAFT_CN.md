# F3-v2 共享候选覆盖与筛选预算审批草案

状态：**DRAFT_NOT_FROZEN / NOT_IMPLEMENTED / REQUIRES_HUMAN_FREEZE**。本文件补齐HF_SEARCH的具体推荐，不替代原四份October计划，不改现有source/proposer/controller，不授权正式实验。

## 问题及建议

已保存的自然K4/t0结构检查中，7980次物理验证耗时455.081s；7596合法REPLACE截断为64个，再选16个singleton后全部替换同一old binding，联合池只有size1。另有经过原Gate B/C验证的安全size4 witness。该结果只证明一个自然场景的筛选成本与覆盖问题，不证明K*或全部时刻；不读取J、traffic收益或delivery来制定本草案。

建议集中审阅 **RR_STRUCTURAL_SCOUT256_RAW64_SINGLE16_SEED4_V1**。它是待审批的算法输入政策变更，不是semantic-preserving runtime优化；其成员集合、排序和pool hash可以与原政策不同，必须有新合同、配置和验收。原身份序列化/hash公式、物理与经济控制语义均不变。生产入口目前只支持旧政策，审批此草案也不会让入口自动采用它。

## 推荐的完整规则

1. 每个epoch只使用当前root、原Gate C当前terminal-pair windows、实际terminal/reservation状态和已知时间窗。eligible old links仍按现有规则排除draining/release_owner；以canonical old terminal-pair排序。不可按J、队列收益、controller identity或未来realization筛选。
2. 旧binding访问顺序采用round-robin。起点是 `decision_epoch_index mod n_old`；epoch index由共同决策schedule定义，包含HOLD机会，不由算法自行改变。无old或无当前窗口时直接输出空raw/HOLD，先检查空域再执行任何mod/index运算。排序后的窗口基本键为 `(-window.end_s, plane_gap, canonical new_terminal_pair)`，与现有窗口半开语义一致；这是scouting顺序，不是假定真实ready或经济收益。
3. 为避免各old都只访问同一段新端口，old在canonical列表的原始序号q对应窗口起点 `floor(q*n_windows/n_old)`；第r轮访问该old的 `(offset_q+r) mod n_windows`。逐轮、逐old懒枚举，每个old/new identity最多访问一次；每old最多遍历一圈。记录真正访问过的identity和原始窗口列表hash，不能只记录最终输出。
4. 推荐 **scout visits≤256，source singleton physical validations≤256/epoch**。访问中exact old==new等静态不可用项计入visits；其余继续原BatchPhysicalValidator，不用廉价预测替代真实Gate B/C。达到256或穷尽该root候选元数据域即停止；不因结果不佳而加预算、不自动补全stratum、不重试。每次物理reject及原因保留。
5. 验证后的真实BBM/MBB分组各最多32、raw总量最多64，保持原stratum上限。每组按old分桶、依上述old访问次序逐轮取一项。桶内用原物理排序 `(-usable_lifetime, plane_gap, old_binding, new_terminal_pair, member_id)`。没有扫描/验证过的动作不得进入raw。
6. proposer仍物理screen实际raw。singleton总量16、BBM/MBB各8槽及原不足槽回填保持；组内先round-robin old binding。为改善终端覆盖，桶内优先选择与当前贪心cover集footprint不相交且old未重复的条目，再按原物理排序；无这样的条目时取原排序首项，但不将它放入cover集。跨两组维护同一cover集。最终重赋canonical index，组次序MBB后BBM，组内用确定的选择顺序；所有B1/B2/B3/B4共用。
7. 在上述16个singleton内，以首四个不同old的canonical代表作greedy anchors（不足四个取实际数）。每anchor从自己开始，按canonical index遍历其余member，仅追加old不同、footprint完全不相交的member，最多4个；每个prefix重排为严格递增canonical index。对size2/3/4的去重结构种子，size4先、再3、再2，同size按index tuple排序；每size最多4种，至多12个。只称resource-compatible，全部仍须原整批Gate B/C+whole-transition safety验收。
8. 16个singleton safety checks先执行；再验证种子；随后原W=4 beam扩展，经济评分不进入beam。所有种子和beam共用**184次joint validation/184次结构展开**上限，缓存同一index tuple的结果，任何条目不重复记预算。种子不获得额外免费验证。物理合法但单项网络不安全的prefix仍可扩展；不能以经济性或singleton safety失败直接删掉其组合。
9. 输出最多32个非HOLD。singleton合法项先保留；joint safe项按size2/3/4每轮取一项，再round-robin余量；同size仍用原 `(-min_usable,-sum_usable,index_tuple)` 排序。最终排序仍为 `(batch_size,index_tuple)`，HOLD始终首项；rollout上限33，所有controller使用同一个pool。batch1消融使用同样16个singleton来源，禁止种子/联合扩展，最多17个HOLD+singleton分支。

所有budget depletion都作为覆盖信息记录，不当作物理不存在。整批资源检查、actual BBM/MBB、tx drain、strict ready<end、事件顺序、whole-transition STRICT_CONNECTED、评分和HOLD exact ties不变。禁止跨root缓存mutable状态；本草案不要求任何cache。

## 预算依据与不确定性

W4、raw32/32/64、singleton16/8+8、M32、184/184、rollout33沿用待审批数字，没有按最终J增加。新增256选择为64输出预算的4倍，同时给80个old约3轮元数据探查机会；拒绝率高时可能输出少于64，不能保证填满或每个old都进入最终16。

这里的80仅是原primary occupancy band的上限：320个终端、每链接占2端，occupancy≤0.5对应K≤80。原K0列表仍含96/120/160，共12个K，本草案绝不删掉它们；它们的完整结构审计另行保留，不能以runtime256 cap代替uncapped库存。审计K160时256次只有一整轮加96次，也不保证合法候选覆盖。

历史物理validator平均454.1976078/7980=0.05691699s；单纯按调用数算256次约14.571s。这只是旧K4状态的线性计数诊断，**不是新政策实测、wall upper bound或episode预测**。后续proposer screen≤64次；joint validation≤184次、每项最多4成员，另有内部transaction/event/safety开销；这些不能和source256混为一项总调用cap。B4的33个rollout成本也未测齐。

现有96h净资源提案中B4的平均零额外开销分配为135s/epoch；256的历史计数估计约占10.8%，留下推进、proposer、rollout和I/O预算，但没有证明总预算可满足。保持候选宇宙元数据的访问、排序与存储也要计费；禁止生成全old×new物理结果之后再声称只有256次scout。

供审批的替代方案：128次（64的2倍，80个old约1–2轮）、256次（推荐，约3轮）、512次（8倍，约6轮）。历史计数诊断对应约7.285/14.571/29.142s，都不是实测。必须在任何正式J比较前选定一个，并按预声明计算资源和结构覆盖标准验收；如果不合格，报告失败/遗漏并提交独立revision，不自动升级预算。

## 审批后必须新增的验收

先实现隔离政策，旧reference保留；新source/proposerhash和身份/顺序/hash均须单独封存。验证0/少量old、窗口空集、stratum不足回填、重复pair、epoch轮换、256访问停止、真实reject保留、whole-transition unsafe组合、unsafe singleton可扩展、各种budget耗尽、不同输入顺序、deterministic replay、live不变。

tiny oracle必须列出原raw域、scouted域、raw64、singleton16、seed/beam、最终pool逐阶段的exact覆盖和遗漏；不能要求bounded policy在任意图上召回所有size4或达到全局最优。预先有安全size2/3/4 witness的注册fixture应逐项检查是否保留，未保留要作为失败或明确遗漏按获批标准处理，不删fixture。

真实自然成本/结构探测点仍按预注册合同，不能因扫描结果或控制器表现换状态。必须分别报告old覆盖、新terminal-footprint覆盖、可找到的batch大小、预算内拒绝、未访问域及UNKNOWN。全部scout排除不等于全域无合法动作；不能算“完整搜索recall”。

最后重新执行新政策下B1/B3/B4共享pool公平性、tiny oracle、最终K*/5s/完整pool的serial8多epoch等价、当前全回归、实测完整预算和正式preflight。原194/523 PASS只证明现有代码；不会证明尚未实现的新政策。

审批的单个动作是：选定上述政策及scout预算，并接受其明确的bounded-search遗漏边界。仍需同时审定HF_K初始化/阈值、HF_SCIENCE、B2、42项矩阵和资源窗口。审批本文件不授权正式K*选择或42项性能实验，也不把旧草案/FAIL改为PASS。
