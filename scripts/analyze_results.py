import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

try:
    from scipy import stats as scipy_stats
except Exception:  # pragma: no cover - exercised only when scipy is missing.
    scipy_stats = None


REQUIRED_COLUMNS = {
    "algorithm",
    "nproc",
    "maxGen",
    "migration_interval",
    "base_seed",
    "global_best",
    "elapsed_sec",
}


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is empty")
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(sorted(missing))}")

        rows = []
        for line_no, row in enumerate(reader, start=2):
            try:
                rows.append(
                    {
                        "algorithm": row["algorithm"],
                        "nproc": int(row["nproc"]),
                        "maxGen": int(row["maxGen"]),
                        "migration_interval": int(row["migration_interval"]),
                        "base_seed": int(row["base_seed"]),
                        "global_best": float(row["global_best"]),
                        "elapsed_sec": float(row["elapsed_sec"]),
                    }
                )
            except ValueError as exc:
                raise ValueError(f"bad numeric value on line {line_no}: {exc}") from exc
    return rows


def group_rows(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["algorithm"], row["nproc"])].append(row)
    return dict(sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])))


def sample_std(values):
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def summarize(groups):
    summaries = []
    for (algorithm, nproc), rows in groups.items():
        best_values = [row["global_best"] for row in rows]
        elapsed_values = [row["elapsed_sec"] for row in rows]
        summaries.append(
            {
                "algorithm": algorithm,
                "nproc": nproc,
                "count": len(rows),
                "best": min(best_values),
                "mean": statistics.mean(best_values),
                "std": sample_std(best_values),
                "min": min(best_values),
                "max": max(best_values),
                "avg_time": statistics.mean(elapsed_values),
            }
        )
    return summaries


def welch_fallback(left, right):
    n1 = len(left)
    n2 = len(right)
    if n1 < 2 or n2 < 2:
        return math.nan, math.nan, "insufficient samples"

    mean1 = statistics.mean(left)
    mean2 = statistics.mean(right)
    var1 = statistics.variance(left)
    var2 = statistics.variance(right)
    denom = math.sqrt(var1 / n1 + var2 / n2)
    if denom == 0:
        return math.nan, math.nan, "zero variance"

    t_stat = (mean1 - mean2) / denom
    numerator = (var1 / n1 + var2 / n2) ** 2
    denominator = ((var1 / n1) ** 2 / (n1 - 1)) + ((var2 / n2) ** 2 / (n2 - 1))
    df = numerator / denominator if denominator != 0 else math.nan
    return t_stat, math.nan, f"fallback t only, df={df:.3f}; scipy required for p-value"


def welch_test(groups, left_key, right_key):
    if left_key not in groups or right_key not in groups:
        return {
            "comparison": f"{format_key(left_key)} vs {format_key(right_key)}",
            "status": "missing group",
            "t_stat": math.nan,
            "p_value": math.nan,
            "left_mean": math.nan,
            "right_mean": math.nan,
            "better": "unknown",
        }

    left = [row["global_best"] for row in groups[left_key]]
    right = [row["global_best"] for row in groups[right_key]]
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    better = format_key(left_key) if left_mean < right_mean else format_key(right_key)

    if scipy_stats is not None and len(left) >= 2 and len(right) >= 2:
        result = scipy_stats.ttest_ind(left, right, equal_var=False)
        return {
            "comparison": f"{format_key(left_key)} vs {format_key(right_key)}",
            "status": "ok",
            "t_stat": float(result.statistic),
            "p_value": float(result.pvalue),
            "left_mean": left_mean,
            "right_mean": right_mean,
            "better": better,
        }

    t_stat, p_value, status = welch_fallback(left, right)
    return {
        "comparison": f"{format_key(left_key)} vs {format_key(right_key)}",
        "status": status,
        "t_stat": t_stat,
        "p_value": p_value,
        "left_mean": left_mean,
        "right_mean": right_mean,
        "better": better,
    }


def format_key(key):
    return f"{key[0]} n={key[1]}"


def format_float(value, digits=6):
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    return f"{value:.{digits}f}"


