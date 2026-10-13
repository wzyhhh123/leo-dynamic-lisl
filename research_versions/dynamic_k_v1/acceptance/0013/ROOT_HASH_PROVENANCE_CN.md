# N4-P0D：原始根指纹溯源

本轮结论是 `STOP_ROOT_BINDING_MISMATCH`。原0011根的完整 native 状态不可恢复：`ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE`。本轮定位了影响指纹的审计日志顺序差异，但不能证明这是0012或整个原始根不匹配的唯一原因。业务守恒根因仍为 `UNRESOLVED`。

## 保护与执行范围

开始前，独立版本起点 `ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691`、0012锚 `e77bf7624a4ac505e0dc52d77d79f6a2dcb45c240d3494d8fffe1119d3040aae`、0001–0012父链及6105个研究文件全部校验PASS，无未登记变更。历史5810文件基线、202排除项及旧README例外均沿用封存机制。

只执行一个 `0013_NEW_DIAGNOSTIC_ATTEMPT_01`，调用原0011构造器推进至t=3。没有提交N2 ADD/DROP/REPLACE/HOLD控制动作，没有运行预测分支，没有枚举catalog合法动作。本构造器加载2742条完整物理目录作为原绑定输入；加载输入不等于开展2742次候选诊断。初始零setup Connect仅为原构造器所定义的初态初始化，不是本轮新增控制动作。随后所有比较均读取已保存JSON。

## 原始指纹的真实来源

来源是0011 `failure_diagnostic_attempt02.py` 的 `main`，不是0012的构造记录，也不是旧B4。调用链如下：

1. `controlled_cost.stage_manifest(c23f188e...)` 逐字节核对0011实施manifest与依赖。
2. `controlled_cost.real_fixture` 调用0011 `workflow.setup`，加载原N3工程fixture及N1a/N1b/N2绑定。
3. `tests/test_n3_baselines.py:real_fixture(full_catalog=True)` 加载160星固定边、2742条Gate C终端窗口、原SGP4/TLE及硬件几何；创建模板，不进行候选遍历。
4. 新建相同160星TerminalExecutor，初始Connect：`X0_1/D2—X1_1/D1`，有效截止600秒，retarget/acquisition均0。初始化后从t=0真实ACTIVE计费。
5. 创建ObservedD2Engine，固定边来自z_ref，每条有向服务边容量1,000,000 bit/s；commodity分别为 `f_bg: X0_1→X1_1` 和 `f_hot: X0_10→X1_10`。传播使用原SGP4距离提供器。
6. trace为[0,8)的200,000/400,000 bit/s和[8,20)的200,000/1,200,000 bit/s。TA=20、评价T=30只是PILOT_ONLY。`wrap`构造原DeliveredFluidEvaluator和AtomicTopologyController，然后一次 `live.advance_to(3.)`。
7. attempt02先调用 `before=causal_view(live)`；`diagnostic`再调用causal_view取得当前观察、构造PERSIST ForecastInput，再调用make_sanitized_root。后者验证N2/物理绑定、提取已观察历史前缀、生成预测trace、再次causal_view并净化deepcopy。**被记录的root SHA是净化前live的view SHA，不是t=6失败状态、预测结果、forecast SHA或一个native checkpoint的文件SHA。**
8. 原程序在root生成后提交ADD并推进，在t=6 N1a验收拒绝。此后捕获的JSON年龄账本虽停留t=3，已经过ADD提交时的同时间结算。

原0011与HandleReaderLease路径封存的records逐字段相同，二者root SHA相同。此事实不证明跨Python进程重构一致。0012在run_diagnosis.py第41行先断言再保存，未保留实际SHA或hash原文；本轮不会补写或猜测0012实际指纹。

## 初始化绑定与业务历史

源文件、0011原始失败证据、12项修订链及物理文件的完整路径/字节数/SHA详见 `historical_evidence_inventory.json` 和 `actual_root_summary.json`。所有登记输入本轮均与封存文件一致，包括z_ref、完整terminal_pair_intervals.jsonl、hardware_gate_c_simplified_v1.json、SGP4 manifest/hashes/constellation.tle，以及N1a/N1b/N2/N3和P0实施绑定。

