# Codex 新窗口交接包

## 1. 项目目标

本项目是“并行分布计算”结课作业，目标是基于老师提供的 TSP 串行进化算法和 `pcb442.tsp` 数据集，使用 MPI 进行并行优化，并通过实验说明并行化后的搜索结果相比原始串行基线更好。

当前项目根目录：

```text
C:\Users\86134\Desktop\Courses\并行分布计算\parallel-optimization-course-project
```

请注意：旧上下文中曾出现过 `...\结课作业` 路径，但当前实际工作目录已经整理为 `parallel-optimization-course-project`。

## 2. 当前已经实现的算法

| 算法 | 状态 | 说明 |
|---|---|---|
| SERIAL | 已实现 | 可复现实验串行基线，支持命令行参数、seed 和 CSV 输出。 |
| DEA | 已实现 | MPI 分布式进化算法，每个 rank 一个子种群，ring migration。 |
| HDEA | 已实现 | 分层分布式进化算法，group 内 local migration，group 间 individual global migration。 |
| MOVING_HDEA | 已实现 | 基于 `groupMembers` 的 ring moving colony HDEA，全局 moving 只更新逻辑分组。 |

## 3. 核心源码文件

| 文件 | 作用 | 注意事项 |
|---|---|---|
| `src/TSP0.C` | 老师提供的原始串行代码 | 不得修改；作为原始基线和代码说明来源。 |
| `src/tsp_serial_fixed.c` | 第 0 步修复版串行程序 | 用于路径、输入格式和 smoke test。 |
| `src/tsp_serial_exp.c` | 正式实验用串行基线 | 支持 `input maxGen seed output.csv`。 |
| `src/tsp_mpi_dea.c` | MPI DEA 实现 | ring migration，发送本地 best，替换本地 worst。 |
| `src/tsp_mpi_hdea.c` | MPI HDEA 实现 | `groupId/localId` 划分 group，local/global 两级个体迁移。 |
| `src/tsp_mpi_moving_hdea.c` | MPI MOVING_HDEA 实现 | `groupMembers` 逻辑分组，global moving colony 不发送个体。 |

## 4. 核心脚本文件

| 文件 | 作用 |
|---|---|
| `scripts/run_experiments_final.ps1` | 编译并运行最终 70 行正式实验。 |
| `scripts/analyze_results_final.py` | 从 `final_experiment_results.csv` 计算统计量和 Welch t-test。 |
| `scripts/run_convergence_sensitivity.ps1` | 运行 maxGen=1000/3000/5000 收敛趋势补充实验。 |
| `scripts/analyze_convergence_sensitivity.py` | 分析收敛趋势实验，计算 improvement 和排序。 |
| `scripts/generate_report_figures.py` | 从 summary CSV 生成最终报告图表 PNG。 |
| `scripts/smoke_test_serial.ps1` | 串行版本 smoke test。 |
| `scripts/smoke_test_dea.ps1` | DEA smoke test。 |
| `scripts/smoke_test_hdea.ps1` | HDEA smoke test。 |
| `scripts/smoke_test_moving_hdea.ps1` | MOVING_HDEA smoke test，含 moving 后 local migration 对象变化验证。 |

## 5. 正式实验结果文件

| 文件 | 说明 |
|---|---|
| `results/final_experiment_results.csv` | 最终正式实验原始结果，70 行数据；当前 CSV 含表头，因此物理行数为 71。 |
| `results/final_analysis_summary.txt` | 最终正式实验统计表、Welch t-test 和结论文本。 |
| `results/final_analysis_summary.csv` | 机器可读的正式统计结果和 t-test 结果。 |
| `results/convergence_sensitivity_results.csv` | maxGen 敏感性补充实验原始结果，36 行。 |
| `results/convergence_sensitivity_summary.txt` | 收敛趋势补充实验分析文本。 |
| `results/convergence_sensitivity_summary.csv` | 机器可读的收敛趋势统计结果。 |
| `reports/04_final_audit.md` | 最终报告前审计，说明文件完整性、统计一致性、结论边界。 |
| `reports/05_convergence_sensitivity.md` | 收敛趋势与 maxGen 敏感性补充实验说明。 |
| `reports/final_report_draft.md` | 当前最终报告初稿。 |

## 6. 当前最终实验配置

正式实验配置为：

```text
7 组算法配置 × 10 个 seed = 70 行结果
```

7 组配置：

| algorithm | nproc | migration_interval | local_to_global_ratio | num_groups |
|---|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 0 | 0 |
| DEA | 2 | 100 | 0 | 0 |
| DEA | 4 | 100 | 0 | 0 |
| HDEA | 4 | 100 | 5 | 2 |
| HDEA | 6 | 100 | 5 | 3 |
| MOVING_HDEA | 4 | 100 | 5 | 2 |
| MOVING_HDEA | 6 | 100 | 5 | 3 |

10 个 seed：

```text
12345, 22345, 32345, 42345, 52345, 62345, 72345, 82345, 92345, 102345
```

## 7. 关键统计结论

以下数据来自 `results/final_analysis_summary.csv` 和 `results/final_analysis_summary.txt`。

| algorithm | nproc | groups | best | mean | std | avg_time |
|---|---:|---:|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 430142 | 438472.100 | 4628.069 | 2.868900 |
| DEA | 2 | 0 | 415765 | 430223.600 | 6134.273 | 3.562728 |
| DEA | 4 | 0 | 424318 | 430458.000 | 3508.236 | 3.594641 |
| HDEA | 4 | 2 | 426732 | 431573.700 | 4266.830 | 4.466030 |
| HDEA | 6 | 3 | 426245 | 430320.900 | 2496.949 | 4.596891 |
| MOVING_HDEA | 4 | 2 | 424632 | 429704.000 | 3745.679 | 5.076744 |
| MOVING_HDEA | 6 | 3 | 423208 | 427890.600 | 3380.349 | 4.892686 |

