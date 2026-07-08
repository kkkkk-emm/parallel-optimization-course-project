import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

try:
    from scipy import stats as scipy_stats
except Exception:  # pragma: no cover - depends on local Python environment.
    scipy_stats = None


REQUIRED_COLUMNS = {
    "algorithm",
    "nproc",
    "maxGen",
    "migration_interval",
    "local_to_global_ratio",
    "num_groups",
    "base_seed",
    "global_best",
    "elapsed_sec",
}

GROUP_ORDER = {
    ("SERIAL", 1, 0, 0, 0): 0,
    ("DEA", 2, 100, 0, 0): 1,
    ("DEA", 4, 100, 0, 0): 2,
    ("HDEA", 4, 100, 5, 2): 3,
    ("HDEA", 6, 100, 5, 3): 4,
}

COMPARISONS = [
    (("SERIAL", 1, 0, 0, 0), ("DEA", 2, 100, 0, 0)),
    (("SERIAL", 1, 0, 0, 0), ("DEA", 4, 100, 0, 0)),
    (("SERIAL", 1, 0, 0, 0), ("HDEA", 4, 100, 5, 2)),
    (("SERIAL", 1, 0, 0, 0), ("HDEA", 6, 100, 5, 3)),
    (("DEA", 4, 100, 0, 0), ("HDEA", 4, 100, 5, 2)),
    (("DEA", 4, 100, 0, 0), ("HDEA", 6, 100, 5, 3)),
    (("HDEA", 4, 100, 5, 2), ("HDEA", 6, 100, 5, 3)),
]


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as fp:
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
                        "local_to_global_ratio": int(row["local_to_global_ratio"]),
                        "num_groups": int(row["num_groups"]),
                        "base_seed": int(row["base_seed"]),
                        "global_best": float(row["global_best"]),
                        "elapsed_sec": float(row["elapsed_sec"]),
                    }
                )
            except ValueError as exc:
                raise ValueError(f"bad numeric value on line {line_no}: {exc}") from exc
    return rows


def group_key(row):
    return (
        row["algorithm"],
        row["nproc"],
        row["migration_interval"],
        row["local_to_global_ratio"],
        row["num_groups"],
    )


def group_rows(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)
    return dict(
        sorted(
            groups.items(),
            key=lambda item: (
                GROUP_ORDER.get(item[0], 100),
                item[0][0],
                item[0][1],
                item[0][2],
                item[0][3],
                item[0][4],
            ),
        )
    )


