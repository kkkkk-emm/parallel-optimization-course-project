import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


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


def algorithm_key(row_or_key):
    if isinstance(row_or_key, tuple):
        return (row_or_key[0], row_or_key[1], row_or_key[3], row_or_key[4], row_or_key[5])
    return (
        row_or_key["algorithm"],
        row_or_key["nproc"],
        row_or_key["migration_interval"],
        row_or_key["local_to_global_ratio"],
        row_or_key["num_groups"],
    )


def algorithm_label(key):
    algorithm, nproc, migration_interval, ratio, groups = key
    if algorithm in {"HDEA", "MOVING_HDEA"}:
        return f"{algorithm} n={nproc} groups={groups}"
    return f"{algorithm} n={nproc}"


def grouped(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)
    return groups


def sample_std(values):
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def summarize(groups):
    summary = []
    for key, rows in groups.items():
        algorithm, nproc, max_gen, migration_interval, ratio, groups_count = key
        best_values = [row["global_best"] for row in rows]
        elapsed_values = [row["elapsed_sec"] for row in rows]
        summary.append(
            {
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
                "min": min(best_values),
                "max": max(best_values),
                "avg_time": statistics.mean(elapsed_values),
            }
        )
    return sorted(
        summary,
        key=lambda row: (
            ALGORITHM_ORDER.get(row["algorithm"], 99),
            row["nproc"],
            row["num_groups"],
            row["maxGen"],
        ),
    )


def compute_improvements(summaries):
    by_algorithm = defaultdict(dict)
    for row in summaries:
        by_algorithm[algorithm_key(row)][row["maxGen"]] = row

    improvements = []
    for key, by_max in sorted(
        by_algorithm.items(),
        key=lambda item: (
            ALGORITHM_ORDER.get(item[0][0], 99),
            item[0][1],
            item[0][4],
        ),
    ):
        if 1000 not in by_max or 5000 not in by_max:
            continue
        mean_1000 = by_max[1000]["mean"]
        mean_5000 = by_max[5000]["mean"]
        improvement_abs = mean_1000 - mean_5000
        improvement_pct = improvement_abs / mean_1000 * 100.0 if mean_1000 else math.nan
        means = [by_max[max_gen]["mean"] for max_gen in sorted(by_max)]
        max_gens = sorted(by_max)
        non_increasing = all(means[i + 1] <= means[i] for i in range(len(means) - 1))
        strictly_decreasing = all(means[i + 1] < means[i] for i in range(len(means) - 1))
        improvements.append(
            {
                "algorithm_label": algorithm_label(key),
                "algorithm": key[0],
                "nproc": key[1],
                "migration_interval": key[2],
                "local_to_global_ratio": key[3],
                "num_groups": key[4],
                "mean_1000": mean_1000,
                "mean_5000": mean_5000,
                "improvement_abs": improvement_abs,
                "improvement_pct": improvement_pct,
                "maxGen_sequence": "->".join(str(value) for value in max_gens),
                "mean_sequence": "->".join(f"{value:.3f}" for value in means),
                "non_increasing": non_increasing,
                "strictly_decreasing": strictly_decreasing,
            }
        )
    return improvements


