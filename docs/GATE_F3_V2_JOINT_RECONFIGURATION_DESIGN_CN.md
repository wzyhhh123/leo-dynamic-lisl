# Gate F3-v2-0 联合拓扑重构设计与仓库审计

**DRAFT_NOT_FROZEN；仅设计与静态审计，无生产实现、结构扫描或性能实验。**

本次 attempt：`outputs/gate_f3_v2_design_20261008T112538_143340Z`。5 s cadence 与每epoch最多4条REPLACE是待审批设计，不是最优参数。保留10 s名义horizon、真实事件驱动物理层、160星、外生0–240 s业务和600 s最大drain。目标为B4核心期刊论文，暂不MARL/PPO。历史F3-v1/K4、K0-v1 FAIL、K0-v1.1 DRAFT、A–E资产和8-worker overlay全部保护。

## 1. 实际代码能力与缺口

Gate B已有多个Reservation并发推进，`submit(commands)`先在transaction clone上逐条执行，任何失败不更新live，全部成功后执行同时间事件并一次更新live。Gate C公开接口仍是单terminal-pair，D2 `_apply_due_actions`也是逐条proposal。**不能将多个单动作依次schedule当成原子batch**：后一个拒绝时，前一个可能已经改变live状态。B1/B3和B4都使用同一single proposal set；旧F0 registry的implemented=false只是历史登记，不能用它判断现在代码未实现。

REPLACE流程为：物理evaluate中trial Gate B验证ready→transition profiler→regime policy→真实submit。Gate B `_connect`先检查terminal/old-release owner/parallel pair和ready，再创建bilateral reservation、target peer、版本，标记旧链DRAINING或MBB release_owner；MBB的旧链在新LINK_UP后drain。批次后面的命令能看到trial里前面的reservation，所以会拒绝冲突。事件可以并发，物理先后关系并未被并行计算取消。

旧B2是global accepted-command timer，首次没有hold阻塞，并非每条链LINK_UP计时。旧B4是root-action-only rollout，不是枚举未来多epoch action树。旧8-worker pool调度可继承，但任务只有一个record/spec、结果只有一个proposal_id；v2 batch payload/validator/clone都要重新验收，旧PASS不能代替新PASS。已登记overlay/registry/current代码与supporting evidence的hash关系仅做静态核对，详见runtime_provenance_audit.json。

