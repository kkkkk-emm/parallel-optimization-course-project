# Version B Algorithm Search Log

## Version A Baseline

从 `results/final_analysis_summary.csv` 提取的 Version A 正式基准为：

- 最低正式 mean：`MOVING_HDEA n=6 groups=3 mean = 427890.600`
- 最低 single best：`DEA n=2 best = 415765`

Version B 达标口径：

- mean 低于 `427890.600` 视为超过 Version A 正式最低 mean。
- single best 低于 `415765` 视为超过 Version A 正式最低 best。

## Trial Setup

trial 命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_scratch_trials.ps1
```

trial 输出：

- `results/scratch_algorithm_trials.csv`
- `results/scratch_algorithm_trials_summary.txt`

trial 使用 3 seeds：`12345,22345,32345`。每个候选算法运行 serial 和 MPI n=4，小时间预算为 `1.0` 秒，iteration budget 为 `80`。

## Candidate Results

| algorithm | nproc | mode | count | best | mean | avg_time | beats Version A mean | beats Version A best |
|---|---:|---|---:|---:|---:|---:|---|---|
| SCRATCH_GREEDY_2OPT | 4 | mpi | 3 | 53473 | 53955.000 | 1.090667 | yes | yes |
| SCRATCH_ILS_2OPT | 4 | mpi | 3 | 52130 | 52473.667 | 1.058333 | yes | yes |
| SCRATCH_NN_2OPT | 4 | mpi | 3 | 52528 | 52577.000 | 1.010333 | yes | yes |
| SCRATCH_GREEDY_2OPT | 1 | serial | 3 | 54333 | 54535.667 | 1.063667 | yes | yes |
| SCRATCH_ILS_2OPT | 1 | serial | 3 | 52666 | 53462.333 | 0.910000 | yes | yes |
| SCRATCH_NN_2OPT | 1 | serial | 3 | 52755 | 52881.667 | 1.010333 | yes | yes |

## Elimination Notes

`SCRATCH_GREEDY_2OPT` 被淘汰，因为 trial mean 明显高于 `SCRATCH_ILS_2OPT` 和 `SCRATCH_NN_2OPT`。

`SCRATCH_NN_2OPT` 保留为强 baseline，但没有进入正式实验。它的 trial 结果稳定，说明 nearest-neighbor + 2-opt 已经足以大幅超过 Version A；但 MPI n=4 trial 中 `SCRATCH_ILS_2OPT` 的 mean 更低，且 ILS 具有继续强化的空间。

`SCRATCH_ILS_2OPT` 被选为正式 Version B 算法。它使用 randomized greedy initialization、double-bridge perturbation 和 repeated 2-opt，在 trial 中取得最低 MPI n=4 mean。

## Formal Version B Results

正式命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_scratch_final.ps1
```

正式输出：

- `results/scratch_experiment_results.csv`
- `results/scratch_analysis_summary.csv`
- `results/scratch_analysis_summary.txt`

正式实验使用 10 seeds，并包含 serial、MPI n=2、MPI n=4、MPI n=6。

| algorithm | nproc | mode | count | best | mean | std | avg_time | beats Version A mean | beats Version A best |
|---|---:|---|---:|---:|---:|---:|---:|---|---|
| SCRATCH_ILS_2OPT | 2 | mpi | 10 | 51843 | 52218.800 | 310.164 | 2.026200 | yes | yes |
| SCRATCH_ILS_2OPT | 4 | mpi | 10 | 51843 | 52170.000 | 232.238 | 2.085700 | yes | yes |
| SCRATCH_ILS_2OPT | 6 | mpi | 10 | 51843 | 52160.600 | 189.863 | 2.061900 | yes | yes |
| SCRATCH_ILS_2OPT | 1 | serial | 10 | 52055 | 52611.400 | 288.659 | 1.980200 | yes | yes |

## Final Selection

最终 Version B 算法为 `SCRATCH_ILS_2OPT`。

它在正式实验中的最佳配置为 MPI n=6：

- mean：`52160.600`
- best：`51843`
- avg_time：`2.061900`
- mean improvement vs Version A：`87.810%`
- best improvement vs Version A：`87.531%`

这些结果说明 Version B 在 `pcb442.tsp` 上达到了满分冲刺口径：mean 和 best 均优于 Version A 正式基准。但该结论仍受算法类型、time budget、并行 rank 数和单实例实验限制。
