# 复现性与并行效果补强实验

本报告用于记录 `reproduction_extension` 独立补强实验。该实验不替代 70 行正式实验，不覆盖任何 `final_*` 正式结果文件，也不修改 `src/TSP0.C`。

## 1. 实验目的

本实验目标是做一个缩小版机制复现，检查当前实现与参考论文设置之间的差距，并在更长迭代预算下继续检验 MPI 并行进化算法相对 SERIAL 的解质量优势。

这里的复现含义是复现核心算法机制：ring DEA、ring individual HDEA、ring moving colony HDEA、每个子种群 `N_COLONY=100`、HDEA 的 local/global 层级迁移，以及 moving colony 通过逻辑分组移动子种群归属。不能声称完全复现论文，因为当前实验没有覆盖论文中的 9 个 TSPLIB 实例、30 次独立运行、16/36/64 子种群、random topology 和完整 100 次 global migration rounds。

## 2. 与论文设置的对应关系

| 项目 | 论文设置 | 当前补强实验 |
|---|---|---|
| 基础问题 | TSP benchmark instances | `data/pcb442.tsp` |
| 子种群规模 | 100 | 100 |
| DEA | ring DEA | `src/tsp_mpi_dea.c` ring migration |
| HDEA | ring local migration + ring individual global migration | `src/tsp_mpi_hdea.c` |
| moving colony | ring/random colony HDEA | 当前只实现 ring moving colony |
| local/global 轮次比 | `20:1` | `local_to_global_ratio=20` |
| 子种群数量 | 16、36、64 等 | 4 和 9，作为缩小版 proxy |
| 独立运行次数 | 30 | 5 seeds |
| 运行时间结论 | 论文平台多核并行 | 当前单机 Windows/MS-MPI；运行时间不作为 speedup 结论 |

## 3. 实验配置

结果写入：

```text
results/reproduction_extension_results.csv
results/reproduction_extension_summary.csv
results/reproduction_extension_summary.txt
```