| 模块 | 分类 | 当前真实实现 | v2影响 |
|---|---|---|---|
| terminal_executor.py | 可直接复用 | 真实多个 reservations/events；trial 顺序验证全体命令，全部成功后才替换 live __dict__。异常不提交。 | 不改内核；新增 v2 资源独立 batch adapter，不能把 submit 多命令能力当作网络级 batch safety 已完成。 |
| terminal_pair_intervals.py | 可直接复用 | 半开窗口、Gate B trial predicted_ready、严格 ready<end 和原 epsilon。 | 在同一 DECISION_ROOT 取各条 Connect，完整集合再 trial.submit；不是独立合法即联合合法。 |
| gate_c_simplified_feasibility.py | 需要新增接口 | 公开 evaluate 只接受一组 a/b/release_after，hardware hook 也是单 pair。 | 新增 BatchPhysicalValidator；保留每条 Gate C，并对整组 Gate B trial 校验。未建模卫星公共电源/热约束不额外声称硬件并发保证。 |
| transition_profiler.py | 可直接复用 | commands 本来是序列；在 clone 上 submit 后按真实事件组生成 active/admit graphs。 | 新 adapter 提供整个 batch 完成边界，包含 MBB release/旧 TX drain，不只用最大 new ready。 |
| operational_policy.py | 不应修改 | STRICT_CONNECTED 拒绝 partition_occurs；profile 的 partition 同时检查 active/admit。BOUNDED_OUTAGE 仍使用现有 2s 界。 | 原 policy reject-only，不根据经济分数补救或替换。新 Z_K* 继承 moderate policy 的选择单独待批准。 |
| production_candidate_source.py | 必须升级 | old_rows×terminal windows 的一换一 raw universe；拒绝 MULTI_OLD_BINDING_CONFLICT；32/32/64 caps。 | 独立 v2 source 可复用物理枚举规则/排序，输出 singleton resource footprint；不得沿用 v1 source identity 假称 batch identity。 |
| candidate_proposer.py | 必须升级 | 逐条 physical/safety pruning，然后 top16/8+8。 | 新增 shared structural joint proposer；single unsafe 作为 diagnostic，不自动证明联合 unsafe；所有可执行最终 batch 整体 safety 通过。 |
| baseline_controllers.py | 必须升级 | kind 仅 HOLD/REPLACE；只容纳一个 proposal_id。 | 新增 v2 HOLD/BATCH_REPLACE schema，ordered member IDs、batch ID、root hash；旧 dataclass 不改。 |
| baseline_controllers.py | 可直接复用 | 恒 HOLD，自然 expiry 仍执行；无需消费候选。 | 轻量 v2 类型 adapter，保留相同物理时间线，controller 权限不同于根本不执行物理。 |
| baseline_controllers.py | 必须升级 | 当前 last_accepted_switch_time 为全局时钟；无 per-link hold。 | 新增逐 old-binding elapsed-seconds eligibility；B2 基于 B1-v2，不混用 B3；H4/H8 历史不改。 |
| scientific_controllers.py | 必须升级 | B1 在理想单目标图上 argmin V_v2；B3 用单条 DeltaV×eta。 | 新增 B1/B3-v2 对共同 batch pool 的完整目标图重新算 snapshot；B3 定义 batch eta。 |
| scientific_snapshot.py | 可直接复用 | 路由重算、current local demands、equal_weight_fair_share 和 in-flight-only Psi=0，未 advance。 | 只新增 batch target_edges 构造/完整批次调用；保留 V_v2 数学与浮点规则。 |
| transition_service_orchestrator.py | 需要新增接口 | ScriptedProposal 单 proposal；逐条 evaluate/profile/submit，不能保证 batch 外层原子性。 | 新 v2 subclass 的 ScriptedBatchProposal/_apply_due_actions hook 一次 commit，外层 microstep 一次刷新图/路由/服务；旧 D2 内核源码不改。 |
| transition_service_orchestrator.py | 不应修改 | propagation settlement→executor events→due action→graphs/router→service；事件推进独立于控制。 | 通过 polymorphic due-action hook 接入；不连续 schedule 多个单动作伪造原子 batch。 |
| common_router.py | 不应修改 | distance/full_path/node heap 和 candidate<current deterministic tie。 | primary/robustness 条件内所有 controller 同 router；保留已有缓存生命周期。 |
| network_service_engine.py | 不应修改 | 既有静态 service reference；production 使用 transition-aware/E2 subclass。 | 不创建平行 simulator，不动 link capacity、allocator、Q/I/D 或 in-flight closure。 |
| controller_runner.py | 必须升级 | 显式拒绝 cadence!=2；每 epoch 消费单 proposal。 | 新增 v2 runner，5s nominal/兼容2s模式由不同合同驱动，旧 guard 不改。 |
| gate_f3_p1_execution.py | 必须升级 | 单 selected_proposal_id/action record；固定 Z_MODERATE 和 v1 hashes/manifest。 | 新增 v2 execution adapter/manifests/evidence writer，读取未来 K* 初态；不改旧 P1 或其 preflight。 |
| production_candidate_source.py | 必须升级 | 2s/240/600 guard 硬编码；600 无 decision。 | 新增 v2 5s policy：0..595；240 后真实 drain；COMPLETE 0.01bit 不变。 |
| forecast.py | 需要新增接口 | 强制 horizon=10；clone 替换 future trace；不读取真实 future phases。 | 新增 v2 effective-horizon forecast以支持595→600的5s截断；当前 lambda persistence 原理保留。 |
| rollout_controller.py | 必须升级 | 最多16 singleton；order/state/forecast hash共享；一次root REPLACE，未来不递归controller。 | 新 B4-v2 shared batch pool argmin真实 J_H；每个 branch root提交完整batch，仍 root-action-only。 |
| rollout_evaluator.py | 必须升级 | 单 ScriptedProposal，固定 advance t+10；单 action_result。 | 新 batch evaluator/result schema，多成员结果与整体 validity；H_eff边界相同，无terminal penalty。 |
| b4_branch_multiprocessing.py | 必须升级 | 调度pool可并行任意task数，但task/evaluator分派依赖一个record/spec。 | 新 v2 BatchBranchTask/payload dispatch；8-worker持久pool机制可继承但必须重新验收，不改旧runtime overlay。 |
| rollout_clone.py | 需要新增接口 | 仅已审计append-only历史record浅共享；其余及未知字段使用同一个memo deepcopy保持alias。TerminalExecutor另有字段白名单。 | 为新 subclass 的 batch queues、ledger/hold-age/readiness maps 单独 field audit；严禁跨branch/epoch共享 mutable state。 |
| f3_drain_continuation.py | 可直接复用 | D2 early return 1bit不等于F3 COMPLETE 0.01；真实 continuation直到边界。 | 换外层cadence，内层阈值/推进/守恒完全保留。 |
| b4_runtime_seal.py | 不应修改 | 旧 source hashes 和明确授权 successor/overlay 链。 | v2 是新科学合同，另建新code/evidence registry；不能借runtime successor许可改变科学动作。 |

