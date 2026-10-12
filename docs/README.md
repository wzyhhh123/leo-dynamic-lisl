# 文档导航

当前 Gate D2 已通过，Gate E/F/G 尚未启动。日常优先阅读：

1. `GATE_D2_TRANSITION_SERVICE_RESULT_CN.md`：动态重构—网络服务耦合验收结果。
2. `GATE_D2_TRANSITION_SERVICE_CONTRACT_CN.md`：D2 图、事件、no-route、守恒和指标合同。
3. `GATE_D2_INTEGRATION_AUDIT_CN.md`：Gate B/C 与 D1 的接口审计。
4. `GATE_D0_TRAFFIC_QUEUE_ROUTING_CONTRACT_CN.md` 与 `GATE_D1_NETWORK_SERVICE_RESULT_CN.md`：冻结的 traffic/service 基础。
5. `GATE_C_SIMPLIFIED_CONTRACT_CN.md` 与 `GATE_C_SIMPLIFIED_RESULT_CN.md`：Gate C v1 最小物理合同与结果。
6. `GATE_A_CURRENT_ACCEPTANCE.md` 与 `GATE_B_RESULT_CN.md`：冻结的几何和双动态终端状态机。

`LEO_dynamic_LISL_experiment_plan_v0.3.md` 是此前完整实验框架；其中 traffic 的旧设想由 Gate D0 fluid contract 取代。带 v0.1/v0.2、RUN、REPAIR、reference、reviews 的文件是历史材料。

当前机器状态以 `configs/current.json` 为准；当前验收命令为 `python tools/check_gate_d2.py`。D2 只完成 scripted integration/correctness，尚未进入控制算法阶段。
