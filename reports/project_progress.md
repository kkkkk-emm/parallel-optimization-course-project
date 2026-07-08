# 并行分布计算 TSP 期末大作业进展记录

## 1. 当前已完成

1. 完成第 0 步串行代码可运行性检查。
   - 保留原始 `src/TSP0.C`。
   - 新增 `src/tsp_serial_fixed.c`，修复原始代码中的硬编码路径、坐标读取格式和输出路径问题。
   - 验证 `data/pcb442.tsp` 可以被正确读取，城市数量为 442。

2. 完成第 1 步 MPI DEA 实现。
   - 新增 `src/tsp_mpi_dea.c`。
   - 每个 MPI rank 维护一个本地 `N_COLONY=100` 的子种群。
   - 每个 rank 独立进化，并每隔 `migration_interval` 代执行 ring migration。
   - 使用 `MPI_Sendrecv` 实现迁移，避免死锁。
   - rank 0 汇总各 rank 的最优结果并写入 CSV。

3. 完成第 2 步 SERIAL vs DEA 可复现实验。
   - 新增 `src/tsp_serial_exp.c`，支持固定 seed 和 CSV 输出。
   - 新增 `scripts/run_experiments.ps1`，自动编译并运行 DEA 阶段正式实验。
   - 新增 `scripts/analyze_results.py`，计算 DEA 阶段分组统计量和 Welch t-test。
   - 完成 SERIAL n=1、DEA n=2、DEA n=4 三组算法各 10 次独立运行。

4. 完成项目目录整理。
   - `src/` 存放源码。
   - `data/` 存放 TSP 数据。
   - `docs/` 存放参考论文。
   - `scripts/` 存放自动化脚本。
   - `results/` 存放实验结果和分析结果。
   - `bin/` 存放编译产物。

5. 完成第 3 步 DEA 阶段文档整理。
   - 新增 `reports/01_dea_algorithm_and_experiment.md`。
   - 新增 `reports/project_progress.md`。

6. 完成第 4 步普通 HDEA 实现与 smoke test。
   - 新增 `src/tsp_mpi_hdea.c`。
   - 新增 `scripts/smoke_test_hdea.ps1`。
   - 验证 `nproc=4,num_groups=2` 和 `nproc=6,num_groups=3` 都能执行 local migration 和 global migration。
   - 验证非法参数 `nproc=4,num_groups=3` 能安全报错。

7. 完成第 5 步 HDEA 正式实验与文档整理。
   - 新增 `scripts/run_experiments_all.ps1`。
   - 新增 `scripts/analyze_results_all.py`。
   - 新增 `results/all_experiment_results.csv`，包含 5 组算法各 10 次，共 50 行正式结果。
   - 新增 `results/all_analysis_summary.txt` 和 `results/all_analysis_summary.csv`。
   - 新增 `reports/02_hdea_algorithm_and_experiment.md`。

8. 完成第 6 步 MOVING_HDEA 实现与 smoke test。
   - 新增 `src/tsp_mpi_moving_hdea.c`。
   - 新增 `scripts/smoke_test_moving_hdea.ps1`。
   - 验证 moving colony 后下一次 local migration 的通信对象确实从 `0<->1, 2<->3` 变为 `2<->1, 0<->3`。
   - 验证 `nproc=4,num_groups=2` 和 `nproc=6,num_groups=3` 合法运行，`nproc=4,num_groups=3` 安全报错。

9. 完成第 7 步 MOVING_HDEA 正式实验与文档整理。
   - 新增 `scripts/run_experiments_final.ps1`。
   - 新增 `scripts/analyze_results_final.py`。
   - 新增 `results/final_experiment_results.csv`，包含 7 组算法各 10 次，共 70 行正式结果。
   - 新增 `results/final_analysis_summary.txt` 和 `results/final_analysis_summary.csv`。
   - 新增 `reports/03_moving_hdea_algorithm_and_experiment.md`。

## 2. 当前已有文件

当前项目主要文件如下。