具体函数与一基行号在repository_impact_matrix.json。2s guard位于controller_runner和DrainDecisionPolicy，P1 runner消费该policy；10s在forecast、rollout controller/evaluator、_finish断言和冻结合同。不得在旧文件原地替换这些常量。

## 2. 调度合同草案

周期点为0,5,…,595 s；最多120个可能点。每次先推进到实际时间并settle既有propagation与Gate B events，再得到右连续DECISION_ROOT，生成同一候选集，controller只读评价，记录POST_OBSERVE，原子提交选择的batch，再刷新graph/router/service得到POST_DECISION。要求DECISION_ROOT=POST_OBSERVE证明假设分支不改live；不要求PRE_CALL=DECISION_ROOT。

同时间戳保留Gate B `(time,priority,sequence)`：expiry0、TX_DONE1、LINK_DOWN2、retarget3、LINK_READY4。命令按共享singleton索引canonical顺序提交，编号/事件sequence确定；worker完成顺序不参与决策。原D2 microstep先结算已承诺传播，后terminal/action，最后router/service，不能把5s变成服务时隙。1.3s建链完成、7.25s失效等都在真实时间执行。

240 s时先观察新业务rate=0；240,245,…,595 s仅在unfinished>0.01bit时继续决策。真实drain可提前完成，D2 1bit early return不能当F3 COMPLETE。600 s结算物理事件后分类COMPLETE/CENSORED，不产生新decision；不clamp/drop/virtual drain。初始归一化alpha*、rho和traffic bytes沿用，不能按K*或当前拓扑重新算load。

**截止边界待批准：H_eff=min(10,600-t)。** 595 s统一预测5s至600，HOLD与所有batch同长度，不外推到605、不补terminal penalty、不延长Gate C资产。该规则需要新v2 forecast/evaluator adapter，因为旧实现硬拒绝非10s。名义10s不是已证明最优；最大horizon附近不代表完整physical lifetime。若不批准截断，须另选晚期决策规则并单独冻结，不能静默在两个规则间切换。

forecast仍current-rate persistence，root内部不产生未来主动控制。235 s的简单预测可能把当前rate延续到245 s，保持其非oracle性质；真实trace仍在240 s归零，240时的新预测为0。物理可知window/expiry可读，未来真实traffic/最终J不可读。当前几何刷新沿用E2/P1在起点和物理拓扑事件触发的惯例，不因5s controller cadence擅加刷新。

