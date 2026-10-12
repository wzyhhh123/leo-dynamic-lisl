# Gate A 当前使用决议：接受为 Gate B 输入

用户明确接受当前 geometry pilot 与 common-mode audit 作为 Gate B 的几何输入。

**relative Walker geometry / SGP4 propagation / candidate & visibility consistency 已满足当前 satellite-only 研究使用要求。absolute TEME orientation 保留为 documented common-mode offset，不作为当前 Gate B 的阻塞项。**

接受的资产：

- `outputs/geometry_20260921T053240_016088Z`
- `outputs/visibility_20260921T055451_308214Z`
- `outputs/common_mode_audit_20260921T061043_579554Z`

此决议新增于历史审计之上；不修改历史 gate_a.json、原始统计、阈值或 TLE，不重拟 TLE。机器记录见 `configs/gate_a_acceptance_v0.3.json`；当前入口状态见 `configs/active_geometry.json`。

接受范围仍为当前 satellite-only 几何使用；5000 km 继续是 diagnostic cutoff，不认证 LCT hardware range/FOV。Gate B 仅验证终端状态机，Gate C 及以后未由该决议放行。
