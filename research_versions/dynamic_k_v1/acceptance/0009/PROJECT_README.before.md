# Dynamic LISL v2

这是当前独立研究目录。日常只需要看三个入口：

1. `docs/README.md`：文档导航和当前结论。
2. `tools/check_gate_d2.py`：当前最新验收入口。
3. `configs/current.json`：当前有效资产与状态的机器索引。

## 当前状态

| Gate | 状态 | 说明 |
|---|---|---|
| A | ACCEPTED_FOR_CURRENT_USE | relative Walker/SGP4/candidate/visibility满足当前satellite-only研究；absolute TEME orientation记录为common-mode offset |
| B | PASS | 双dynamic-LCT terminal state machine，34项测试 |
| C | PASS | simplified parametric terminal model：RTN、D1/D2 mounting、双端FoR、terminal-pair interval、lifetime、BBM/MBB与Z_ref |
| D0 | PASS | fluid traffic、MCF normalization、queue/in-flight、CommonRouter、objective与drain合同已冻结 |
| D1 | PASS | 固定G_ref上的traffic→routing→service→queue→propagation→delivery内核通过 |
| Detailed PAT/tracking/link budget | OUTSIDE C v1 | FoR与setup数值为sensitivity-only；5000 km仍是diagnostic cutoff |
| D2 | PASS | scripted Gate B/C transition 已接入 dynamic routing/service/queue/in-flight/delivery；小型解析 fixture 与 160 星 pilot 通过 |
| E–G | NOT_STARTED | 没有 topology controller、matching、MPC 或 RL |

## 运行

在本目录的PyCharm `(pytorch)` 终端：

```powershell
python tools/check_sgp4.py
python tools/check_gate_b.py
python tools/check_gate_c_simplified.py
python tools/check_gate_d1.py
python tools/check_gate_d2.py
```

当前通常只需运行最后一条。每次验收都会新建带时间戳的`outputs/`目录，不覆盖历史。

## 目录

| 目录 | 作用 |
|---|---|
| `src/dynamic_lisl/` | 当前实现 |
| `tests/` | Gate A/B/C/D1/D2确定性测试 |
| `tools/` | 少量可直接运行的入口 |
| `configs/` | 当前状态、合同和schema |
| `data/raw/sgp4_x720/` | 冻结合成TLE |
| `docs/` | 合同、设计、结果；先看其中README |
| `outputs/` | 运行证据 |
| `archive/` | 历史备份，日常不用看 |

根目录`provenance.json`只是项目最初拷贝记录；当前状态以`configs/current.json`为准。旧sender-only production executor没有被修改或引用。