## 3. 资源独立批量动作

`A_t={REPLACE_r}`，0<=m<=min(4,K*)，m=0是HOLD。每条含具体old binding/new terminal pair与member ID；batch含decision time/frame、root hash、joint pool hash、成员序列和batch ID。BBM/MBB来自实际Gate B/C状态，不能controller自报。

对每条r定义footprint=old endpoints∪new endpoints，批次中不同footprint必须互不相交；可以共用卫星的不同终端，不允许共用同一terminal、old binding、reservation、release owner或非法satellite pair。MBB新端口在root时真实IDLE；BBM占用端口只属于自己的old binding，释放和ready由旧TX/retarget/acquisition实际决定。不支持借另一动作将释放的端口、终端交换链、同peer非法并行链或fixed port借用。

validate_batch只读同一个root，逐条Gate C取得窗口/command，整组Gate B trial.submit验证原子性，再profile整个组的真实event timeline与当前已有pending events，并应用原regime policy。必须看全过程而非最终图，也不能把两条独立合法误当联合合法。profile应覆盖所有new ready和选中old release/drain结束；MBB old TX可能晚于new ready，不能只取max(new ready)+epsilon。验证覆盖超出600时报告观察窗口不足，不把600称为自然失效。

验证失败拒绝整个batch；不会由safety删掉经济性差的成员或换更好候选。真实commit一次submit(commands)，失败无部分terminal/Q/I/D改变；commit不一致则证据持久化后STOP。原子的是“验证和接纳”，不是未来物理成功承诺：之后某个reservation因可见性abort，按原Gate B释放、版本检查处理，独立其他成员继续，不回滚已经发生的时间。

原moderate STRICT_CONNECTED判定来自profile的active/admit partition，sparse BOUNDED_OUTAGE仍为2s，不能随cadence改为5s。v2 K*主regime建议继承moderate policy，但该映射待人工批准；没有新增必须全天候连通或k-edge-connectivity硬约束。批量原子化和资源独立限制是新动作合同，需要批准。

固定K指一换一目标预算，无ADD/DROP；并非每一时刻active link count恒等K。BBM暂时减少、MBB暂时增加，自然expiry也可减少。现有内核不会把已自然消失的old link自动补回K。若论文要求真实active始终K，则与BBM和自然失效不相容，必须另立maintenance合同，不能本轮暗中实现。

## 4. shared joint search与B4范围

建议采用同一结构bounded beam：先共同singleton physical universe，再footprint/conflict剪枝，按递增singleton索引扩展至size4；按最小/总截断usable lifetime及canonical order做结构beam保留，完全不读traffic/Q/J/controller结果。单条network safety失败不自动证明组合失败；resource/physical有效但safety失败的prefix可在budget内扩展，最终可执行pool必须整体safety通过。

所有可执行singletons保留，然后按预注册的depth/结构顺序填充合法size2/3/4。pool预算必须至少容纳single预算，并给部分batch留位；不强制四条。exact member集合去重；只有satellite target graph相同但terminal/ready/release不同不得合并。pool在任何经济评价前固定canonical hash，B1/B2/B3/B4同root获得相同pool。

raw32/32/64、singleton16/8+8只是建议继承，全部待批准；beam width W、最大非HOLD batch M、validation/expansion caps、rollout E和operational timeout均留null，不能偷偷写死。16 singletons全部0..4组合有2517个，主规模禁止全部做10s rollout。B4只评价共同pool的HOLD+M，E必须>=1+M，并按pool order归并8-worker结果。

确定性count budget耗尽截断结构搜索并明确记录，不依据J拓展或缩小候选。真正wall timeout/worker错误不作为科学策略：只能明确operational HOLD并封存异常、STOP该性能attempt，不把未评价完整pool的run当科学COMPLETE/CENSORED。不能取先完成的branch，不因机器速度改变science。

## 5. K0依赖

