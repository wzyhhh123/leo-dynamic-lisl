# N1a 工程接口

此目录独立于历史生产代码，不选择拓扑动作或算法。结果为 `ENGINEERING_TEST_ONLY`，不构成科学性能结果或旧 Gate 验收。

`TerminalEnergyLedger(executor)` 在真实 t=0 状态创建；`capture(executor)` 消费新增完整 Gate B 状态日志并按相邻事件的时间差累加驻留时间；`metrics()` 返回四能耗态、五执行态、逐终端驻留时间、能量和拓扑时间序列。此低层接口只核算终端；联合测量须经下述评价器和校验器输出。

`EngineeringBinding(project_root, manifest_path, expected_manifest_sha256).verify()` 核对外部固定的候选实现清单摘要、版本起点、父修订、基线 seal、实现与合同/配置文件。候选清单绑定 0004，封存后由 0004 修订记录绑定整份清单和验收证据，避免结果和修订互相自引用。

`FixedHorizonEvaluator(engine, T_s=..., time_tolerance_s=..., energy_tolerance_J=..., business_tolerance_bits=..., evidence_binding=...)` 只接收真实 t=0 D2 引擎和 320 个动态终端。T 必须为显式有限正数且覆盖输入业务时域；没有正式默认 T。传入的三个容差也是工程输入，不写入未冻结科学参数。

- `advance_to(t)` 推进到不超过 T 的实际检查点，每次先核对绑定；返回经跨字段校验的检查点测量。
- `run()` 固定推进到 T，采用 D2 的 `advance_to`，不采用提前排空返回的 `run`。
- `clone()`、`checkpoint()`、`restore(checkpoint)` 同时保留引擎、终端事件游标、完整计费起点和累计驻留时间。checkpoint 是内存对象，不是磁盘 pickle 反序列化接口。
- `validate_measurement(result)` 对完整工程结果执行数值范围、逐终端/总驻留、能耗、业务守恒、完成标志、K/SETUP 计数及拓扑时间积分一致性检查。

K_admit 对应输出 `K_time_series[].K_active_admissible`，按双端真实 ACTIVE 连接计数；DRAINING 另计，SETUP 状态终端数与预约终端数允许重叠。`setup_connection_count` 统计已处于 RETARGETING/ACQUIRING 的不同预约连接；仅等待旧链释放的预约仍体现在 `setup_reserved_terminal_count`。相同时间戳只保留最终右侧状态，检查点本身不制造新的终端状态事件。

J_T 按业务事件时间线上的未加权 N=A-D 积分，包含 queue/in-flight；不沿用旧加权 objective。N_T 为实际队列与在途量之和。所有业务在输入时域结束后交付且剩余量在显式工程容差内，才报告 `all_offered_business_delivered=true`；此标志独立于是否正常到达 T。空输入的 R_del 为 1。年龄加权累计与 fluid 平均时延始终为 null，N1b 未实现。

工程测试使用现有 pytorch Python 和 `-B`。`acceptance/0004/run_n1a_acceptance.py` 是本轮一次性证据生成器，已封存的证据禁止覆盖。后续复测若需要新增持久证据，应在新修订下登记新证据目录；不要原地重写 0004。

限制：计费依赖受版本保护的 Gate B 完整事件日志，禁止中途清空/改写已消费日志或直接绕过执行器改动状态；违反时拒绝测量。完整初始状态与日志必须保留。此版本未接入生产 runner，未实现 N1b、N2 动作控制器或 RL。
