import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

try:
    from scipy import stats
except Exception:  # pragma: no cover - fallback is for minimal environments.
    stats = None


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
            if not math.isfinite(parsed["global_best"]):
                raise ValueError(f"non-finite global_best on line {line_no}")
            key = (
                parsed["algorithm"],
                parsed["nproc"],
                parsed["num_groups"],
                parsed["base_seed"],
            )
            if key in seen:
                raise ValueError(f"duplicate row on line {line_no}: {key}")
            seen.add(key)
            rows.append(parsed)
    return rows


def label_for(row):
    if row["algorithm"] == "SERIAL":
        return "SERIAL n=1"
    if row["num_groups"]:
        return f"{row['algorithm']} n={row['nproc']} groups={row['num_groups']}"
    return f"{row['algorithm']} n={row['nproc']}"


def group_rows(rows):
    groups = defaultdict(dict)
    meta = {}
    for row in rows:
        label = label_for(row)
        groups[label][row["base_seed"]] = row["global_best"]
        meta[label] = row
    return groups, meta


def sample_std(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def t_critical(confidence, df):
    if stats is not None:
        return float(stats.t.ppf((1.0 + confidence) / 2.0, df))
    return 1.96


def paired_t_p_value(diffs):
    if len(diffs) < 2:
        return float("nan")
    sd = sample_std(diffs)
    if sd == 0:
        return 0.0 if statistics.mean(diffs) != 0 else 1.0
    if stats is not None:
        return float(stats.ttest_1samp(diffs, 0.0).pvalue)
    t_value = abs(statistics.mean(diffs) / (sd / math.sqrt(len(diffs))))
    return math.erfc(t_value / math.sqrt(2.0))


def wilcoxon_p_value(diffs):
    non_zero = [value for value in diffs if value != 0]
    if not non_zero:
        return 1.0
    if stats is not None:
        try:
            return float(stats.wilcoxon(non_zero, zero_method="wilcox", alternative="two-sided").pvalue)
        except ValueError:
            return 1.0
    positives = sum(1 for value in non_zero if value > 0)
    n = len(non_zero)
    tail = min(positives, n - positives)
    prob = sum(math.comb(n, k) for k in range(tail + 1)) / (2**n)
    return min(1.0, 2.0 * prob)


def welch_p_value(left, right):
    if len(left) < 2 or len(right) < 2:
        return float("nan")
    if stats is not None:
        return float(stats.ttest_ind(left, right, equal_var=False).pvalue)
    return float("nan")


def holm_adjust(p_values):
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [float("nan")] * len(p_values)
    running_max = 0.0
    m = len(indexed)
    for rank, (idx, p_value) in enumerate(indexed):
        factor = m - rank
        value = min(1.0, p_value * factor)
        running_max = max(running_max, value)
        adjusted[idx] = running_max
    return adjusted


def build_comparisons(labels):
    if "SERIAL n=1" not in labels:
        return []
    serial = "SERIAL n=1"
    others = [label for label in labels if label != serial]
    comparisons = [(serial, label) for label in others]
    for i, left in enumerate(others):
        for right in others[i + 1 :]:
            comparisons.append((left, right))
    return comparisons


def analyze(rows):
    groups, _ = group_rows(rows)
    labels = sorted(groups.keys(), key=lambda label: (label != "SERIAL n=1", label))
    comparisons = build_comparisons(labels)
    results = []
    for left_label, right_label in comparisons:
        left_by_seed = groups[left_label]
        right_by_seed = groups[right_label]
        seeds = sorted(set(left_by_seed).intersection(right_by_seed))
        if len(seeds) < 2:
            continue
        left_values = [left_by_seed[seed] for seed in seeds]
        right_values = [right_by_seed[seed] for seed in seeds]
        diffs = [left - right for left, right in zip(left_values, right_values)]
        mean_diff = statistics.mean(diffs)
        sd_diff = sample_std(diffs)
        se = sd_diff / math.sqrt(len(diffs)) if len(diffs) > 1 else 0.0
        crit = t_critical(0.95, len(diffs) - 1) if len(diffs) > 1 else 0.0
        ci_low = mean_diff - crit * se
        ci_high = mean_diff + crit * se
        dz = mean_diff / sd_diff if sd_diff else (math.inf if mean_diff > 0 else 0.0)
        paired_p = paired_t_p_value(diffs)
        results.append(
            {
                "comparison": f"{left_label} vs {right_label}",
                "left_label": left_label,
                "right_label": right_label,
                "paired_count": len(seeds),
                "paired_seeds": ";".join(str(seed) for seed in seeds),
                "left_mean": statistics.mean(left_values),
                "right_mean": statistics.mean(right_values),
                "mean_diff": mean_diff,
                "ci95_low": ci_low,
                "ci95_high": ci_high,
                "paired_t_p_value": paired_p,
                "wilcoxon_p_value": wilcoxon_p_value(diffs),
                "holm_adjusted_p_value": 0.0,
                "cohens_dz": dz,
                "welch_p_value_sensitivity": welch_p_value(left_values, right_values),
                "direction": "right_lower_is_better" if mean_diff > 0 else "left_lower_or_tie",
            }
        )
    adjusted = holm_adjust([row["paired_t_p_value"] for row in results])
    for row, p_value in zip(results, adjusted):
        row["holm_adjusted_p_value"] = p_value
    return results


def fmt(value):
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return f"{value:.6f}"
    return str(value)


def write_csv(path, rows):
    fieldnames = [
        "comparison",
        "left_label",
        "right_label",
        "paired_count",
        "paired_seeds",
        "left_mean",
        "right_mean",
        "mean_diff",
        "ci95_low",
        "ci95_high",
        "paired_t_p_value",
        "wilcoxon_p_value",
        "holm_adjusted_p_value",
        "cohens_dz",
        "welch_p_value_sensitivity",
        "direction",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt(row[key]) for key in fieldnames})


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def write_txt(path, rows):
    lines = [
        "Paired formal statistics",
        "",
        "Mean difference is left global_best minus right global_best; positive values mean the right-hand configuration has shorter tours.",
        "Holm-Bonferroni is applied to paired t-test p-values. Welch t-test is retained only as a sensitivity reference.",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "comparison",
                "n",
                "mean_diff",
                "95% CI",
                "paired_t_p",
                "wilcoxon_p",
                "Holm-Bonferroni p",
                "Cohen dz",
            ],
            [
                [
                    row["comparison"],
                    str(row["paired_count"]),
                    f"{row['mean_diff']:.3f}",
                    f"[{row['ci95_low']:.3f}, {row['ci95_high']:.3f}]",
                    fmt(row["paired_t_p_value"]),
                    fmt(row["wilcoxon_p_value"]),
                    fmt(row["holm_adjusted_p_value"]),
                    fmt(row["cohens_dz"]),
                ]
                for row in rows
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_paths(argv):
    input_path = Path(argv[1]) if len(argv) > 1 else ROOT / "results" / "final_experiment_results.csv"
    output_csv = Path(argv[2]) if len(argv) > 2 else ROOT / "results" / "final_paired_statistics.csv"
    output_txt = Path(argv[3]) if len(argv) > 3 else ROOT / "results" / "final_paired_statistics.txt"
    return input_path, output_csv, output_txt


def main(argv):
    input_path, output_csv, output_txt = default_paths(argv)
    rows = read_rows(input_path)
    paired_rows = analyze(rows)
    write_csv(output_csv, paired_rows)
    write_txt(output_txt, paired_rows)
    print(Path(output_txt).read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main(sys.argv)