def sample_std(values):
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def summarize(groups):
    summaries = []
    for key, rows in groups.items():
        best_values = [row["global_best"] for row in rows]
        elapsed_values = [row["elapsed_sec"] for row in rows]
        algorithm, nproc, migration_interval, ratio, groups_count = key
        summaries.append(
            {
                "algorithm": algorithm,
                "nproc": nproc,
                "migration_interval": migration_interval,
                "local_to_global_ratio": ratio,
                "num_groups": groups_count,
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


def student_t_pdf(x, df):
    coeff = math.exp(
        math.lgamma((df + 1.0) / 2.0)
        - math.lgamma(df / 2.0)
        - 0.5 * math.log(df * math.pi)
    )
    return coeff * (1.0 + (x * x) / df) ** (-(df + 1.0) / 2.0)


def adaptive_simpson(func, a, b, eps=1e-10, max_depth=20):
    def simpson(fa, fm, fb, left, right):
        return (right - left) * (fa + 4.0 * fm + fb) / 6.0

    def recurse(left, right, fa, fm, fb, whole, depth):
        mid = (left + right) / 2.0
        left_mid = (left + mid) / 2.0
        right_mid = (mid + right) / 2.0
        flm = func(left_mid)
        frm = func(right_mid)
        left_area = simpson(fa, flm, fm, left, mid)
        right_area = simpson(fm, frm, fb, mid, right)
        delta = left_area + right_area - whole
        if depth <= 0 or abs(delta) <= 15.0 * eps:
            return left_area + right_area + delta / 15.0
        return recurse(left, mid, fa, flm, fm, left_area, depth - 1) + recurse(
            mid, right, fm, frm, fb, right_area, depth - 1
        )

    if a == b:
        return 0.0
    fa = func(a)
    bval = func(b)
    mid = (a + b) / 2.0
    fm = func(mid)
    whole = simpson(fa, fm, bval, a, b)
    return recurse(a, b, fa, fm, bval, whole, max_depth)


def t_two_sided_p_value(t_stat, df):
    if math.isnan(t_stat) or math.isnan(df) or df <= 0:
        return math.nan
    t_abs = abs(t_stat)
    if t_abs == 0:
        return 1.0
    if t_abs > 80:
        return 0.0
    area = adaptive_simpson(lambda x: student_t_pdf(x, df), 0.0, t_abs)
    cdf = min(1.0, max(0.0, 0.5 + area))
    return max(0.0, min(1.0, 2.0 * (1.0 - cdf)))


def welch_manual(left, right):
    n1 = len(left)
    n2 = len(right)
    if n1 < 2 or n2 < 2:
        return math.nan, math.nan, math.nan, "insufficient samples"

    mean1 = statistics.mean(left)
    mean2 = statistics.mean(right)
    var1 = statistics.variance(left)
    var2 = statistics.variance(right)
    denom = math.sqrt(var1 / n1 + var2 / n2)
    if denom == 0:
        return math.nan, math.nan, math.nan, "zero variance"

    t_stat = (mean1 - mean2) / denom
    numerator = (var1 / n1 + var2 / n2) ** 2
    denominator = ((var1 / n1) ** 2 / (n1 - 1)) + ((var2 / n2) ** 2 / (n2 - 1))
    df = numerator / denominator if denominator != 0 else math.nan
    return t_stat, df, t_two_sided_p_value(t_stat, df), "ok"


def format_key(key):
    algorithm, nproc, migration_interval, ratio, groups_count = key
    if algorithm == "HDEA":
        return f"{algorithm} n={nproc} groups={groups_count}"
    if algorithm == "DEA":
        return f"{algorithm} n={nproc}"
    return f"{algorithm} n={nproc}"


def format_number(value, digits=6):
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    return f"{value:.{digits}f}"


def make_conclusion(left_key, right_key, left_mean, right_mean, p_value, status):
    left_label = format_key(left_key)
    right_label = format_key(right_key)
    if status != "ok" or math.isnan(p_value):
        return "p-value unavailable; no significance claim can be made"

    if left_mean < right_mean:
        better = left_label
    elif right_mean < left_mean:
        better = right_label
    else:
        better = "tie"

    if p_value < 0.05:
        return f"{better} has a lower mean and the difference is significant"
    if better == "tie":
        return "means are equal; no significant difference"
    return f"{better} has a lower mean, but the difference is not significant"


def welch_test(groups, left_key, right_key):
    comparison = f"{format_key(left_key)} vs {format_key(right_key)}"
    if left_key not in groups or right_key not in groups:
        return {
            "comparison": comparison,
            "status": "missing group",
            "mean_left": math.nan,
            "mean_right": math.nan,
            "p_value": math.nan,
            "better_group": "unknown",
            "significant_at_0.05": "unknown",
            "conclusion": "missing group",
        }

    left = [row["global_best"] for row in groups[left_key]]
    right = [row["global_best"] for row in groups[right_key]]
    mean_left = statistics.mean(left)
    mean_right = statistics.mean(right)
    if mean_left < mean_right:
        better = format_key(left_key)
    elif mean_right < mean_left:
        better = format_key(right_key)
    else:
        better = "tie"

    status = "ok"
    if scipy_stats is not None and len(left) >= 2 and len(right) >= 2:
        result = scipy_stats.ttest_ind(left, right, equal_var=False)
        p_value = float(result.pvalue)
    else:
        _t_stat, _df, p_value, status = welch_manual(left, right)

    significant = "yes" if status == "ok" and not math.isnan(p_value) and p_value < 0.05 else "no"
    if status != "ok" or math.isnan(p_value):
        significant = "unknown"

    return {
        "comparison": comparison,
        "status": status,
        "mean_left": mean_left,
        "mean_right": mean_right,
        "p_value": p_value,
        "better_group": better,
        "significant_at_0.05": significant,
        "conclusion": make_conclusion(left_key, right_key, mean_left, mean_right, p_value, status),
    }


def markdown_table(headers, rows):
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def build_report(summaries, tests):
    lines = []
    lines.append("Grouped statistics")
    lines.extend(
        markdown_table(
            [
                "algorithm",
                "nproc",
                "migration_interval",
                "local_to_global_ratio",
                "num_groups",
                "count",
                "best",
                "mean",
                "std",
                "min",
                "max",
                "avg_time",
            ],
            [
                [
                    row["algorithm"],
                    str(row["nproc"]),
                    str(row["migration_interval"]),
                    str(row["local_to_global_ratio"]),
                    str(row["num_groups"]),
                    str(row["count"]),
                    f"{row['best']:.0f}",
                    f"{row['mean']:.3f}",
                    f"{row['std']:.3f}",
                    f"{row['min']:.0f}",
                    f"{row['max']:.0f}",
                    f"{row['avg_time']:.6f}",
                ]
                for row in summaries
            ],
        )
    )

    lines.append("")
    lines.append("Welch t-tests on global_best (two-sided; lower is better)")
    lines.extend(
        markdown_table(
            [
                "comparison",
                "mean_left",
                "mean_right",
                "p_value",
                "better_group",
                "significant_at_0.05",
                "conclusion",
            ],
            [
                [
                    row["comparison"],
                    format_number(row["mean_left"], 3),
                    format_number(row["mean_right"], 3),
                    format_number(row["p_value"], 6),
                    row["better_group"],
                    row["significant_at_0.05"],
                    row["conclusion"],
                ]
                for row in tests
            ],
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
        f"groups={best_mean['num_groups']} mean={best_mean['mean']:.3f}."
    )
    lines.append(
        f"Smallest single best: {best_single['algorithm']} n={best_single['nproc']} "
        f"groups={best_single['num_groups']} best={best_single['best']:.0f}."
    )

    significant = [
        row
        for row in tests
        if row["significant_at_0.05"] == "yes"
    ]
    if significant:
        lines.append("Significant comparisons at alpha=0.05:")
        for row in significant:
            lines.append(f"- {row['comparison']}: {row['conclusion']} (p={row['p_value']:.6f})")
    else:
        lines.append("No configured comparison is significant at alpha=0.05.")
    return lines


def write_summary_csv(path, summaries, tests):
    fieldnames = [
        "record_type",
        "algorithm",
        "nproc",
        "migration_interval",
        "local_to_global_ratio",
        "num_groups",
        "count",
        "best",
        "mean",
        "std",
        "min",
        "max",
        "avg_time",
        "comparison",
        "mean_left",
        "mean_right",
        "p_value",
        "better_group",
        "significant_at_0.05",
        "conclusion",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in summaries:
            writer.writerow(
                {
                    "record_type": "summary",
                    "algorithm": row["algorithm"],
                    "nproc": row["nproc"],
                    "migration_interval": row["migration_interval"],
                    "local_to_global_ratio": row["local_to_global_ratio"],
                    "num_groups": row["num_groups"],
                    "count": row["count"],
                    "best": f"{row['best']:.0f}",
                    "mean": f"{row['mean']:.6f}",
                    "std": f"{row['std']:.6f}",
                    "min": f"{row['min']:.0f}",
                    "max": f"{row['max']:.0f}",
                    "avg_time": f"{row['avg_time']:.6f}",
                }
            )
        for row in tests:
            writer.writerow(
                {
                    "record_type": "ttest",
                    "comparison": row["comparison"],
                    "mean_left": format_number(row["mean_left"], 6),
                    "mean_right": format_number(row["mean_right"], 6),
                    "p_value": format_number(row["p_value"], 6),
                    "better_group": row["better_group"],
                    "significant_at_0.05": row["significant_at_0.05"],
                    "conclusion": row["conclusion"],
                }
            )


def default_paths(argv):
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir if (script_dir / "src").exists() else script_dir.parent
    input_path = argv[1] if len(argv) > 1 else str(project_root / "results" / "all_experiment_results.csv")
    summary_path = argv[2] if len(argv) > 2 else str(project_root / "results" / "all_analysis_summary.txt")
    summary_csv_path = argv[3] if len(argv) > 3 else str(project_root / "results" / "all_analysis_summary.csv")
    return input_path, summary_path, summary_csv_path


def main(argv):
    input_path, summary_path, summary_csv_path = default_paths(argv)
    rows = read_rows(input_path)
    groups = group_rows(rows)
    summaries = summarize(groups)
    tests = [welch_test(groups, left, right) for left, right in COMPARISONS]

    report = build_report(summaries, tests)
    print(report, end="")
    Path(summary_path).write_text(report, encoding="utf-8")
    write_summary_csv(summary_csv_path, summaries, tests)


if __name__ == "__main__":
    main(sys.argv)
