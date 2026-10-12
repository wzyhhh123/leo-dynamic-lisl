# F3-v2 条件运行入口与共享执行管线

状态：ENGINEERING_ONLY。此文件不是科学合同冻结、K*选择或正式运行授权。

## 共同内核与权限

`episode_execution.py`从原engineering episode提取共同编排，继续调用同一`BatchCadenceAdapter`和Gate D2 service/event内核。工程入口只接受ENGINEERING-* ID；条件正式入口另行检查FROZEN合同、完整42项manifest、K0/K1、当前工程验收、实测预算与独立人工授权。没有新建第二套物理/队列模拟器或修改旧Gate B/C/D。

`matrix_execution.py`严格按原run次序执行独立episode，对公平配置组检查完整canonical初态相同。失败先保存原状态、invariant、partial metrics、timelines、candidate audit及hash，再STOP；不继续、不重试、不覆盖attempt。CENSORED可合法继续。仅完整注册矩阵全部得到合法结果后才加载全部seal并生成paired analysis，删失点不按截断J排名。工程矩阵不生成论文paired analysis/result seal。

`registered_runtime.py`从显式、hash绑定的物理/OD/traffic/topology配置构造现有v2模块。K4初态保留原单条预建立事件顺序；K*必须绑定正式K1并校验exact K、双端Gate C和连通性。B4每episode复用persistent 8-worker对象，分支仍从当前root构造；cleanup在成功存证前执行，失败即execution failure。没有自动P2/RL路径。

仅支持已实现的`UNCAPPED_PHYSICAL_SCAN_THEN_STRATIFIED_OUTPUT_CAPS_V1`，它仍有已报告的覆盖/费用问题。新diversity/scouting若尚未实现验收则入口明确拒绝，不回退到旧source、engineering witness或另一预算。完整K0/K1、K*和生产source合同仍需审批。

## 只读验证

`epoch_validation.py`在经济评分前只读验证raw BBM/MBB/total output caps、singleton/joint pool/rollout/expansion/validation上限、共同root、terminal资源独立性、HOLD/batch权限与proposal identity/order/hash。每项保存observed与limit，失败先存输入和原始子项再进入失败持久化。它不按J替controller换action，不把raw输出cap误称physical evaluation次数上限。

capacity tolerance绑定到现有`max(1e-9,C*1e-12)`；load-aware权重绑定原E0 registry，time tolerance继承原router。没有新增调参权或容差。全部实际读取的runtime输入/代码必须同时登记manifest与逐run provenance；独立manifest/approval批准后按文件SHA保护，避免循环hash。

操作wall limit为合作式检查：source/controller返回及episode结束后检查，不是强制中断正在运行函数的硬超时。超限是execution failure，不能写成CENSORED；保留原状态并停止。最终资源准入仍需实测最坏阶段费用和worker-liveness，不能用此检查替代计算预算。

## 证据范围

focused tests覆盖真实tiny网络全部baseline顺序执行、与直接现有adapter的完整state chain相同、source失败、paired初态错误、cleanup失败、合法censor继续、历史attempt保护、authority/code/provenance篡改拒绝、继承参数及epoch预算/身份错误存证。临时目录FROZEN/授权schema样例是字面测试数据，未建正式runtime，绝不代表真实人工批准或K0/K1验收。

`tools/check_f3_v2_runtime_entry.py`仅执行固定tiny工程episodes，并在真实160星/K4/ρ=.5/t0构造B0/B1/B3/B4，完整canonical初态与既有构造器exact相同。自然检查不advance、不枚举candidate、不调用observe/rollout；原DRAFT正式CLI必须在建runtime前拒绝。该范围不能证明K*/5s/full pool多epoch等价、最终B4工程PASS或42项正式实验完成。

新attempt保存于`outputs/f3_v2_runtime_entry_<timestamp>/`，当前报告和全回归在进度checkpoint中精确链接并校验seal。历史attempt不改判；正式实验和整episode费用仍未完成。