def build_report(summaries, tests):
    lines = []
    lines.append("Grouped statistics")
    lines.append("algorithm,nproc,count,best,mean,std,min,max,avg_time")
    for row in summaries:
        lines.append(
            "{algorithm},{nproc},{count},{best:.0f},{mean:.3f},{std:.3f},{min:.0f},{max:.0f},{avg_time:.6f}".format(
                **row
            )
        )

    lines.append("")
    lines.append("Welch t-tests on global_best (two-sided; lower is better)")
    lines.append("comparison,status,t_stat,p_value,left_mean,right_mean,better_mean")
    for row in tests:
        lines.append(
            "{comparison},{status},{t_stat},{p_value},{left_mean},{right_mean},{better}".format(
                comparison=row["comparison"],
                status=row["status"],
                t_stat=format_float(row["t_stat"]),
                p_value=format_float(row["p_value"]),
                left_mean=format_float(row["left_mean"], 3),
                right_mean=format_float(row["right_mean"], 3),
                better=row["better"],
            )
        )

    lines.append("")
    lines.extend(build_conclusion(summaries, tests))
    return "\n".join(lines) + "\n"


def build_conclusion(summaries, tests):
    lines = ["Conclusion"]
    if not summaries:
        return lines + ["No data rows found."]

    best_mean = min(summaries, key=lambda row: row["mean"])
    best_single = min(summaries, key=lambda row: row["best"])
    lines.append(
        f"Smallest mean global_best: {best_mean['algorithm']} n={best_mean['nproc']} "
        f"with mean={best_mean['mean']:.3f}."
    )
    lines.append(
        f"Smallest single best: {best_single['algorithm']} n={best_single['nproc']} "
        f"with best={best_single['best']:.0f}."
    )

    serial_vs_dea = [row for row in tests if row["comparison"].startswith("SERIAL n=1 vs DEA")]
    significant_better = [
        row
        for row in serial_vs_dea
        if row["status"] == "ok"
        and not math.isnan(row["p_value"])
        and row["p_value"] < 0.05
        and row["better"].startswith("DEA")
    ]
    dea_better = [
        row
        for row in serial_vs_dea
        if row["status"] == "ok" and row["better"].startswith("DEA")
    ]

    if significant_better:
        lines.append(
            "At least one DEA configuration has a lower mean than SERIAL with p-value < 0.05."
        )
        lines.append(
            "A plausible reason is that multiple independently seeded subpopulations explore different regions, "
            "while ring migration propagates good tours without fully eliminating island diversity."
        )
    elif dea_better:
        lines.append(
            "DEA has a lower mean in at least one comparison, but the p-value is not below 0.05."
        )
        lines.append(
            "This supports only a directional improvement, not a statistically significant claim."
        )
    else:
        lines.append(
            "The current runs do not show DEA outperforming SERIAL on mean global_best."
        )
        lines.append(
            "Possible reasons include maxGen being too small, migration_interval not being tuned, "
            "or the current 10-seed sample not separating the methods clearly."
        )

    return lines


def write_summary_csv(path, summaries, tests):
    with Path(path).open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["section", "metric", "a", "b", "value"])
        for row in summaries:
            label = f"{row['algorithm']} n={row['nproc']}"
            for metric in ["count", "best", "mean", "std", "min", "max", "avg_time"]:
                writer.writerow(["summary", metric, label, "", row[metric]])
        for row in tests:
            writer.writerow(["ttest", "p_value", row["comparison"], row["status"], row["p_value"]])
            writer.writerow(["ttest", "t_stat", row["comparison"], row["status"], row["t_stat"]])


def main(argv):
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir if (script_dir / "src").exists() else script_dir.parent
    input_path = argv[1] if len(argv) > 1 else str(project_root / "results" / "experiment_results.csv")
    summary_path = argv[2] if len(argv) > 2 else str(project_root / "results" / "analysis_summary.txt")
    summary_csv_path = argv[3] if len(argv) > 3 else str(project_root / "results" / "analysis_summary.csv")

    rows = read_rows(input_path)
    groups = group_rows(rows)
    summaries = summarize(groups)

    comparisons = [
        (("SERIAL", 1), ("DEA", 2)),
        (("SERIAL", 1), ("DEA", 4)),
        (("DEA", 2), ("DEA", 4)),
        (("SERIAL", 1), ("DEA", 1)),
    ]
    tests = [welch_test(groups, left, right) for left, right in comparisons]

    report = build_report(summaries, tests)
    print(report, end="")
    Path(summary_path).write_text(report, encoding="utf-8")
    write_summary_csv(summary_csv_path, summaries, tests)


if __name__ == "__main__":
    main(sys.argv)