主要 t-test 结论：

| comparison | p-value | 结论 |
|---|---:|---|
| SERIAL n=1 vs DEA n=2 | 0.003512 | DEA n=2 显著优于 SERIAL。 |
| SERIAL n=1 vs DEA n=4 | 0.000435 | DEA n=4 显著优于 SERIAL。 |
| SERIAL n=1 vs HDEA n=4 groups=2 | 0.002782 | HDEA n=4 显著优于 SERIAL。 |
| SERIAL n=1 vs HDEA n=6 groups=3 | 0.000242 | HDEA n=6 显著优于 SERIAL。 |
| SERIAL n=1 vs MOVING_HDEA n=4 groups=2 | 0.000218 | MOVING_HDEA n=4 显著优于 SERIAL。 |
| SERIAL n=1 vs MOVING_HDEA n=6 groups=3 | 0.000022 | MOVING_HDEA n=6 显著优于 SERIAL。 |
| DEA n=4 vs MOVING_HDEA n=4 groups=2 | 0.647810 | MOVING_HDEA n=4 均值更低，但差异不显著。 |
| DEA n=4 vs MOVING_HDEA n=6 groups=3 | 0.112945 | MOVING_HDEA n=6 均值更低，但差异不显著。 |
| HDEA n=4 groups=2 vs MOVING_HDEA n=4 groups=2 | 0.311721 | MOVING_HDEA n=4 均值更低，但差异不显著。 |
| HDEA n=6 groups=3 vs MOVING_HDEA n=6 groups=3 | 0.085502 | MOVING_HDEA n=6 均值更低，但差异不显著。 |

## 8. 可以写进报告的结论

可以写：

1. 已实现 SERIAL、DEA、HDEA、MOVING_HDEA 四类实验程序，其中后三类为 MPI 并行进化算法。
2. 在当前 70 行正式实验中，所有被列入 t-test 的并行算法配置相对 SERIAL 均取得显著更低的平均路径长度。
3. `MOVING_HDEA n=6 groups=3` 在正式实验中取得最低平均路径长度 `427890.600`。
4. `DEA n=2` 取得最低单次 best `415765`。
5. MOVING_HDEA 相比 DEA/HDEA 具有均值优势趋势，但没有达到 `p<0.05` 显著性。
6. maxGen 补充实验显示 `maxGen=1000` 尚未充分收敛，正式实验是统一迭代预算下的相对比较。
7. 当前项目可以说明“并行进化结构改善了解质量”，但不能简单说“运行时间显著加速”。

## 9. 不能夸大的结论

不能写：

1. 不能写“完全复现了论文结果”。当前只是实现了论文相关思想并在 `pcb442.tsp` 上做课程实验。
2. 不能写“MOVING_HDEA 显著优于 DEA”。
3. 不能写“MOVING_HDEA 显著优于普通 HDEA”。
4. 不能写“HDEA 显著优于 DEA”。
5. 不能写“MPI 并行版本显著加速运行时间”。当前实验中并行版本主要提升解质量，运行时间不一定更快。
6. 不能写“已经达到 TSPLIB 最优解”或“已经完全收敛”。
7. 不能把 3 seed 的 maxGen 补充实验当作主实验显著性结论。

## 10. 当前最大问题

| 问题 | 状态 | 建议 |
|---|---|---|
| 论文结果未完全复现 | 存在 | 报告中写“参考并实现论文思想”，不要写完全复现。 |
| 并行后解质量更好但运行时间不一定更快 | 存在 | 区分“解质量提升”和“运行时间加速”。 |
| README 口径 | 已更新 | README 已改为 SERIAL、DEA、HDEA、MOVING_HDEA 当前状态；后续修改报告时仍需同步检查 README。 |
| 实验公平性边界需要说明 | 存在 | 每个 rank 都有 `N_COLONY=100`，并行组总个体数更大。 |
| maxGen=1000 未充分收敛 | 已有证据 | 使用 `reports/05_convergence_sensitivity.md` 支撑边界说明。 |

## 11. 老师最新要求

老师最新要求可以概括为：

```text
要复现出来，并且加并行后效果要更好；报告越学术越高分。
```

对下一窗口的含义：

1. “复现出来”应理解为尽量复现论文算法思想和趋势，不要无证据声称完全复现论文全部结果。
2. “并行后效果更好”当前可以用 70 行正式实验和 t-test 支撑，重点是解质量更好。
3. “越学术越高分”意味着报告需要加强论文背景、算法机制、实验设计、统计检验、公平性边界和局限性讨论。

## 12. 下一步建议任务优先级

1. P0：先审计当前文件和正式结果，不要破坏已有 CSV、summary 和报告。
2. P1：保持 README、handoff、最终报告的算法状态和正式结果数字一致。
3. P2：若需要继续补强复现性实验，必须新建结果文件，不能覆盖 `final_*` 结果。
4. P3：继续保持“解质量提升”与“运行时间加速”的区别。
5. P4：按提交需要继续打磨 `reports/final_report_draft.md`，但不得扩大显著性结论。
6. P5：最后运行验证脚本，确认统计结果、图表和报告引用一致。

## 13. 建议新窗口优先阅读顺序

1. `AGENTS.md`
2. `reports/CODEX_HANDOFF.md`
3. `reports/CODEX_NEXT_ACTIONS.md`
4. `reports/04_final_audit.md`
5. `reports/05_convergence_sensitivity.md`
6. `reports/final_report_draft.md`
7. `results/final_analysis_summary.csv`
8. `README.md`