def compute_rankings(summaries):
    by_max = defaultdict(list)
    for row in summaries:
        by_max[row["maxGen"]].append(row)

    rankings = []
    for max_gen in sorted(by_max):
        sorted_rows = sorted(by_max[max_gen], key=lambda row: row["mean"])
        for rank, row in enumerate(sorted_rows, start=1):
            rankings.append(
                {
                    "maxGen": max_gen,
                    "rank": rank,
                    "algorithm_label": algorithm_label(algorithm_key(row)),
                    "mean": row["mean"],
                    "best": row["best"],
                }
            )
    return rankings


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def build_report(summaries, improvements, rankings):
    lines = []
    lines.append("Grouped statistics")
    lines.extend(
        markdown_table(
            [
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
                "min",
                "max",
                "avg_time",
            ],
            [
                [
                    row["algorithm"],
                    str(row["nproc"]),
                    str(row["maxGen"]),
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
    lines.append("Improvement from maxGen=1000 to maxGen=5000")
    lines.extend(
        markdown_table(
            [
                "algorithm",
                "mean_1000",
                "mean_5000",
                "improvement_abs",
                "improvement_pct",
                "mean_sequence",
                "non_increasing",
                "strictly_decreasing",
            ],
            [
                [
                    row["algorithm_label"],
                    f"{row['mean_1000']:.3f}",
                    f"{row['mean_5000']:.3f}",
                    f"{row['improvement_abs']:.3f}",
                    f"{row['improvement_pct']:.3f}%",
                    row["mean_sequence"],
                    "yes" if row["non_increasing"] else "no",
                    "yes" if row["strictly_decreasing"] else "no",
                ]
                for row in improvements
            ],
        )
    )
    lines.append("")
    lines.append("Mean ranking by maxGen")
    lines.extend(
        markdown_table(
            ["maxGen", "rank", "algorithm", "mean", "best"],
            [
                [
                    str(row["maxGen"]),
                    str(row["rank"]),
                    row["algorithm_label"],
                    f"{row['mean']:.3f}",
                    f"{row['best']:.0f}",
                ]
                for row in rankings
            ],
        )
    )
    lines.append("")
    lines.append("Trend conclusion")
    decreasing_count = sum(1 for row in improvements if row["strictly_decreasing"])
    lines.append(
        f"Strictly decreasing mean sequences: {decreasing_count}/{len(improvements)} algorithms."
    )
    if rankings:
        best_5000 = min(
            (row for row in rankings if row["maxGen"] == 5000),
            key=lambda row: row["mean"],
        )
        lines.append(
            f"Best mean at maxGen=5000: {best_5000['algorithm_label']} mean={best_5000['mean']:.3f}."
        )
    lines.append("No Welch t-test conclusion is made for this supplemental 3-seed experiment.")
    return "\n".join(lines) + "\n"


def write_summary_csv(path, summaries, improvements, rankings):
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
        "min",
        "max",
        "avg_time",
        "algorithm_label",
        "mean_1000",
        "mean_5000",
        "improvement_abs",
        "improvement_pct",
        "maxGen_sequence",
        "mean_sequence",
        "non_increasing",
        "strictly_decreasing",
        "rank",
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
                    "best": f"{row['best']:.0f}",
                    "mean": f"{row['mean']:.6f}",
                    "std": f"{row['std']:.6f}",
                    "min": f"{row['min']:.0f}",
                    "max": f"{row['max']:.0f}",
                    "avg_time": f"{row['avg_time']:.6f}",
                }
            )
        for row in improvements:
            writer.writerow(
                {
                    "record_type": "improvement",
                    "algorithm": row["algorithm"],
                    "nproc": row["nproc"],
                    "migration_interval": row["migration_interval"],
                    "local_to_global_ratio": row["local_to_global_ratio"],
                    "num_groups": row["num_groups"],
                    "algorithm_label": row["algorithm_label"],
                    "mean_1000": f"{row['mean_1000']:.6f}",
                    "mean_5000": f"{row['mean_5000']:.6f}",
                    "improvement_abs": f"{row['improvement_abs']:.6f}",
                    "improvement_pct": f"{row['improvement_pct']:.6f}",
                    "maxGen_sequence": row["maxGen_sequence"],
                    "mean_sequence": row["mean_sequence"],
                    "non_increasing": "yes" if row["non_increasing"] else "no",
                    "strictly_decreasing": "yes" if row["strictly_decreasing"] else "no",
                }
            )
        for row in rankings:
            writer.writerow(
                {
                    "record_type": "ranking",
                    "maxGen": row["maxGen"],
                    "algorithm_label": row["algorithm_label"],
                    "mean": f"{row['mean']:.6f}",
                    "best": f"{row['best']:.0f}",
                    "rank": row["rank"],
                }
            )


def default_paths(argv):
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir if (script_dir / "src").exists() else script_dir.parent
    input_path = (
        argv[1]
        if len(argv) > 1
        else str(project_root / "results" / "convergence_sensitivity_results.csv")
    )
    summary_path = (
        argv[2]
        if len(argv) > 2
        else str(project_root / "results" / "convergence_sensitivity_summary.txt")
    )
    summary_csv_path = (
        argv[3]
        if len(argv) > 3
        else str(project_root / "results" / "convergence_sensitivity_summary.csv")
    )
    return input_path, summary_path, summary_csv_path


def main(argv):
    input_path, summary_path, summary_csv_path = default_paths(argv)
    rows = read_rows(input_path)
    groups = grouped(rows)
    summaries = summarize(groups)
    improvements = compute_improvements(summaries)
    rankings = compute_rankings(summaries)
    report = build_report(summaries, improvements, rankings)
    print(report, end="")
    Path(summary_path).write_text(report, encoding="utf-8")
    write_summary_csv(summary_csv_path, summaries, improvements, rankings)


if __name__ == "__main__":
    main(sys.argv)
