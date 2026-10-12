# Executor compatibility successor bootstrap

本 Gate 仅授权工程验收。registered P1/P2/RL 不启动；旧 FAIL attempt 不重写。

H_old 取自 `b4_production_multiprocessing_20261002T124551_332297Z/report.json`，为 `f879ea45dd006769108c32205ed111c53f5f2a3c83e7098bdbf0220415b73a44`。H_new 从本次源文件记录。唯一差异是 `_checkpoint()` 安全读取可选 sink；按字节反向替换后必须恢复 H_old，否则立即失败。

独立入口为 `tools/check_b4_successor_bootstrap.py`。先运行 checkpoint、telemetry 科学等价和 multiprocessing 测试，再运行新的 0/2/4/6/8/10 s 对照，最后执行所有仓库测试。每个失败保留完整 traceback；只有明确命中 runtime seal 中源码哈希等值断言的失败可标为 LEGACY_HASH_EXPECTATION。其他失败或跳过测试均阻止授权。此阶段不调用最终 production preflight 作为启动前提。

候选通过后先写 `CANDIDATE_SUCCESSOR_VALIDATED` 证据，再新建 `configs/b4_executor_compatibility_successor_v1.json`。校验要求 registry canonical hash、parent/successor、证据文件 hash、多 epoch PASS、实际源码 hash 和唯一逆向补丁全部一致。缺少 registry 或链条任何一项不成立均拒绝。此登记不等于 production integration PASS。

随后从独立目录按顺序重做最终兼容性验收与多 epoch 对照；全部通过后才能生成 production overlay。最终报告位于本次 `outputs/b4_successor_bootstrap_<timestamp>`；文件存在或本设计文档不代表 Gate 已通过。
