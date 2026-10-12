# N3 配对工程 K 状态时间线

仅 ENGINEERING_TEST_ONLY。表格压缩相邻且所有展示状态一致的重复行；相同时间戳的不同真实微步状态保留，不代表额外驻留区间。原始完整序列在 engineering_examples.json / paired_metrics.json。显示数值四舍五入，原始 binary64 值和 N1b 精度/误差界保留在 JSON。

## paired_K0_ADD_delivery_idle_DROP

REACTIVE_DYNAMIC_K（T=4.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|0|0|2|2|
|1|1|0|0|0|
|3|0|0|0|0|
|4.0|0|0|0|0|

实际控制动作：0.0s ADD, 0.5s HOLD, 1.0s HOLD, 2.0s HOLD, 3.0s DROP。

STATIC_HOLD（T=4.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|0|0|0|0|
|4.0|0|0|0|0|

实际控制动作：0.0s HOLD, 0.5s HOLD, 1.0s HOLD, 2.0s HOLD, 3.0s HOLD。

## paired_REPLACE_MBB_spare_terminals

REACTIVE_DYNAMIC_K（T=5.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|1|0|2|2|
|1|1|1|0|0|
|2|1|0|0|0|
|3|0|0|0|0|
|5.0|0|0|0|0|

实际控制动作：0.0s REPLACE/MBB, 0.5s HOLD, 1.0s HOLD, 2.0s HOLD, 3.0s DROP, 4.0s HOLD。

STATIC_HOLD（T=5.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|1|0|0|0|
|5.0|1|0|0|0|

实际控制动作：0.0s HOLD, 0.5s HOLD, 1.0s HOLD, 2.0s HOLD, 3.0s HOLD, 4.0s HOLD。

## paired_no_demand_DROP_draining_energy

REACTIVE_DYNAMIC_K（T=4.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|0|1|0|0|
|2|0|0|0|0|
|4.0|0|0|0|0|

实际控制动作：0.0s DROP, 0.5s HOLD, 2.0s HOLD, 3.0s HOLD。

STATIC_HOLD（T=4.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|1|0|0|0|
|4.0|1|0|0|0|

实际控制动作：0.0s HOLD, 0.5s HOLD, 2.0s HOLD, 3.0s HOLD。

## paired_resource_constrained_REPLACE_BBM

REACTIVE_DYNAMIC_K（T=5.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|0|1|1|2|
|1|0|0|2|2|
|2|1|0|0|0|
|4|0|0|0|0|
|5.0|0|0|0|0|

实际控制动作：0.0s REPLACE/BBM, 0.5s HOLD, 1.0s HOLD, 2.0s HOLD, 3.0s HOLD, 4.0s DROP。

STATIC_HOLD（T=5.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|1|0|0|0|
|5.0|1|0|0|0|

实际控制动作：0.0s HOLD, 0.5s HOLD, 1.0s HOLD, 2.0s HOLD, 3.0s HOLD, 4.0s HOLD。

## real160_natural_SGP4

REACTIVE_DYNAMIC_K（T=4.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|0|0|2|2|
|0.4|1|0|0|0|
|1.25|0|0|0|0|
|4.0|0|0|0|0|

实际控制动作：0.0s ADD, 0.2s HOLD, 0.4s HOLD, 1.25s DROP, 2.0s HOLD, 3.0s HOLD。

STATIC_HOLD（T=4.0 s）

|t (s)|K_admit|DRAINING 连接|SETUP 终端|预约 SETUP 终端|
|---:|---:|---:|---:|---:|
|0|0|0|0|0|
|4.0|0|0|0|0|

实际控制动作：0.0s HOLD, 0.2s HOLD, 0.4s HOLD, 1.25s HOLD, 2.0s HOLD, 3.0s HOLD。
