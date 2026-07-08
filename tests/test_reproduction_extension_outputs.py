import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "scripts/analyze_reproduction_extension.py"
RUNNER = ROOT / "scripts/run_reproduction_extension.ps1"
REPORT = ROOT / "reports/06_reproduction_extension.md"
RESULTS = ROOT / "results/reproduction_extension_results.csv"


FIELDNAMES = [
    "algorithm",
    "nproc",
    "maxGen",
    "migration_interval",
    "local_to_global_ratio",
    "num_groups",
    "base_seed",
    "global_best",
    "elapsed_sec",
]


def write_fixture(path: Path):
    rows = [
        ("SERIAL", 1, 5000, 0, 0, 0, 12345, 200000, 10.0),
        ("SERIAL", 1, 5000, 0, 0, 0, 22345, 205000, 10.5),
        ("SERIAL", 1, 5000, 0, 0, 0, 32345, 210000, 11.0),
        ("SERIAL", 1, 5000, 0, 0, 0, 42345, 215000, 11.5),
        ("SERIAL", 1, 5000, 0, 0, 0, 52345, 220000, 12.0),
        ("DEA", 4, 5000, 25, 0, 0, 12345, 180000, 12.0),
        ("DEA", 4, 5000, 25, 0, 0, 22345, 182000, 12.5),
        ("DEA", 4, 5000, 25, 0, 0, 32345, 184000, 13.0),
        ("DEA", 4, 5000, 25, 0, 0, 42345, 186000, 13.5),
        ("DEA", 4, 5000, 25, 0, 0, 52345, 188000, 14.0),
    ]
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(FIELDNAMES)
        writer.writerows(rows)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def test_analyzer_outputs_extended_statistics(tmp_path):
    input_csv = tmp_path / "fixture_results.csv"
    summary_txt = tmp_path / "fixture_summary.txt"
    summary_csv = tmp_path / "fixture_summary.csv"
    write_fixture(input_csv)

    result = subprocess.run(
        [sys.executable, str(ANALYZER), str(input_csv), str(summary_txt), str(summary_csv)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert summary_txt.exists()
    assert summary_csv.exists()

    rows = read_csv(summary_csv)
    summary_rows = [row for row in rows if row["record_type"] == "summary"]
    ttest_rows = [row for row in rows if row["record_type"] == "ttest"]
    criteria_rows = [row for row in rows if row["record_type"] == "criteria"]

    dea = next(row for row in summary_rows if row["algorithm"] == "DEA")
    assert dea["median"] == "184000.000000"
    assert dea["time_median"] == "13.000000"
    assert dea["improvement_vs_serial_mean_pct"] == "12.380952"
    assert dea["success_below_serial_median_count"] == "5"
    assert dea["success_below_serial_best_count"] == "5"

    test = next(row for row in ttest_rows if row["comparison"] == "SERIAL n=1 vs DEA n=4")
    assert test["hedges_g"] != ""
    assert test["mean_diff_ci_low"] != ""
    assert test["mean_diff_ci_high"] != ""
    assert test["p_value"] != ""

    criteria = next(row for row in criteria_rows if row["algorithm"] == "DEA")
    assert criteria["better_than_serial_mean"] == "yes"
    assert criteria["better_than_serial_median"] == "yes"

    text = summary_txt.read_text(encoding="utf-8")
    assert "Extended grouped statistics" in text
    assert "Hedges" in text
    assert "success_below_serial_median" in text


def test_runner_defaults_and_protected_result_guards():
    text = RUNNER.read_text(encoding="utf-8-sig")
    assert 'results/reproduction_extension_results.csv' in text
    assert 'results/final_experiment_results.csv' in text
    assert 'results/final_analysis_summary.csv' in text
    assert 'results/final_analysis_summary.txt' in text
    assert "Assert-NotProtectedResultPath" in text
    assert "$MaxGen = 5000" in text
    assert "$MigrationInterval = 25" in text
    assert "$LocalToGlobalRatio = 20" in text
    assert "12345,22345,32345,42345,52345" in text
    assert "reproduction_extension_results.csv.bak-" in text


def test_report_documents_scope_and_outputs():
    text = REPORT.read_text(encoding="utf-8-sig")
    for expected in [
        "缩小版机制复现",
        "不能声称完全复现论文",
        "results/reproduction_extension_results.csv",
        "results/reproduction_extension_summary.csv",
        "results/reproduction_extension_summary.txt",
        "运行时间不作为 speedup 结论",
        "local_to_global_ratio=20",
    ]:
        assert expected in text


def test_real_reproduction_results_shape_if_present():
    if not RESULTS.exists():
        return

    rows = read_csv(RESULTS)
    assert len(rows) == 35

    expected_seeds = {"12345", "22345", "32345", "42345", "52345"}
    expected_groups = {
        ("SERIAL", "1", "5000", "0", "0", "0"),
        ("DEA", "4", "5000", "25", "0", "0"),
        ("HDEA", "4", "5000", "25", "20", "2"),
        ("MOVING_HDEA", "4", "5000", "25", "20", "2"),
        ("DEA", "9", "5000", "25", "0", "0"),
        ("HDEA", "9", "5000", "25", "20", "3"),
        ("MOVING_HDEA", "9", "5000", "25", "20", "3"),
    }

    seen = {}
    duplicate_keys = set()
    for row in rows:
        group = (
            row["algorithm"],
            row["nproc"],
            row["maxGen"],
            row["migration_interval"],
            row["local_to_global_ratio"],
            row["num_groups"],
        )
        seen.setdefault(group, set()).add(row["base_seed"])
        key = group + (row["base_seed"],)
        assert key not in duplicate_keys
        duplicate_keys.add(key)
        assert float(row["global_best"]) > 0
        assert float(row["elapsed_sec"]) > 0

    assert set(seen) == expected_groups
    assert all(seeds == expected_seeds for seeds in seen.values())
