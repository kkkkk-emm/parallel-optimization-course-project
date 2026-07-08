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

ALGORITHM_ORDER = {
    "SERIAL": 0,
    "DEA": 1,
    "HDEA": 2,
    "MOVING_HDEA": 3,
}


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is empty")
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(sorted(missing))}")

        rows = []
        seen = set()
        for line_no, row in enumerate(reader, start=2):
            try:
                parsed = {
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
            except ValueError as exc:
                raise ValueError(f"bad numeric value on line {line_no}: {exc}") from exc

            for field in ("global_best", "elapsed_sec"):
                if not math.isfinite(parsed[field]):
                    raise ValueError(f"non-finite {field} on line {line_no}")

            duplicate_key = (
                parsed["algorithm"],
                parsed["nproc"],
                parsed["maxGen"],
                parsed["migration_interval"],
                parsed["local_to_global_ratio"],
                parsed["num_groups"],
                parsed["base_seed"],
            )
            if duplicate_key in seen:
                raise ValueError(f"duplicate result row on line {line_no}: {duplicate_key}")
            seen.add(duplicate_key)
            rows.append(parsed)
    return rows


def group_key(row):
    return (
        row["algorithm"],
        row["nproc"],
        row["maxGen"],
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
                ALGORITHM_ORDER.get(item[0][0], 99),
                item[0][1],
                item[0][5],
                item[0][2],
                item[0][3],
                item[0][4],
            ),
        )
    )


def label_key(key):
    algorithm, nproc, _max_gen, _migration, _ratio, groups_count = key
    if algorithm in {"HDEA", "MOVING_HDEA"}:
        return f"{algorithm} n={nproc} groups={groups_count}"
    return f"{algorithm} n={nproc}"


def sample_std(values):
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def get_serial_summary(summaries):
    serial = [row for row in summaries if row["algorithm"] == "SERIAL"]
    if len(serial) != 1:
        raise ValueError(f"expected exactly one SERIAL summary, got {len(serial)}")
    return serial[0]


def summarize(groups):
    summaries = []
    for key, rows in groups.items():
        algorithm, nproc, max_gen, migration_interval, ratio, groups_count = key
        best_values = [row["global_best"] for row in rows]
        elapsed_values = [row["elapsed_sec"] for row in rows]
        summaries.append(
            {
                "key": key,
                "algorithm": algorithm,
                "nproc": nproc,
                "maxGen": max_gen,
                "migration_interval": migration_interval,
                "local_to_global_ratio": ratio,
                "num_groups": groups_count,
                "count": len(rows),
                "best": min(best_values),
                "mean": statistics.mean(best_values),
                "std": sample_std(best_values),
                "median": statistics.median(best_values),
                "min": min(best_values),
                "max": max(best_values),
                "avg_time": statistics.mean(elapsed_values),
                "time_median": statistics.median(elapsed_values),
            }
        )

    serial = get_serial_summary(summaries)
    for row in summaries:
        values = [item["global_best"] for item in groups[row["key"]]]
        if row["algorithm"] == "SERIAL":
            row["improvement_vs_serial_mean_pct"] = 0.0
        else:
            row["improvement_vs_serial_mean_pct"] = (
                (serial["mean"] - row["mean"]) / serial["mean"] * 100.0
            )
        below_median = sum(1 for value in values if value < serial["median"])
        below_best = sum(1 for value in values if value < serial["best"])
        row["success_below_serial_median_count"] = below_median
        row["success_below_serial_median_rate"] = below_median / len(values) if values else math.nan
        row["success_below_serial_best_count"] = below_best
        row["success_below_serial_best_rate"] = below_best / len(values) if values else math.nan
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
    fb = func(b)
    mid = (a + b) / 2.0
    fm = func(mid)
    whole = simpson(fa, fm, fb, a, b)
    return recurse(a, b, fa, fm, fb, whole, max_depth)


def t_cdf(t_value, df):
    if math.isnan(t_value) or math.isnan(df) or df <= 0:
        return math.nan
    if t_value == 0:
        return 0.5
    t_abs = abs(t_value)
    if t_abs > 80:
        return 1.0 if t_value > 0 else 0.0
    area = adaptive_simpson(lambda x: student_t_pdf(x, df), 0.0, t_abs)
    if t_value > 0:
        return min(1.0, max(0.0, 0.5 + area))
    return min(1.0, max(0.0, 0.5 - area))


