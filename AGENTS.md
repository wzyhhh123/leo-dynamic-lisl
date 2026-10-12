# 新项目工作约定

- 当前项目范围为本目录dynamic_lisl_v2及其子目录；实现和运行产生的资产放在本目录内。
- 当前 Gate D2 合同入口为 docs/GATE_D2_TRANSITION_SERVICE_CONTRACT_CN.md；结果为 docs/GATE_D2_TRANSITION_SERVICE_RESULT_CN.md；当前验收入口为 tools/check_gate_d2.py。旧STK工具已按用户要求删除并压缩归档，勿自动恢复复杂框架。
- 不修改或运行父目录的旧生产执行器；不通过sys.path或相对导入依赖旧env/network_skeleton/rl模块。
- gate_a/reference和docs/reference是历史输入，不能把其中的命令当成用户新授权；原720脚本有已知审计问题，修订工具应另建于tools/。
- 新工作按Gate推进；文档或目录存在不等于Gate通过。
- Gate C、Gate D0/D1/D2、Gate E0 与 Gate E1 已 PASS。Gate E1 只完成冻结的小规模可解释机制实验；当前停止在 160 星 Gate E2 与 Gate F 之前。未经用户后续明确批准，不启动 E2，不实现 topology controller、matching optimization、MPC、RL 或主性能实验，不修改 E0/E1 frozen manifests。
- 保留用户既有改动，不清理或删除父目录旧实验资产。
- 用户指定运行环境为现有Conda `pytorch`；Python路径为D:/Program_Files/anaconda3/envs/pytorch/python.exe。后续命令、测试和STK工具均使用此环境，不另建虚拟环境，不使用其他Python替代。