K0-v1.1仍DRAFT，20snapshot/18-20等未被本任务改动。16个single legal replacements不能证明4个资源独立且joint-safe。建议K0-v1.2额外记录M_resource（conflict graph最大independent set）与M_joint（再加整体Gate B/C/safety）；它们不是terminal maximum matching同一问题。size2/3/4必须有certified witness或exact不可行证明，bounded搜索找不到仅为UNKNOWN。

记录BBM-only/MBB-only/mixed的联合兼容性、reservation/terminal/parallel/joint-connectivity冲突、capped runtime pool相对uncapped结构空间的损失。初态snapshot空reservation不证明运行中也可用4条。所有内容只读物理结构，不读J/Q/delivery/traffic。

建议先作为诊断；可选hard gate为某预注册snapshot比例存在safe size4，具体分子留null。它会偏向更密集K/更多spare-MBB资源并排除虽能m1-3控制的场景，不能自动把18/20或原K-selection标准替换掉。人工批准batch predicate后先验收validator，再执行获授权的K0-v1.2/K1；本轮未完整K0、未K* selection。

## 6. 验收、工作量与阻塞项

后续按V2-A调度→V2-B joint atomicity→V2-C并发资源/守恒→V2-D当前状态baselines→V2-E真实batch rollout/oracle/8workers→V2-F公平性→V2-G成本与新preflight。每Gate具体断言及FAIL/STOP在implementation_and_test_plan.json；任何真实mismatch、泄漏、历史修改或守恒失败先持久化再停止，不改tolerance。

tiny oracle仅6–10星、U<=8，最多163个size0..4组合；穷举验证完整joint legality、cardinality、conflicts、ties，量化beam遗漏和B3/B4各自best action。不能要求B3/B4通常选同动作，只在proxy确实精确的专门toy中要求一致。兼容模式m1/cadence2从同root/pool比较旧B1/B3/B4，但不预先承诺历史binary/hash相等；B2需专门legacy global timer模式。

最小代码路径：新v2 action/batch physical validator+service due-action hook+5s runner；shared structural joint proposer；whole-graph snapshot adapter/B3；batch rollout evaluator/forecast cap/B4；8worker batch task与精确clone审计；B1同pool；B2最后。旧Gate B/C/D源码、service allocator/router、v1controllers/runner/overlay保留，不再建第二套仿真。

估计core与结构前置18–29人日（不含长跑和返工保证）：shared executor4–6、shared pool+B3 3–5、B4+oracle4–6、B1 1–2、B2 1–2、K0/K1 3–5、最终engineering验收2–3；部分文档和K0准备可并行，validator必须先验收。以2026年12月中下旬投稿为目标：10月冻结/核心实现，11月初闭合正确性/K0-K1/preflight，11月单独授权结果与写作并行，12月初留复查修改。B2不阻塞核心B3/B4实验，但最终是否纳入鲁棒性要预注册。

待人工冻结清单：

- 5s cadence、max batch4的科学设计值（本轮只有草案）
- raw32/32/64、singleton16/8+8是否继承及结构排序规则
- beam width W、非HOLD batch budget M、结构expansion/validation caps、rollout预算 E>=1+M、operational timeout
- B3 batch eta=min(member eta) 聚合定义；不能由旧singleton合同自动推出
- 595决策的H_eff=min(10,600-t)统一截断；不延长资产
- Z_K* safety regime继承STRICT_CONNECTED的批准；现有active/admit实际判定不扩成新物理约束
- B2逐链接LINK_UP计时、初态age及H4/H8是否纳入最后鲁棒性
- K0-v1.1冻结／v1.2新增batch audit诊断与可选hard gate；K*与K1初态仍未知
- F3-v2实验grid/manifest/result seal需要另行预注册；旧F3-v1不授权v2性能运行

本轮只证明设计与静态审计交付完整，不证明batch implementation PASS或正式performance readiness。完成后STOP，等待人工审核和实施授权。
