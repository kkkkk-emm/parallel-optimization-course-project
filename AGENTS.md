# AGENTS.md

本文件是给新 Codex 窗口使用的项目级工作规范。除非用户明确修改要求，否则后续所有工作都应遵守。

## 项目定位

这是并行分布计算结课作业项目，主题是基于老师提供的 TSP 串行进化算法，使用 MPI 实现并比较 DEA、HDEA、MOVING_HDEA 三类并行进化算法。

当前项目根目录：

```text
C:\Users\86134\Desktop\Courses\并行分布计算\parallel-optimization-course-project
```

## 不可破坏规则

1. 不得修改 `src/TSP0.C`。它是老师提供的原始代码，必须保留为原始参考。
2. 不得覆盖已有正式实验结果，除非用户明确要求并指定新文件。
3. 所有新增实验必须输出到新的结果文件，不能覆盖 `results/final_experiment_results.csv`。
4. 不得无理由重跑 70 行正式实验。
5. 不得为了让结论更好看而改算法、改 CSV 或删数据。
6. 不得伪造实验结果、图表或统计结论。

## 正式结果引用规则

修改报告或 README 时，必须优先引用：

```text
results/final_analysis_summary.csv
results/final_analysis_summary.txt
reports/04_final_audit.md
```

如果涉及 maxGen / 收敛趋势，还必须引用：

```text
results/convergence_sensitivity_summary.csv
results/convergence_sensitivity_summary.txt
reports/05_convergence_sensitivity.md
```

## 性能结论规则

任何性能结论必须区分：

1. 解质量提升：路径长度更短，`global_best`、`best`、`mean` 更低。
2. 运行时间加速：`elapsed_sec` 或 `avg_time` 更低。

当前实验支持“并行进化结构改善解质量”。当前实验不支持“MPI 并行版本显著加速运行时间”。

## 论文复现表述规则

不得声称“完全复现论文结果”，除非后续新增实验能够严格支持。

可以写：

- 参考论文实现了 DEA、HDEA 和 moving colony HDEA 的核心思想。
- 当前 MOVING_HDEA 实现对应 ring moving colony。
- 当前实验在 `pcb442.tsp` 上观察到 moving colony 的均值优势趋势。

不能写：

- 完全复现论文全部实验。
- moving colony 在所有实例上最优。
- MOVING_HDEA 显著优于 DEA/HDEA。

## 统计结论规则

当前正式实验的关键结论：

- 所有被比较的并行配置相对 SERIAL 均达到 `p<0.05`。
- `MOVING_HDEA n=6 groups=3` 的 mean 最低，为 `427890.600`。
- `DEA n=2` 的单次 best 最低，为 `415765`。
- MOVING_HDEA 相比 DEA/HDEA 均值更低，但 t-test 不显著。

涉及显著性时，必须查 `results/final_analysis_summary.csv/txt`。

## 实验文件规则

新增实验命名建议：

```text
results/<purpose>_results.csv
results/<purpose>_summary.csv
results/<purpose>_summary.txt
reports/<NN>_<purpose>.md
scripts/run_<purpose>.ps1
scripts/analyze_<purpose>.py
```

新增实验必须：

- 写清楚参数；
- 写清楚 seed；
- 写清楚是否替代正式实验；
- 默认不替代 `final_*` 结果；
- 失败时停止，不静默跳过。

## 文档修改规则

修改报告时：

1. 先读 `reports/04_final_audit.md`。
2. 再读 `reports/05_convergence_sensitivity.md`。
3. 若修改最终报告，读 `reports/final_report_draft.md`。
4. 所有数字必须来自已有 CSV/summary 或明确重新计算。
5. 不要只改一个地方造成 README、报告、handoff 口径不一致。

## 验证规则

修改后必须说明：

1. 改了哪些文件；
2. 为什么改；
3. 如何验证；
4. 是否触碰正式实验结果；
5. 是否存在仍需人工检查的问题。

推荐验证命令：

```powershell
python -m pytest -q tests/test_final_report_outputs.py tests/test_convergence_sensitivity_outputs.py
```

检查正式结果是否被误改：

```powershell
Get-FileHash -Algorithm SHA256 results\final_experiment_results.csv,results\final_analysis_summary.txt,results\final_analysis_summary.csv
```

## 新窗口推荐首读文件

1. `AGENTS.md`
2. `reports/CODEX_HANDOFF.md`
3. `reports/CODEX_NEXT_ACTIONS.md`
4. `reports/04_final_audit.md`
5. `reports/05_convergence_sensitivity.md`
6. `reports/final_report_draft.md`