```text
bin/
  tsp_mpi_dea.exe
  tsp_mpi_hdea.exe
  tsp_mpi_moving_hdea.exe
  tsp_serial_exp.exe
  tsp_serial_fixed.exe

data/
  pcb442.tsp

docs/
  hierarchical.pdf

reports/
  01_dea_algorithm_and_experiment.md
  02_hdea_algorithm_and_experiment.md
  03_moving_hdea_algorithm_and_experiment.md
  project_progress.md

results/
  all_analysis_summary.csv
  all_analysis_summary.txt
  all_experiment_results.csv
  analysis_summary.csv
  analysis_summary.txt
  dea_result.csv
  experiment_results.csv
  final_analysis_summary.csv
  final_analysis_summary.txt
  final_experiment_results.csv
  hdea_result.csv
  moving_hdea_result.csv
  quick_analysis_summary.csv
  quick_analysis_summary.txt
  quick_experiment_results.csv
  serial_result.txt

scripts/
  analyze_results.py
  analyze_results_all.py
  analyze_results_final.py
  run_experiments.ps1
  run_experiments_all.ps1
  run_experiments_final.ps1
  smoke_test_dea.ps1
  smoke_test_experiment_pipeline.ps1
  smoke_test_hdea.ps1
  smoke_test_moving_hdea.ps1
  smoke_test_serial.ps1

src/
  TSP0.C
  tsp_mpi_dea.c
  tsp_mpi_hdea.c
  tsp_mpi_moving_hdea.c
  tsp_serial_exp.c
  tsp_serial_fixed.c

README.md
```

DEA 阶段正式实验结果以 `results/experiment_results.csv` 和 `results/analysis_summary.txt` 为准。包含 HDEA 的统一正式实验结果以 `results/all_experiment_results.csv` 和 `results/all_analysis_summary.txt` 为准。包含 MOVING_HDEA 的最终统一正式实验结果以 `results/final_experiment_results.csv` 和 `results/final_analysis_summary.txt` 为准。

## 3. 已验证的最终统一实验结果

最终统一正式实验设置：

- 数据集：`data/pcb442.tsp`
- `maxGen = 1000`
- DEA `migration_interval = 100`
- HDEA `local_migration_interval = 100`
- HDEA `local_to_global_ratio = 5`
- MOVING_HDEA `local_migration_interval = 100`
- MOVING_HDEA `local_to_global_ratio = 5`
- 每组 10 个 seed：

```text
12345, 22345, 32345, 42345, 52345, 62345, 72345, 82345, 92345, 102345
```

正式统计结果如下。

| algorithm | nproc | groups | ratio | count | best | mean | std | avg_time |
| --------- | ----: | -----: | ----: | ----: | ---: | ---: | --: | -------: |
| SERIAL | 1 | 0 | 0 | 10 | 430142 | 438472.100 | 4628.069 | 2.613500 |
| DEA | 2 | 0 | 0 | 10 | 415765 | 430223.600 | 6134.273 | 2.701971 |
| DEA | 4 | 0 | 0 | 10 | 424318 | 430458.000 | 3508.236 | 2.774825 |
| HDEA | 4 | 2 | 5 | 10 | 426732 | 431573.700 | 4266.830 | 3.457383 |
| HDEA | 6 | 3 | 5 | 10 | 426245 | 430320.900 | 2496.949 | 3.458822 |
| MOVING_HDEA | 4 | 2 | 5 | 10 | 424632 | 429704.000 | 3745.679 | 5.076744 |
| MOVING_HDEA | 6 | 3 | 5 | 10 | 423208 | 427890.600 | 3380.349 | 4.892686 |

Welch t-test 主要结果：