新诊断真实trace的规范字节SHA为：

`195625b48e0b1ff817d77a12732c00a88a1238b7e1a746025388ebfbb5576e87`

这是**本轮按封存构造器生成的trace SHA**。原0011失败JSON中的trace已经是净化预测trace，不能当作原live真实trace。没有原t=3 native checkpoint，原进程的真实trace对象/独立原文件SHA标记UNVERIFIABLE；源码与历史注入前缀是可核对证据。

本轮物理内容摘要SHA `0bdc19777053c1763f7dd367aadf59409ff3d5f225fbe7f6cb7ba4541836ea33` 与0011保存的物理摘要精确相同。PERSIST输入为start=3、horizon=6、end=9、当前200,000/400,000 bit/s，forecast SHA `66061c9bc91a8b6af7903cbb898b101081b02621f8f48f92038da54d66ef0da1` 与0011相同。历史前缀SHA本轮为 `bd36dc338830410efae2e8421cd5b90977857e03c175b18794c2fa7f31273b3f`；原值缺少独立保存，但0→3完整观察前缀逐字段相同。

原D2事件循环保留真实微步、传播agenda、队列排空边界和同时间settle；没有把事件强行对齐决策周期。原N1a首先推进/验收，成功后N1b.consume推进年龄游标。本轮0→3保存的43个观察记录与0011前43个记录逐字段相同，含真实连续注入率、服务率、到达率、传播排程、各节点/edge的before/after。22项timeline和2项route_state_events截至t=3也相同。其他未匹配时间字段的事件日志不能以空过滤结果声称一致。

t=3已知标量逐键相同：A=1,800,000，D=1,768,782.232853443，Q=0，I=31,217.767146556987 bit。FIFO的MD、arrived、delivered、delivered_original_moment、queue、flight、sent_mass、shift、closure_audit及nodes/commodities/now/scale这13个保存字段逐字段相同。这些局部一致不建立完整根等价。

## 根hash的精确规则

未改写的 `runtime/n4_p0.py:causal_view/encode`：

- 从 `engine.business_state()`取除trace、boundaries、boundary_index、delay、router、executor之外的所有实例字段；ObservedD2Engine的business_state本身排除age_observations。
- 加入terminal_snapshot、完整terminal_events/terminal_history、energy账本全部vars、age账本全部vars、receipts、physical_sha256和delay_class。
- None/str/bool/int/float直接保留；Fraction变为有理数字符串；Path为posix字符串；dataclass先asdict；dict变成按键repr排序的键值对列表；list/tuple/deque保持原顺序；set/frozenset按repr排序；数组tolist；普通对象变为type类名及fields。不能从该编码无损恢复所有Python类型，尤其tuple/list、Fraction/string和dataclass/native对象。
- `json.dumps(encode(state), sort_keys=True, separators=(',', ':'), allow_nan=False)`；默认ensure_ascii=True，无尾换行；`payload.encode()`为UTF-8。SHA-256只覆盖这段state_json字节。CurrentObservation在payload形成之后计算，独立返回，不是hash输入。
- 真实未来业务trace及其未来边界排除；已承诺的物理/传播事件仍保留。ForecastInput模式/窗口/速率和observed_prefix SHA是另外绑定，不直接加入根payload。

新hash原文文件 `actual_root_hash_preimage.json` 为1,368,252字节，保留精确原文，重新按原字节核算与实际SHA一致。首次断言前先写入该文件及actual_root_summary，再进行严格expected==actual比较。

## 首个可定位差异及证据等级

旧期望：`ba301c6b0d92b96b8490fe28b24322e254377aea01adffd0c368653daa3f01f6`

本轮实际：`06f3803e0c74ca9ba4a45a04ac5efada773ad988e044f7323083cc3421fc2adb`

最早已定位差异是年龄账本roundoff_audit零基索引4，时间精确有理数 `2554160564200857/576460752303423488`，约0.004430762292133393秒：旧日志先记录X0_1→X1_1/f_bg的I核验，新日志先记录X0_10→X0_9/f_hot的I核验。两条业务均在该时刻存在；这里变的是审计遍历/追加顺序，非业务到达顺序。

