# Gate C core framework 验收结果

状态：

- **Gate C core transition framework = PASS**
- **Hardware calibration = PENDING**
- 完整状态：`CORE_PASS_HARDWARE_PENDING`

21项 acceptance tests 在同一环境连续运行两遍，全部通过；代表性 transition traces 完全一致。实际4-plane/160星资产完成三种 Z_ref study，但没有选择最终方案，也没有执行主性能实验。

关键行为验证：

- 2 s BBM分区：STRICT拒绝，BOUNDED(5 s)接受，BOUNDED(1 s)拒绝，T_max=2 s按`≤`接受。
- MBB使用真实空闲端口，新链LINK_UP后才释放旧链，active/admit全程连通，两种policy均接受。
- 两条边单独删除安全、同刻删除断网；profiler只在同刻事件组处理完成后采样。
- DRAINING桥边可使active connected而admit disconnected。
- setup expiry会abort；无恢复、自然expiry不安全、超界outage均返回独立机器原因。
- existing pending transitions与new batch联合回放；非法proposal不被validator修复。
- allocator顺序无关、无双占用；子集不能借外部卫星。

证据目录：`outputs/gate_c_20260921T092620_617747Z/`。

| 文件 | 内容 |
|---|---|
| `report.json` | C0–C4/C6分项状态和21项测试 |
| `z_ref_study.json` | 三种160星构造的完整bindings与统计 |
| `representative_transition_traces.json` | Gate B真实事件回放和图时间线 |
| `rejection_outage_statistics.json` | 拒绝原因fixture与outage统计 |
| `inputs.json` | 接受的几何、Gate A/B、hardware config及code hash |
| `hashes.json` | 本次所有输出SHA256 |

复现命令：

```powershell
python tools/check_gate_c.py
```

本轮停止在Gate C。未实现traffic、queue、routing、matching optimization、MPC、RL或160/240/720性能比较。

