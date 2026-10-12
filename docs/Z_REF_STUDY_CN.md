# Z_ref construction study（4-plane / 160 星）

本 study 使用已接受的 0–600 s continuous visibility asset，在 t=0 构造 traffic-agnostic reference topology。固定部分是每个轨道面的前后邻居 ring。动态候选允许所有可见 inter-plane pair，但排序优先 adjacent-plane；terminal assignment 双边、确定性，每端最多 D1/D2 各一次，无平行卫星对链路。

没有自动冻结最终 Z_ref。

| 方案 | dynamic links | 端口占用 | idle terminal | 有空闲端口的卫星 | projected MBB candidate | dynamic bridges |
|---|---:|---:|---:|---:|---:|---:|
| sparse connected | 3 | 1.875% | 98.125% | 100% | 100% | 3 |
| medium occupancy | 80 | 50% | 50% | 67.5% | 41.88% | 0 |
| relative dense | 120 | 75% | 25% | 50% | 14.33% | 0 |

稀疏方案仅用 plane 0–1、1–2、2–3 各一条链，因此三条动态链全是桥，且出现6个 articulation node；它保留最多MBB资源，但自然失效敏感性最高。

中等方案的相邻面链数为28/26/26，平均动态度1.0，无桥或 articulation。boundary/interior端口占用分别35%/55%。它在冗余和空闲端口之间较平衡，但本轮不据此直接选择。

相对稠密方案三个面间各40条链，平均动态度1.5，无桥或 articulation。boundary/interior端口占用分别50%/83.33%，projected MBB candidate 降至14.33%，说明“更多初始链”会明显挤压后续 MBB 机会。

距离均值的中位数分别约280.01、639.08、934.84 km。所有入选链在 pilot 内均持续到600 s且全部右截断，因此只能写“在观察窗内可维持”，不能写真实 lifetime=600 s，也不能做自然 expiry 排名。5000 km仍是上游诊断 cutoff，不是 hardware range。

完整 terminal bindings、距离、remaining lifetime、bridge、articulation、plane-pair和boundary/interior统计在当前 Gate C 输出的 `z_ref_study.json`。后续人工冻结 Z_ref 前，还需完成hardware标定和更长窗口的expiry sensitivity。
