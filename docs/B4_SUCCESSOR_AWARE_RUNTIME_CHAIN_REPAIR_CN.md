# Final successor-aware runtime chain repair

本轮只修改 production preflight 的 `runtime_chain_valid()` 及其只读验证辅助模块、专项测试和验收记录入口。B4 branch、8-worker scheduling、routing/service/Q/I/D、horizon/cadence/top-K 与实验 manifest 均不修改。

历史 runtime overlay 按既有顺序验证 parent。链尾等于当前源码 hash 时保留原 PASS 行为。不同则调用 `tools/runtime_successor_chain.py`，只读取精确登记的 registry；当前生产允许的 registry 是 `configs/b4_executor_compatibility_successor_v1.json`，其文件 SHA-256 固定为 `e3ea7f5ef62ecbd3d329dbc66095abfad14a5f3042de84a094df4f89076eeec9`。不通过 glob 搜索授权，不自动接受其他文件。

每条 successor 必须满足 exact file、parent 与前一步 cursor 相同、授权 status/gate、registry canonical hash 与文件 hash、evidence 文件 hash、evidence 的 H_old/H_new 和科学语义声明、支持的 multi-epoch exact-equivalence PASS。生产 executor 额外继续使用已存在的完整 bootstrap 验证（包括唯一逆向补丁恢复旧源码 hash）。多级链必须显式提供逐级 hash-pinned registry，跳链和反序拒绝；不自动授权未来版本。

失败原因包括 UNREGISTERED_SUCCESSOR、CURRENT_HASH_MISMATCH、PARENT_HASH_MISMATCH、MISSING_GATE_EVIDENCE、GATE_NOT_PASS、BROKEN_SUCCESSOR_CHAIN、REGISTRY_HASH_MISMATCH。实际链与原因进入 preflight 的 `runtime_successor_chain_checks`，可审计。

本轮使用新的 `outputs/b4_final_compatibility_<timestamp>`。先完成 runtime-chain、checkpoint、telemetry、evidence-persistence、multiprocessing 测试，再执行 0/2/4/6/8/10 s 的新 serial-vs-8-worker 对照，随后 CLI full regression 与 P1 preflight。生产 overlay 只在全通过后生成，并登记历史 chain、已授权 executor registry、当前源码 hashes、新 multi-epoch 证据、full regression 和 preflight 证据。旧 FAIL 目录逐文件 hash 验证，原样保留。

本设计文件不代表最终验收 PASS。最终状态以本轮 acceptance report 为准；registered P1/P2/RL 不启动。
