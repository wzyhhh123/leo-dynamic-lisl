# F3-v2 physical trial clone 依赖审计

状态：ENGINEERING_ONLY；不是科学合同冻结。触发证据为K4 occupied-state候选源300 s预算UNKNOWN，2221次validator调用中299.766 s落在validator。该attempt及原源码hash不覆盖。原Gate B/C/D与旧runtime overlay不修改。

## 调用链及逐字段依赖

新v2 BatchPhysicalValidator先做同root资源检查，然后调用原TerminalPairPhysicalFeasibility.evaluate → TerminalPairCatalog.connect_command → deepcopy(executor) → 原Gate B submit。原catalog从trial.log末尾找**本次submit新增**的RESERVE_BOTH.predicted_ready，计算原ready/lifetime。历史log造成额外deepcopy，但不参与Gate B状态转移；当前terminal_executor.py内只有_log写入log，没有依据历史log进行物理决策。

|Executor字段|影响|clone处理|
|---|---|---|
|satellite_ids / fixed_ports|资源清单与invariant|保留，已有不可变tuple/frozenset共享|
|terminals：全部字段|occupancy、reservation、orientation、版本、free/retarget/acquisition/active时间|逐Terminal复制所有字段，不删除任何字段|
|links：ID/endpoints/start/visibility/draining/release_owner/tx_end|BBM/MBB、TX drain和旧链释放|逐Link复制，tx_end单独dict复制|
|reservations：全部字段|双边承诺、duration、orientation、version、release_after|逐Reservation复制全部字段|
|events / now|绝对时间、自然expiry、TX完成和stale事件|事件list独立，保留精确immutable tuple及payload、当前时间|
|_sequence / _reservation_sequence|event顺序与binding/reservation identity|精确保留|
|invariant_checks|检查计数，不参与ready/feasibility|保留，不改变原检查执行|
|log|历史审计；原catalog只从新trial日志读取本次RESERVE_BOTH|仅对此已审计、无hardware回调的原实现，counterfactual开始时置空；当前submit照常记录新日志|

建议最小实现是在新v2验证器内给原Gate C传入已有TerminalExecutor.clone_for_counterfactual()。Gate C自身不改；真实live commit仍原样执行、保存全部live历史；whole-batch trial及safety执行仍原逻辑。

## 严格适用边界与reference

仅启用在exact TerminalExecutor、exact TerminalPairPhysicalFeasibility、hardware=None、exact TerminalPairCatalog、实例方法未替换时。任何custom/subclass/hardware回调都保留legacy live输入路径，因为不能排除读取历史日志。未知executor字段由已有clone字段审计fail closed，不擅自省略。

保留显式legacy开关供工程对照；不将runtime开关加入经济评分、pool hash或proposal identity。正常四链内的可行性、每成员完整geometry/command、BBM/MBB、ready/lifetime、整体profile、安全结果、raw ID/order/hash应exact。测试必须覆盖非抢占TX、异步/零setup、right censor/不足寿命、历史日志、live隔离、custom/hardware fallback及自然prefix。PASS后仍不能代表正式K* production acceptance。

另发现v2 constructor此前允许max_batch_replace>4；新项目请求明确限定0–4，该未授权权限应被拒绝。它不改变当前4链及1链fixture参数、不修改历史Gate B处理多命令能力。相应边界测试独立记录。