运行脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_reproduction_extension.ps1
python .\scripts\analyze_reproduction_extension.py .\results\reproduction_extension_results.csv
```

统一参数：

| 参数 | 值 |
|---|---:|
| maxGen | 5000 |
| migration_interval | 25 |
| local_to_global_ratio | 20 |
| seeds | 12345, 22345, 32345, 42345, 52345 |

配置矩阵：

| algorithm | nproc | maxGen | migration_interval | local_to_global_ratio | num_groups | rows |
|---|---:|---:|---:|---:|---:|---:|
| SERIAL | 1 | 5000 | 0 | 0 | 0 | 5 |
| DEA | 4 | 5000 | 25 | 0 | 0 | 5 |
| HDEA | 4 | 5000 | 25 | 20 | 2 | 5 |
| MOVING_HDEA | 4 | 5000 | 25 | 20 | 2 | 5 |
| DEA | 9 | 5000 | 25 | 0 | 0 | 5 |
| HDEA | 9 | 5000 | 25 | 20 | 3 | 5 |
| MOVING_HDEA | 9 | 5000 | 25 | 20 | 3 | 5 |

## 4. 统计指标

分析脚本 `scripts/analyze_reproduction_extension.py` 输出以下统计：

- best、mean、std、median、min、max；
- avg_time、time_median；
- 相对 SERIAL mean 的 improvement ratio；
- Welch t-test；
- mean difference 的 95% confidence interval；
- Hedges effect size；
- `success_below_serial_median`；
- `success_below_serial_best`。

## 5. 结论口径

TSP 是最小化问题，`global_best` 越低越好。判断“并行后效果更好”时，本报告只以解质量为主，不以运行时间作为主要结论。

可以写：

- 某并行配置的 mean 或 median 低于 SERIAL。
- 某并行配置相对 SERIAL 的 Welch t-test 达到 `p<0.05`。
- 某并行配置的 95% confidence interval 和 Hedges effect size 支持解质量优势。
- 某并行配置在若干 seed 中低于 SERIAL median 或 SERIAL best。

不能写：

- 完全复现论文结果。
- MOVING_HDEA 在所有实例或所有设置下最优。
- 并行版本显著加速运行时间。
- 为了得到更好结论而改 CSV、删数据或替换失败配置。

## 6. 结果记录

本节数字来自：

```text
results/reproduction_extension_results.csv
results/reproduction_extension_summary.csv
results/reproduction_extension_summary.txt
```

### 6.1 分组统计

| algorithm | nproc | groups | best | mean | std | median | avg_time | time_median | improvement_vs_serial_mean_pct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 168654 | 171558.600 | 2460.118 | 171648.000 | 5.721000 | 5.761000 | 0.000% |
| DEA | 4 | 0 | 107560 | 110326.000 | 3079.609 | 109393.000 | 4.849960 | 4.762979 | 35.692% |
| DEA | 9 | 0 | 104278 | 108607.600 | 2750.780 | 109318.000 | 5.798542 | 5.746716 | 36.694% |
| HDEA | 4 | 2 | 105728 | 107892.800 | 1496.672 | 107695.000 | 5.101788 | 5.049673 | 37.110% |
| HDEA | 9 | 3 | 102586 | 105127.400 | 1983.763 | 104770.000 | 5.796031 | 5.736405 | 38.722% |
| MOVING_HDEA | 4 | 2 | 106838 | 110460.800 | 4040.559 | 108204.000 | 5.376493 | 5.447458 | 35.613% |
| MOVING_HDEA | 9 | 3 | 104960 | 106957.000 | 1634.146 | 107545.000 | 6.013772 | 6.008192 | 37.656% |

所有 6 个并行配置的 mean 和 median 均低于 SERIAL，且每个并行配置 5 次运行均低于 SERIAL median，也均低于 SERIAL best。因此，本补强实验支持“并行版本在解质量上明显优于串行版本”的结论。

### 6.2 与 SERIAL 的统计检验

| comparison | mean_diff_left_minus_right | 95% CI | p_value | Hedges g | significant |
|---|---:|---|---:|---:|---|
| SERIAL n=1 vs DEA n=4 | 61232.600 | [57132.943, 65332.257] | 0.000000 | 19.843672 | yes |
| SERIAL n=1 vs DEA n=9 | 62951.000 | [59136.980, 66765.020] | 0.000000 | 21.789228 | yes |
| SERIAL n=1 vs HDEA n=4 groups=2 | 63665.800 | [60583.236, 66748.364] | 0.000000 | 28.241153 | yes |
| SERIAL n=1 vs HDEA n=9 groups=3 | 66431.200 | [63146.395, 69716.005] | 0.000000 | 26.850668 | yes |
| SERIAL n=1 vs MOVING_HDEA n=4 groups=2 | 61097.800 | [56034.356, 66161.244] | 0.000000 | 16.497698 | yes |
| SERIAL n=1 vs MOVING_HDEA n=9 groups=3 | 64601.600 | [61474.261, 67728.939] | 0.000000 | 27.940311 | yes |

上述 mean difference 使用 `SERIAL mean - parallel mean` 的方向，正数表示并行配置路径更短。所有并行配置相对 SERIAL 的 95% CI 均为正，Welch t-test 均达到显著性，Hedges effect size 方向也支持并行解质量优势。

### 6.3 并行算法之间的比较

并行算法之间的 pairwise Welch t-test 没有达到 `p<0.05`。例如：

| comparison | p_value | 结论 |
|---|---:|---|
| DEA n=4 vs HDEA n=4 groups=2 | 0.164947 | HDEA n=4 mean 更低，但不显著 |
| DEA n=4 vs MOVING_HDEA n=4 groups=2 | 0.954244 | DEA n=4 mean 略低，但不显著 |
| HDEA n=4 groups=2 vs MOVING_HDEA n=4 groups=2 | 0.239318 | HDEA n=4 mean 更低，但不显著 |
| DEA n=9 vs HDEA n=9 groups=3 | 0.054057 | HDEA n=9 mean 更低，但未达到 0.05 |
| DEA n=9 vs MOVING_HDEA n=9 groups=3 | 0.289269 | MOVING_HDEA n=9 mean 更低，但不显著 |
| HDEA n=9 groups=3 vs MOVING_HDEA n=9 groups=3 | 0.151482 | HDEA n=9 mean 更低，但不显著 |

因此，本补强实验不能写成 MOVING_HDEA 显著优于 DEA/HDEA，也不能写成 HDEA 显著优于 DEA。可以写的是：在 `maxGen=5000`、`local_to_global_ratio=20`、5 seed 的缩小版复现设置下，所有并行配置相对 SERIAL 显著改善了解质量；并行算法之间仅表现出均值差异趋势，样本量不足以支持显著性排序。

### 6.4 运行时间说明

运行时间结果是混合的：n=4 并行配置的 `avg_time` 低于 SERIAL，但 n=9 配置的 `avg_time` 接近或高于 SERIAL。当前样本量只有 5，且运行环境是单机 Windows/MS-MPI，时间受进程启动和调度影响较大。

因此，本报告不声称获得稳定 speedup。更稳妥的表述是：补强实验进一步支持 MPI 并行进化结构带来的解质量提升；运行时间方面没有形成可推广的显著加速结论。