| comparison | p-value | conclusion |
| ---------- | ------: | ---------- |
| SERIAL n=1 vs DEA n=2 | 0.003512 | DEA n=2 显著优于 SERIAL |
| SERIAL n=1 vs DEA n=4 | 0.000435 | DEA n=4 显著优于 SERIAL |
| SERIAL n=1 vs HDEA n=4 groups=2 | 0.002782 | HDEA n=4 显著优于 SERIAL |
| SERIAL n=1 vs HDEA n=6 groups=3 | 0.000242 | HDEA n=6 显著优于 SERIAL |
| DEA n=4 vs HDEA n=4 groups=2 | 0.531355 | DEA n=4 均值略好，但差异不显著 |
| DEA n=4 vs HDEA n=6 groups=3 | 0.921034 | HDEA n=6 均值略好，但差异不显著 |
| HDEA n=4 groups=2 vs HDEA n=6 groups=3 | 0.435846 | HDEA n=6 均值略好，但差异不显著 |
| SERIAL n=1 vs MOVING_HDEA n=4 groups=2 | 0.000218 | MOVING_HDEA n=4 显著优于 SERIAL |
| SERIAL n=1 vs MOVING_HDEA n=6 groups=3 | 0.000022 | MOVING_HDEA n=6 显著优于 SERIAL |
| DEA n=4 vs MOVING_HDEA n=4 groups=2 | 0.647810 | MOVING_HDEA n=4 均值略好，但差异不显著 |
| DEA n=4 vs MOVING_HDEA n=6 groups=3 | 0.112945 | MOVING_HDEA n=6 均值略好，但差异不显著 |
| HDEA n=4 groups=2 vs MOVING_HDEA n=4 groups=2 | 0.311721 | MOVING_HDEA n=4 均值略好，但差异不显著 |
| HDEA n=6 groups=3 vs MOVING_HDEA n=6 groups=3 | 0.085502 | MOVING_HDEA n=6 均值略好，但差异不显著 |

## 4. 当前结论

当前 DEA 版本已经满足最低要求：实现一个 MPI 分布式进化算法，并用 10 次可复现实验证明其结果优于串行版本。

普通 HDEA 和 MOVING_HDEA 都已经实现并完成正式实验。实验显示 HDEA 与 MOVING_HDEA 相对于 SERIAL 都显著更好。MOVING_HDEA n=4 和 n=6 的均值分别低于同规模普通 HDEA，但差异未达到 `0.05` 显著性水平。当前最小均值来自 `MOVING_HDEA n=6 groups=3`，为 `427890.600`；单次最优值来自 `DEA n=2`，为 `415765`。

## 5. 已知问题与注意事项

1. 当前实验没有固定总种群规模。每个 rank 均使用 `N_COLONY=100`：

```text
SERIAL n=1: 总个体数 100
DEA n=2: 总个体数 200
DEA n=4: 总个体数 400
HDEA n=4: 总个体数 400
HDEA n=6: 总个体数 600
MOVING_HDEA n=4: 总个体数 400
MOVING_HDEA n=6: 总个体数 600
```

因此，当前实验可以支撑“并行进化算法相对于串行基线更好”的作业要求，但不应被表述为在严格相同计算预算下 DEA 或 HDEA 必然优于串行版本。

2. HDEA n=6 和 MOVING_HDEA n=6 的总个体数更大，不能和 n=4 组做完全公平比较。更公平的比较是 `DEA n=4 vs HDEA n=4 vs MOVING_HDEA n=4`，以及 `HDEA n=6 vs MOVING_HDEA n=6`。

3. MOVING_HDEA 当前只实现 ring moving colony，没有实现 random moving colony。

4. `src/TSP0.C` 是原始代码，应保持不动。`src/tsp_serial_exp.c`、`src/tsp_mpi_dea.c` 和 DEA 阶段 Markdown 文档也应保持稳定，后续开发应新增文件或在统一脚本中扩展。

5. 如果后续重新运行最终统一正式实验，`scripts/run_experiments_final.ps1` 默认会备份旧的 `results/final_experiment_results.csv`，再生成新文件。

## 6. 当前阶段文档

已生成阶段文档：

- `reports/01_dea_algorithm_and_experiment.md`
- `reports/02_hdea_algorithm_and_experiment.md`
- `reports/03_moving_hdea_algorithm_and_experiment.md`

## 7. 下一步计划

1. 检查所有代码、脚本、结果文件和阶段文档。
2. 整合最终报告。
3. 可选补充固定总种群规模或固定函数评价次数的公平性实验。
