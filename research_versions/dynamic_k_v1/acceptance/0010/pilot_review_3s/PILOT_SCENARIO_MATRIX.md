# PILOT_SCENARIO_MATRIX — 3秒审阅修订

状态：PILOT_ONLY / 未执行预实验 / 人工修订决策周期为3秒。旧1秒草案原字节及哈希保存在 ../prior_pilot_drafts_1s 和 ../prior_pilot_draft_hashes.json，原文件未覆盖。

T=30 s，T_A=20 s，H=6 s，decision_cadence_s=3.0，epoch=(0,3,6,9,12,15,18,21,24,27)。所有四控制器共用该时间表；真实注入/传播/setup/释放仍按事件时间处理，不强行对齐。双端retarget各0.5 s，acquisition0.5 s，空闲ready=t+1 s。t0至t24的h=6 s，t27的h=3 s，预测均不越T。lambda_N=6 s，lambda_E=1000 bit·s/J。正式科学参数和正式周期/预算继续null。

主计划6场景×2MPC×10epoch×最多7分支=840分支；每个候选累计h=9×6+3=57 s，主预测上限4788 branch-s。敏感性额外24个MPC运行=1680分支/9576 branch-s；全部2520分支/14364 branch-s，真实运行24或48次的T仍30 s。这里仅预算，均未执行且本轮无运行授权。

保留六场景U-STABLE/U-SHORT/U-SUSTAIN/C-STABLE/C-SHORT/C-SUSTAIN；OD为f_bg:X0_1→X1_1，f_hot:X0_10→X1_10。背景200000bit/s，热点基础400000，短突发[8,10)为1200000，持续[8,20)为1200000。旧场景矩阵的完整2742行catalog、160固定环边、输入原字节哈希、U/C初态及小域保留规则全部不变。t8和t10突发边界不与epoch强制对齐。四臂仍为STATIC_HOLD/原N3 REACTIVE/MPC-ZERO/PERSIST，但四臂runner和预实验本轮不实现。

完整未变条目逐项继承对应旧快照，不覆盖原文；本修订只对周期、检查点、预算及本轮实施状态形成明确覆盖。
