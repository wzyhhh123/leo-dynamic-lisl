# N4-P0F 最小方案与事件时钟审计

接缝可执行。采用新模块 `runtime/n4_p0f_events.py`，定义ExactEventClock及ExactObservedD2Engine/ExactBareD2Engine；由显式构造与独立VariantBinding选择数值语义。原src/dynamic_lisl/transition_service_orchestrator.py、ObservedD2Engine、Gate B/C、N1a/N1b/N2/N3/P0全部保持原字节，不对全局运行时类作monkeypatch。

完整最小源码差异见MINIMAL_SOURCE_DIFF.json，包括原源码行号、原始字节SHA及每方法unified diff。新模块只覆盖七个相互关联的方法，原业务积分、队列/在途更新、数值闭合、服务容量分配、路由算法、FIFO和能耗计算继续继承原实现。

## 门限的作用与修改

| 原入口 | 原条件作用 | 隔离变体 |
|---|---|---|
| _settle_propagation_rate_events | now+1e-12把稍晚传播率事件提前生效 | 仅time_s<=now结算 |
| _next_time外生边界游标 | now+1e-12可能提前越过业务边界 | 仅boundary<=now递增 |
| _next_time候选过滤 | now+1e-13丢弃可表示的短正区间 | 保留所有value>now |
| advance_to终止 | until−1e-13可在终点前停止 | while now<until，逐步检查prior<now<=until |
| _step/settle_current_time几何刷新 | now+1e-12提前刷新并跳过近邻刷新点 | 仅refresh<=now，检查每次加法严格前进 |
| _microstep拓扑记账标记 | now+1e-12提前标记terminal/action到期 | 标记精确到期，Gate B本身仍使用原严格事件时间 |
| _apply_due_actions脚本推进 | now+1e-12提前提交脚本 | 仅action.time<=now；实际新N2场景不使用旧脚本 |

1e-12在service rate差异判断、到达率数值归零、D2相对守恒容差等地方具有**不同单位/用途**，不作为时间门限删改。原1e-15导数判断、state_tol/abs_tol、1e-6 bit严格业务验收也均未变。

同一timestamp的传播率事件仍按原RateArrivalEvent的time/sequence heap顺序弹出，再按edge/commodity叠加。微步顺序保持传播率结算→真实终端事件/脚本→图与路由更新→服务重新分配/传播排程。跨节点同时合流的FIFO比例混合规则不变。Gate B的setup/TX/到期时钟不改变。

_next_time在微步完成后选择最小严格未来候选；真正同时发生的事件已在当前微步处理，不创建零时长积分。可表示的正时间间隔即使低于1e-13也保留。若浮点加法无法产生未来候选，原NO_FORWARD_EVENT或新严格前进检查拒绝；不改用人为nextafter强推进或补造业务。保留原百万事件上限，刷新加法停滞则显式拒绝。终点到达后调用原式同时间settle，不漏掉恰在评价边界的事件。

原引擎run()另有早排空/1e-13逻辑，是历史Gate业务运行入口；它不属于本次固定T预测执行入口，也未被推广为新修复评价器。修复验证只使用N1a固定时域advance_to及N2真实动作；没有把旧run()宣传为已经获得极短区间保证的接口。旧schedule_action对过去1e-12的接纳兼容判断保持原样，新N2不使用该入口；新的时钟结算不会提前执行其未来动作。通用历史run/任意脚本接口扩展不在本轮授权内。

## 观察与验收接缝

local_observer.py从封存0012只读Auditor生成，包装只安装到被诊断的engine/queue/in_flight**实例**上，退出上下文恢复。捕获原实际调用一次，Reference Fraction/Decimal从不写回状态。完整状态快照在实例包装退出后保存；干净根重建进一步证明观察没有改变根。

diagnostic_measure.py独立继承N1a FixedHorizonEvaluator，仅把相同measure结果送至实例capture_and_validate：先排他写出原测量输入，然后调用未修改的validate_measurement。业务数值、公式、容差、断言顺序不变。该评价子类只在两个诊断分支显式选用，不修改任何全局函数。

## 解析验收与边界

7项测试全部通过：

- 正负传播率事件不可提前；相邻1秒IEEE数1.0000000000000002与1.0000000000000004形成真实正区间。速率2^40 bit/s的精确积分为1/4096 bit。
- 同时正负事件与多边叠加积分13bit，所有事件消耗且终态到达率归零。
- 一ulp终点推进恰好到达，负时间请求拒绝。
- 连续短注入1→1+2^-40、2^30bit/s，已交付0.0009765625bit，FIFO按真实时间分布核算传播时延2^-20秒，无中点近似。
- 两跳每跳0.5秒尾流：10bit全部交付，年龄积分10bit·s，平均1秒。
- 明确从交付计数扣除1bit模拟真实丢失，原1e-6 bit BUSINESS_CONSERVATION断言拒绝；不修改阈值以通过。
- 小于旧epsilon的几何刷新正区间正常推进，无停滞、漏事件或倒退。

这些有限测试不宣称任意规模/平台的通用数值误差定理。正式科学参数保持null，固定seed与短时数值仅为PILOT_ONLY工程条件。