同阶段315条审计项的**精确多重集相同、列表顺序不同**。原N1b `_check_state`使用未排序的 `set(expected[kind]) | set(raw[kind])` 遍历，`_roundoff`按遍历顺序append；causal_view又把全部roundoff_audit列表原序写入payload。因此该差异确实改变hash原文，是强证据的指纹敏感字段差异。没有执行第二个根、排序回写、拼接并重新尝试根hash或搜索seed。

本轮Python3.9.21，hash_randomization=1，PYTHONHASHSEED未设置；标记文件保存当前环境及进程hash探针。原0011实际进程hashseed/探针未记录，不能据当前进程信息证明原种子。未发现这条构造调用链使用随机业务生成；非确定性set迭代为明确源代码风险，但不能声称已经证明整个hash不匹配只由seed造成。

## 同一绝对时刻不等于同一操作阶段

旧失败年龄快照cursor=44、roundoff_audit=338、mass_error_bound=`10978471/2251799813685248`；新动作前根cursor=43、315条、bound=`3600151/1125899906842624`。原Atomic.submit在真实命令提交后调用 `advance_to(engine.now)`，即仍在t=3追加SCHEDULE、消费年龄观察，再做FINAL及REPORTED_DELIVERY核验。原第43号观察是t=3的SCHEDULE，未发射传播事件、old/new service rates相同。

旧尾部23条由22条FINAL及1条REPORTED_DELIVERY组成，时间均3秒；绝对误差和=`3778169/2251799813685248`。**只作离线算术参考**：旧bound减此和精确等于新bound；未向旧或新账本写回。原审计前315项与新列表是精确排列关系。故cursor/日志长度/bound的额外差异有明确的操作阶段解释，不应当误诊为原根丢失业务。保留初次混阶段比较为age_mixed_stage_comparison_attempt01.json，最终diff披露阶段校正。

能耗账本已推进t=6，样本截至t=3还包含ADD产生的SETUP项；它与动作前根不相同，不能以旧t=6驻留时间还原原t=3账本。进一步离线核对：旧terminal log严格早于t=3的8项与本轮完整根历史精确相同；能耗严格早于t=3的初始样本相同；旧t=3样本额外含2个RETARGETING/预约终端。graph_event_sequence、route_changes和terminal_event_sequence按各自真实时间字段核对严格早于t=3的前缀，均为空且相同，仅证明该范围无记录。详见terminal_event_and_energy_prefix_evidence.json。根终端状态、预约、links、完整事件agenda及所有能耗历史，没有同阶段完整原文供逐字段校验，均标记UNVERIFIABLE。

## 分类及限制

| 类别 | 结论及边界 |
|---|---|
| A 业务/物理输入 | 登记原字节无变化；物理与forecast摘要相同；原live真实trace完整对象未保存。 |
| B t=3网络状态 | 已保存A/Q/I/D、观察前缀、timeline和route_state_events一致；完整native网络状态不可验证。 |
| C FIFO/能耗/年龄历史 | 13项年龄字段一致；额外结算项有阶段解释；完整原t=3能耗账本不可验证。 |
| D 事件/观察顺序 | 实际服务观察前缀一致；舍入核验日志顺序确实不同；原进程seed不可验证。 |
| E hash/非科学元数据 | 日志排列差异且原编码保留顺序，确认存在指纹敏感差异；不是完整根等价声明，也不能证明排他性根因。 |
| F 证据不足 | 原hash全文/native checkpoint缺失；0012 actual hash缺失，无法逐字段归因该轮。 |

age.queue/flight/MD、状态游标、误差envelope属于计费状态；roundoff_audit的内容支持误差审计，其追加列表顺序是证据元数据，但原hash将它一并覆盖。terminal_history、timeline等也兼具审计作用；不能简单删除它们、排序后替代旧锚，或把当前摘要宣布成等价原根。

本轮未授予N4-P0/N4-P0R Engineering PASS，未解决t=6业务守恒问题。后续决定见独立ROOT_REPLAYABILITY_DECISION_CN.md。