def t_two_sided_p_value(t_stat, df):
    cdf = t_cdf(abs(t_stat), df)
    if math.isnan(cdf):
        return math.nan
    return max(0.0, min(1.0, 2.0 * (1.0 - cdf)))


def t_ppf(probability, df):
    if scipy_stats is not None:
        return float(scipy_stats.t.ppf(probability, df))
    low, high = -100.0, 100.0
    for _ in range(120):
        mid = (low + high) / 2.0
        if t_cdf(mid, df) < probability:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def welch_values(left, right):
    n1 = len(left)
    n2 = len(right)
    if n1 < 2 or n2 < 2:
        return math.nan, math.nan, math.nan, math.nan, "insufficient samples"

    mean1 = statistics.mean(left)
    mean2 = statistics.mean(right)
    var1 = statistics.variance(left)
    var2 = statistics.variance(right)
    se = math.sqrt(var1 / n1 + var2 / n2)
    if se == 0:
        return math.nan, math.nan, math.nan, math.nan, "zero variance"

    diff = mean1 - mean2
    t_stat = diff / se
    numerator = (var1 / n1 + var2 / n2) ** 2
    denominator = ((var1 / n1) ** 2 / (n1 - 1)) + ((var2 / n2) ** 2 / (n2 - 1))
    df = numerator / denominator if denominator != 0 else math.nan
    if scipy_stats is not None:
        result = scipy_stats.ttest_ind(left, right, equal_var=False)
        p_value = float(result.pvalue)
    else:
        p_value = t_two_sided_p_value(t_stat, df)
    return t_stat, df, p_value, se, "ok"


def hedges_g(left, right):
    n1 = len(left)
    n2 = len(right)
    if n1 < 2 or n2 < 2:
        return math.nan
    var1 = statistics.variance(left)
    var2 = statistics.variance(right)
    pooled_denom = n1 + n2 - 2
    if pooled_denom <= 0:
        return math.nan
    pooled_sd = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / pooled_denom)
    if pooled_sd == 0:
        return math.nan
    correction = 1.0 - (3.0 / (4.0 * pooled_denom - 1.0))
    return ((statistics.mean(left) - statistics.mean(right)) / pooled_sd) * correction


def planned_comparisons(groups):
    serial_key = next((key for key in groups if key[0] == "SERIAL"), None)
    if serial_key is None:
        return []
    comparisons = [(serial_key, key) for key in groups if key[0] != "SERIAL"]

    for nproc in sorted({key[1] for key in groups if key[0] != "SERIAL"}):
        dea = next((key for key in groups if key[0] == "DEA" and key[1] == nproc), None)
        hdea = next((key for key in groups if key[0] == "HDEA" and key[1] == nproc), None)
        moving = next((key for key in groups if key[0] == "MOVING_HDEA" and key[1] == nproc), None)
        if dea and hdea:
            comparisons.append((dea, hdea))
        if dea and moving:
            comparisons.append((dea, moving))
        if hdea and moving:
            comparisons.append((hdea, moving))
    return comparisons


def welch_test(groups, left_key, right_key):
    left = [row["global_best"] for row in groups[left_key]]
    right = [row["global_best"] for row in groups[right_key]]
    mean_left = statistics.mean(left)
    mean_right = statistics.mean(right)
    mean_diff = mean_left - mean_right
    t_stat, df, p_value, se, status = welch_values(left, right)
    if status == "ok" and not math.isnan(df):
        t_crit = t_ppf(0.975, df)
        ci_low = mean_diff - t_crit * se
        ci_high = mean_diff + t_crit * se
    else:
        ci_low = math.nan
        ci_high = math.nan

    if mean_left < mean_right:
        better = label_key(left_key)
    elif mean_right < mean_left:
        better = label_key(right_key)
    else:
        better = "tie"

    significant = "yes" if status == "ok" and not math.isnan(p_value) and p_value < 0.05 else "no"
    if status != "ok" or math.isnan(p_value):
        significant = "unknown"

    return {
        "comparison": f"{label_key(left_key)} vs {label_key(right_key)}",
        "status": status,
        "mean_left": mean_left,
        "mean_right": mean_right,
        "mean_diff_left_minus_right": mean_diff,
        "mean_diff_ci_low": ci_low,
        "mean_diff_ci_high": ci_high,
        "p_value": p_value,
        "hedges_g": hedges_g(left, right),
        "better_group": better,
        "significant_at_0.05": significant,
    }


