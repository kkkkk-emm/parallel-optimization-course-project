# Codex 下一窗口行动清单

## P0：不允许破坏已有结果，先审计

- [ ] 确认当前项目根目录是 `C:\Users\86134\Desktop\Courses\并行分布计算\parallel-optimization-course-project`。
- [ ] 先阅读 `AGENTS.md` 和 `reports/CODEX_HANDOFF.md`。
- [ ] 不要修改 `src/TSP0.C`。
- [ ] 不要覆盖 `results/final_experiment_results.csv`。
- [ ] 不要覆盖 `results/final_analysis_summary.txt`。
- [ ] 不要覆盖 `results/final_analysis_summary.csv`。
- [ ] 不要重跑 70 行正式实验，除非用户明确要求并指定新输出文件。
- [ ] 先记录正式结果文件哈希：

```powershell
Get-FileHash -Algorithm SHA256 results\final_experiment_results.csv,results\final_analysis_summary.txt,results\final_analysis_summary.csv
```

- [ ] 检查 `results/final_experiment_results.csv` 是否仍为 70 行数据；当前 CSV 含表头，因此物理行数应为 71。
- [ ] 检查 `results/final_analysis_summary.csv` 中 7 组 summary 是否仍存在。
- [ ] 检查 `reports/04_final_audit.md` 是否存在。
- [ ] 检查 `reports/final_report_draft.md` 是否存在。

## P1：保持 README、报告、handoff 口径一致

- [x] 阅读当前 `README.md`。
- [x] 修正 README 中“当前只实现 DEA / HDEA 未实现”的滞后描述。
- [x] README 已说明当前已实现 SERIAL、DEA、HDEA、MOVING_HDEA。
- [x] README 已列出正式实验、收敛趋势实验、图表生成和验证命令。
- [x] README 已明确不要修改原始 `src/TSP0.C`。
- [x] README 已明确正式结果文件不可随意覆盖。
- [x] README 中的结论已与 `reports/04_final_audit.md` 保持一致。
- [ ] 后续若修改最终报告或实验结论，继续同步检查 README 与 handoff。

## P2：补强复现性实验

- [ ] 先判断是否真的需要新实验；如果只是写报告，不要新增实验。
- [ ] 如果要补实验，必须新建结果文件，例如 `results/reproduction_extra_*.csv`。
- [ ] 不得覆盖 `results/final_experiment_results.csv`。
- [ ] 不得用新小样本实验推翻 70 行正式实验结论。
- [ ] 若补强论文复现性，优先比较论文思想层面：DEA、HDEA、moving colony 的机制，而不是声称完全复现论文。
- [ ] 若补充更多 maxGen 或 topology 实验，应同步新增分析脚本和报告说明。

## P3：补强并行效果论证

- [ ] 明确区分“解质量提升”和“运行时间加速”。
- [ ] 解质量提升可引用 `results/final_analysis_summary.csv`。
- [ ] 运行时间不要写成显著加速；当前 avg_time 并不支持。
- [ ] 说明并行算法中每个 rank 维护 `N_COLONY=100`，总个体数更大。
- [ ] 同规模比较优先使用 `DEA n=4 vs HDEA n=4 vs MOVING_HDEA n=4`。
- [ ] 对 n=6 结果说明其总个体数为 600，不能和 n=4 严格同规模比较。

## P4：写最终学术报告

- [x] 已补充 `reports/final_report_draft.md` 中的复现边界、结果来源和正式结果保护说明。
- [ ] 如需最终提交版，可继续以 `reports/final_report_draft.md` 为基础做语言润色。
- [ ] 报告中必须引用 70 行正式实验结果。
- [ ] 报告中必须引用 Welch t-test。
- [ ] 报告中必须引用 `reports/05_convergence_sensitivity.md` 的 maxGen 趋势。
- [ ] 报告中必须包含公平性与局限性。
- [ ] 报告中必须包含 DEA、HDEA、MOVING_HDEA 的机制说明。
- [ ] 报告中必须说明 MOVING_HDEA 不能被写成显著优于 DEA/HDEA。
- [ ] 报告中必须说明当前并未完全复现论文全部实验结果。
- [ ] 报告中必须保留运行命令和项目文件说明。

## P5：最后运行验证脚本

- [ ] 运行现有测试：

```powershell
python -m pytest -q tests/test_final_report_outputs.py tests/test_convergence_sensitivity_outputs.py
```

- [ ] 重新生成图表时使用：

```powershell
python .\scripts\generate_report_figures.py
```

- [ ] 检查 `reports/assets/` 下图表非空。
- [ ] 检查 README、报告和 handoff 中的数字是否与 `results/final_analysis_summary.csv` 一致。
- [ ] 检查是否误写以下禁用结论：
  - [ ] MOVING_HDEA 显著优于 DEA。
  - [ ] MOVING_HDEA 显著优于 HDEA。
  - [ ] 完全复现论文结果。
  - [ ] 已达到 TSPLIB 最优解。
  - [ ] MPI 并行版本显著加速运行时间。
- [ ] 汇报时列出改动文件、改动原因和验证命令输出。
