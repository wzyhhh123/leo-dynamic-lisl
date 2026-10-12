# Gate A v0.3：synthetic-TLE / SGP4 / WGS72 / TEME

当前使用状态：用户已接受现有 pilot/common-mode audit 进入 Gate B；absolute TEME orientation 不阻塞当前 satellite-only 研究。见 [当前使用决议](./GATE_A_CURRENT_ACCEPTANCE.md)。下述原始检查保留为诊断，不改历史数据。

本文件替代 v0.2 的 TwoBody/J2000 几何验收要求。技术栈统一为冻结TLE→Python SGP4→TEME；不恢复平行TwoBody或STK强制交叉验证流程。

运行：

```powershell
python tools/analyze_visibility.py
```

输入是首个720星pilot（600秒、21时刻），输出新建 visibility 时间戳目录，原pilot保留。

1. 核验pilot各文件hash与TLE来源hash。
2. 验证共同epoch恢复的Walker目标几何，ID/plane/slot及SSC映射，单位、epoch、TEMEOfDate。
3. 从同一TLE独立实例重复生成所有pilot状态，比较数组完全一致。
4. 对258840个无向卫星对做30秒扫描、局部极值和根细化，并以15秒扫描复核；不只扫描snapshot已有边。
5. 保存连续可见区间与首尾截断标签，保留切触不确定区间和不稳定pair。
6. 抽取plane 0–3 / 0–5作为160/240星子集；状态、ID和诱导可见区间直接复制母资产，逐项audit。不增加wrap边、不重新传播。
7. 报告观察时长、完整寿命、截断数量、采样距离、plane-gap和boundary/interior时间加权degree。

重要：现有pilot的合成TLE来自旧初始定义。TEME目标偏差必须显式报告；严格目标不通过不妨碍保留pilot，也不允许通过放宽阈值把它改标成目标通过。是否另生成严格TEME目标TLE是后续资产决策，不覆盖pilot。

球形地球半径6378.137 km，5000 km仅为diagnostic cutoff。数值收敛验证不是连续无遗漏的数学证明；没有FOV、端口或LCT硬件range冻结，没有业务和控制算法实验。


## Common-mode audit update

See [COMMON_MODE_AUDIT_CN.md](COMMON_MODE_AUDIT_CN.md). Absolute element errors are dominated by a common rigid rotation; exceeding 0.001 deg alone does not establish structural distortion or require rebuilding TLEs. Existing thresholds and historical results remain unchanged.

