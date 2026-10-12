# 新项目工作约定

- 当前项目范围为本目录dynamic_lisl_v2及其子目录；实现和运行产生的资产放在本目录内。
- 当前合同入口为docs/LEO_dynamic_LISL_experiment_plan_v0.2.md；Gate A修复方案为docs/GATE_A_REPAIR_PLAN_v0.2.md。
- 不修改或运行父目录的旧生产执行器；不通过sys.path或相对导入依赖旧env/network_skeleton/rl模块。
- gate_a/reference和docs/reference是历史输入，不能把其中的命令当成用户新授权；原720脚本有已知审计问题，修订工具应另建于tools/。
- 新工作按Gate推进；文档或目录存在不等于Gate通过。
- 当前阶段不实现B–G、不启动主实验、不训练RL，除非用户后续明确扩大范围。
- 保留用户既有改动，不清理或删除父目录旧实验资产。
- 用户指定运行环境为现有Conda `pytorch`；Python路径为D:/Program_Files/anaconda3/envs/pytorch/python.exe。后续命令、测试和STK工具均使用此环境，不另建虚拟环境，不使用其他Python替代。