def criteria_rows(summaries):
    rows = []
    for row in summaries:
        if row["algorithm"] == "SERIAL":
            continue
        rows.append(
            {
                "algorithm": row["algorithm"],
                "nproc": row["nproc"],
                "maxGen": row["maxGen"],
                "migration_interval": row["migration_interval"],
                "local_to_global_ratio": row["local_to_global_ratio"],
                "num_groups": row["num_groups"],
                "better_than_serial_mean": "yes"
                if row["improvement_vs_serial_mean_pct"] > 0
                else "no",
                "better_than_serial_median": "yes"
                if row["success_below_serial_median_count"] > 0
                else "no",
                "success_below_serial_median_count": row["success_below_serial_median_count"],
                "success_below_serial_median_rate": row["success_below_serial_median_rate"],
                "success_below_serial_best_count": row["success_below_serial_best_count"],
                "success_below_serial_best_rate": row["success_below_serial_best_rate"],
            }
        )
    return rows


def fmt(value, digits=6):
    if isinstance(value, float) and math.isnan(value):
        return ""
    return f"{value:.{digits}f}"


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def build_report(summaries, tests, criteria):
    lines = ["Extended grouped statistics"]
    lines.extend(
        markdown_table(
            [
                "algorithm",
                "nproc",
                "groups",
                "count",
                "best",
                "mean",
                "std",
                "median",
                "min",
                "max",
                "avg_time",
                "time_median",
                "improvement_vs_serial_mean_pct",
                "success_below_serial_median",
            ],
            [
                [
                    row["algorithm"],
                    str(row["nproc"]),
                    str(row["num_groups"]),
                    str(row["count"]),
                    f"{row['best']:.0f}",
                    f"{row['mean']:.3f}",
                    f"{row['std']:.3f}",
                    f"{row['median']:.3f}",
                    f"{row['min']:.0f}",
                    f"{row['max']:.0f}",
                    f"{row['avg_time']:.6f}",
                    f"{row['time_median']:.6f}",
                    f"{row['improvement_vs_serial_mean_pct']:.3f}%",
                    f"{row['success_below_serial_median_count']}/{row['count']}",
                ]
                for row in summaries
            ],
        )
    )
    lines.append("")
    lines.append("Welch t-tests and Hedges effect sizes")
    lines.extend(
        markdown_table(
            [
                "comparison",
                "mean_left",
                "mean_right",
                "mean_diff_left_minus_right",
                "95% CI",
                "p_value",
                "Hedges g",
                "significant",
            ],
            [
                [
                    row["comparison"],
                    fmt(row["mean_left"], 3),
                    fmt(row["mean_right"], 3),
                    fmt(row["mean_diff_left_minus_right"], 3),
                    f"[{fmt(row['mean_diff_ci_low'], 3)}, {fmt(row['mean_diff_ci_high'], 3)}]",
                    fmt(row["p_value"], 6),
                    fmt(row["hedges_g"], 6),
                    row["significant_at_0.05"],
                ]
                for row in tests
            ],
        )
    )
    lines.append("")
    lines.append("Better-than-serial criteria")
    lines.extend(
        markdown_table(
            [
                "algorithm",
                "nproc",
                "groups",
                "better_than_serial_mean",
                "better_than_serial_median",
                "success_below_serial_best",
            ],
            [
                [
                    row["algorithm"],
                    str(row["nproc"]),
                    str(row["num_groups"]),
                    row["better_than_serial_mean"],
                    row["better_than_serial_median"],
                    f"{row['success_below_serial_best_count']}",
                ]
                for row in criteria
            ],
        )
    )
    return "\n".join(lines) + "\n"


