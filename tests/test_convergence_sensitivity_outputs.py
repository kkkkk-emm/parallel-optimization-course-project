import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_convergence_sensitivity_artifacts_are_complete():
    required = [
        ROOT / "scripts/run_convergence_sensitivity.ps1",
        ROOT / "scripts/analyze_convergence_sensitivity.py",
        ROOT / "results/convergence_sensitivity_results.csv",
        ROOT / "results/convergence_sensitivity_summary.txt",
        ROOT / "results/convergence_sensitivity_summary.csv",
        ROOT / "reports/05_convergence_sensitivity.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert missing == []


def test_convergence_sensitivity_csv_shape_and_values():
    csv_path = ROOT / "results/convergence_sensitivity_results.csv"
    with csv_path.open(newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))

    assert len(rows) == 36

    expected_seeds = {"12345", "22345", "32345"}
    expected_groups = {
        ("SERIAL", "1", "1000", "0"),
        ("SERIAL", "1", "3000", "0"),
        ("SERIAL", "1", "5000", "0"),
        ("DEA", "4", "1000", "0"),
        ("DEA", "4", "3000", "0"),
        ("DEA", "4", "5000", "0"),
        ("HDEA", "4", "1000", "2"),
        ("HDEA", "4", "3000", "2"),
        ("HDEA", "4", "5000", "2"),
        ("MOVING_HDEA", "4", "1000", "2"),
        ("MOVING_HDEA", "4", "3000", "2"),
        ("MOVING_HDEA", "4", "5000", "2"),
    }

    seen = defaultdict(set)
    duplicate_keys = Counter()
    for row in rows:
        group_key = (row["algorithm"], row["nproc"], row["maxGen"], row["num_groups"])
        seen[group_key].add(row["base_seed"])
        duplicate_keys[
            (
                row["algorithm"],
                row["nproc"],
                row["maxGen"],
                row["migration_interval"],
                row["local_to_global_ratio"],
                row["num_groups"],
                row["base_seed"],
            )
        ] += 1
        for field in ("global_best", "elapsed_sec"):
            value = float(row[field])
            assert math.isfinite(value)

    assert set(seen) == expected_groups
    assert all(seeds == expected_seeds for seeds in seen.values())
    assert all(count == 1 for count in duplicate_keys.values())


def test_convergence_sensitivity_report_contains_required_evidence():
    report = (ROOT / "reports/05_convergence_sensitivity.md").read_text(encoding="utf-8-sig")
    for text in [
        "SERIAL n=1",
        "DEA n=4",
        "HDEA n=4 groups=2",
        "MOVING_HDEA n=4 groups=2",
        "maxGen=1000",
        "maxGen=3000",
        "maxGen=5000",
        "不替代正式实验",
        "不做强 t-test 结论",
    ]:
        assert text in report
