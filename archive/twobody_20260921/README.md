# TwoBody 归档

本目录是 2026-09-21 用户要求迁移到 SGP4 时保存的历史快照，不是正式实验入口。

- outputs 内保存原场景、原报告、原星历，包括成功和失败记录。
- src/tools/tests/docs 是当时的实现与说明快照，不再维护为正式分支。
- archive_index.json 逐文件记录旧路径、新路径、SHA256；移动后的内容保持不变。
- 旧文件中绝对路径代表历史来源，不应据此从正式程序回退读取 TwoBody。
- 拟合迁移工具可以只读归档初始状态；冻结合成 TLE 后，正式重建只依赖 data/raw/sgp4_x720。
- 正式入口与状态以 ../../configs/active_geometry.json 为准。