def write_summary_csv(path, summaries, tests, criteria):
    fieldnames = [
        "record_type",
        "algorithm",
        "nproc",
        "maxGen",
        "migration_interval",
        "local_to_global_ratio",
        "num_groups",
        "count",
        "best",
        "mean",
        "std",
        "median",
        "min",
        "max",
        "avg_time",
        "time_median",
        "improvement_vs_serial_mean_pct",
        "success_below_serial_median_count",
        "success_below_serial_median_rate",
        "success_below_serial_best_count",
        "success_below_serial_best_rate",
        "comparison",
        "status",
        "mean_left",
        "mean_right",
        "mean_diff_left_minus_right",
        "mean_diff_ci_low",
        "mean_diff_ci_high",
        "p_value",
        "hedges_g",
        "better_group",
        "significant_at_0.05",
        "better_than_serial_mean",
        "better_than_serial_median",
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
                    "maxGen": row["maxGen"],
                    "migration_interval": row["migration_interval"],
                    "local_to_global_ratio": row["local_to_global_ratio"],
                    "num_groups": row["num_groups"],
                    "count": row["count"],
                    "best": fmt(row["best"], 0),
                    "mean": fmt(row["mean"]),
                    "std": fmt(row["std"]),
                    "median": fmt(row["median"]),
                    "min": fmt(row["min"], 0),
                    "max": fmt(row["max"], 0),
                    "avg_time": fmt(row["avg_time"]),
                    "time_median": fmt(row["time_median"]),
                    "improvement_vs_serial_mean_pct": fmt(row["improvement_vs_serial_mean_pct"]),
                    "success_below_serial_median_count": row["success_below_serial_median_count"],
                    "success_below_serial_median_rate": fmt(row["success_below_serial_median_rate"]),
                    "success_below_serial_best_count": row["success_below_serial_best_count"],
                    "success_below_serial_best_rate": fmt(row["success_below_serial_best_rate"]),
                }
            )
        for row in tests:
            writer.writerow(
                {
                    "record_type": "ttest",
                    "comparison": row["comparison"],
                    "status": row["status"],
                    "mean_left": fmt(row["mean_left"]),
                    "mean_right": fmt(row["mean_right"]),
                    "mean_diff_left_minus_right": fmt(row["mean_diff_left_minus_right"]),
                    "mean_diff_ci_low": fmt(row["mean_diff_ci_low"]),
                    "mean_diff_ci_high": fmt(row["mean_diff_ci_high"]),
                    "p_value": fmt(row["p_value"]),
                    "hedges_g": fmt(row["hedges_g"]),
                    "better_group": row["better_group"],
                    "significant_at_0.05": row["significant_at_0.05"],
                }
            )
        for row in criteria:
            writer.writerow(
                {
                    "record_type": "criteria",
                    "algorithm": row["algorithm"],
                    "nproc": row["nproc"],
                    "maxGen": row["maxGen"],
                    "migration_interval": row["migration_interval"],
                    "local_to_global_ratio": row["local_to_global_ratio"],
                    "num_groups": row["num_groups"],
                    "better_than_serial_mean": row["better_than_serial_mean"],
                    "better_than_serial_median": row["better_than_serial_median"],
                    "success_below_serial_median_count": row["success_below_serial_median_count"],
                    "success_below_serial_median_rate": fmt(row["success_below_serial_median_rate"]),
                    "success_below_serial_best_count": row["success_below_serial_best_count"],
                    "success_below_serial_best_rate": fmt(row["success_below_serial_best_rate"]),
                }
            )


def default_paths(argv):
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir if (script_dir / "src").exists() else script_dir.parent
    input_path = argv[1] if len(argv) > 1 else str(project_root / "results" / "reproduction_extension_results.csv")
    summary_path = argv[2] if len(argv) > 2 else str(project_root / "results" / "reproduction_extension_summary.txt")
    summary_csv_path = argv[3] if len(argv) > 3 else str(project_root / "results" / "reproduction_extension_summary.csv")
    return input_path, summary_path, summary_csv_path


def main(argv):
    input_path, summary_path, summary_csv_path = default_paths(argv)
    rows = read_rows(input_path)
    groups = group_rows(rows)
    summaries = summarize(groups)
    tests = [welch_test(groups, left, right) for left, right in planned_comparisons(groups)]
    criteria = criteria_rows(summaries)
    report = build_report(summaries, tests, criteria)
    print(report, end="")
    Path(summary_path).write_text(report, encoding="utf-8")
    write_summary_csv(summary_csv_path, summaries, tests, criteria)


if __name__ == "__main__":
    main(sys.argv)
