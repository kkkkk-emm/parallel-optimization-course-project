import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src_scratch"
SERIAL_SRC = SRC_DIR / "tsp_scratch_serial.c"
MPI_SRC = SRC_DIR / "tsp_scratch_mpi.c"
ANALYZER = ROOT / "scripts/analyze_scratch_results.py"
TOUR_VERIFIER = ROOT / "scripts/verify_scratch_tours.py"
TRIAL_RUNNER = ROOT / "scripts/run_scratch_trials.ps1"
FINAL_RUNNER = ROOT / "scripts/run_scratch_final.ps1"
TRIAL_RESULTS = ROOT / "results/scratch_algorithm_trials.csv"
FINAL_RESULTS = ROOT / "results/scratch_experiment_results.csv"
FINAL_SUMMARY = ROOT / "results/scratch_analysis_summary.csv"
BEST_TOURS_DIR = ROOT / "results/scratch_best_tours"


FIELDNAMES = [
    "algorithm",
    "nproc",
    "mode",
    "seed",
    "time_budget_sec",
    "iteration_budget",
    "best_length",
    "elapsed_sec",
]


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def write_fixture(path: Path):
    rows = [
        ("SCRATCH_ILS_2OPT", 1, "serial", 12345, 1.0, 1000, 410000, 1.0),
        ("SCRATCH_ILS_2OPT", 1, "serial", 22345, 1.0, 1000, 409000, 1.1),
        ("SCRATCH_ILS_2OPT", 1, "serial", 32345, 1.0, 1000, 408000, 1.2),
        ("SCRATCH_ILS_2OPT", 2, "mpi", 12345, 1.0, 1000, 390000, 1.3),
        ("SCRATCH_ILS_2OPT", 2, "mpi", 22345, 1.0, 1000, 391000, 1.4),
        ("SCRATCH_ILS_2OPT", 2, "mpi", 32345, 1.0, 1000, 389000, 1.5),
    ]
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(FIELDNAMES)
        writer.writerows(rows)


def test_scratch_sources_compile_and_smoke_test_runs(tmp_path):
    exe = tmp_path / "scratch_serial.exe"
    compile_result = subprocess.run(
        ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", str(SERIAL_SRC), "-lm", "-o", str(exe)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    smoke_result = subprocess.run(
        [str(exe), "--smoke"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert smoke_result.returncode == 0, smoke_result.stderr
    assert "SCRATCH_SMOKE_OK" in smoke_result.stdout


def test_scratch_runner_defaults_and_protected_result_guards():
    for path in [TRIAL_RUNNER, FINAL_RUNNER]:
        text = path.read_text(encoding="utf-8-sig")
        assert "Assert-NotProtectedResultPath" in text
        assert "results/final_experiment_results.csv" in text
        assert "results/final_analysis_summary.csv" in text
        assert "results/final_analysis_summary.txt" in text
        assert "src/TSP0.C" not in text.replace("Get-FileHash", "")

    final_text = FINAL_RUNNER.read_text(encoding="utf-8-sig")
    assert "results/scratch_experiment_results.csv" in final_text
    assert "scratch_analysis_summary.csv" in final_text
    assert "12345,22345,32345,42345,52345,62345,72345,82345,92345,102345" in final_text

    trial_text = TRIAL_RUNNER.read_text(encoding="utf-8-sig")
    assert "results/scratch_algorithm_trials.csv" in trial_text
    assert "scratch_algorithm_trials_summary.txt" in trial_text


def test_scratch_analyzer_outputs_contextual_reference_fields(tmp_path):
    input_csv = tmp_path / "scratch_fixture.csv"
    summary_csv = tmp_path / "scratch_summary.csv"
    summary_txt = tmp_path / "scratch_summary.txt"
    write_fixture(input_csv)

    result = subprocess.run(
        [sys.executable, str(ANALYZER), str(input_csv), str(summary_csv), str(summary_txt)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr

    rows = read_csv(summary_csv)
    summary_rows = [row for row in rows if row["record_type"] == "summary"]
    assert summary_rows
    for row in summary_rows:
        assert row["contextual_reference_version_a_mean"] != ""
        assert row["contextual_reference_version_a_best"] != ""
        assert row["gap_to_tsplib_optimum_pct"] != ""
        assert "beats_version_a_mean" not in row
        assert "beats_version_a_best" not in row

    text = summary_txt.read_text(encoding="utf-8")
    assert "Version A contextual reference" in text
    assert "TSPLIB optimum" in text
    assert "beats_version_a_mean" not in text
    assert "beats_version_a_best" not in text


def test_scratch_reports_document_independence_if_present():
    reports = [
        ROOT / "reports/scratch_design.md",
        ROOT / "reports/scratch_algorithm_search_log.md",
        ROOT / "reports/scratch_audit.md",
    ]
    if not all(path.exists() for path in reports):
        return

    combined = "\n".join(path.read_text(encoding="utf-8-sig") for path in reports)
    for expected in [
        "src_scratch",
        "Version B",
        "不修改 Version A",
        "tour 合法性",
        "results/scratch_experiment_results.csv",
        "results/scratch_algorithm_trials.csv",
    ]:
        assert expected in combined


def test_scratch_best_tours_verify_against_formal_results():
    assert TOUR_VERIFIER.exists()
    assert BEST_TOURS_DIR.exists()

    result = subprocess.run(
        [sys.executable, str(TOUR_VERIFIER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "SCRATCH_TOUR_VERIFY_OK" in result.stdout
    assert "verified_configs=4" in result.stdout

    expected = {
        "best_SCRATCH_ILS_2OPT_serial_n1.tour",
        "best_SCRATCH_ILS_2OPT_mpi_n2.tour",
        "best_SCRATCH_ILS_2OPT_mpi_n4.tour",
        "best_SCRATCH_ILS_2OPT_mpi_n6.tour",
    }
    actual = {path.name for path in BEST_TOURS_DIR.glob("best_*.tour")}
    assert expected.issubset(actual)


def test_scratch_audit_and_final_report_include_optimum_and_dual_route_claims():
    audit = (ROOT / "reports/scratch_audit.md").read_text(encoding="utf-8-sig")
    report = (ROOT / "reports/final_report_draft.md").read_text(encoding="utf-8-sig")
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")

    for text in [
        "TSPLIB pcb442 official optimum = 50778",
        "Version B best = 51843",
        "optimality gap = 2.10%",
        "Version B best formal mean = 52160.600",
        "mean gap = 2.72%",
    ]:
        assert text in audit

    for text in [
        "双路线",
        "Version A",
        "Version B",
        "SCRATCH_ILS_2OPT",
        "完全独立实现",
        "不是严格公平消融",
        "TSPLIB official optimum 50778",
    ]:
        assert text in report

    assert "DEA only" not in readme
    assert "DEA-only" not in readme
    assert "Version B" in readme
    assert "SCRATCH_ILS_2OPT" in readme


def test_real_scratch_results_shape_if_present():
    if not FINAL_RESULTS.exists():
        return

    rows = read_csv(FINAL_RESULTS)
    assert len(rows) >= 30

    expected_seeds = {
        "12345",
        "22345",
        "32345",
        "42345",
        "52345",
        "62345",
        "72345",
        "82345",
        "92345",
        "102345",
    }

    groups = {}
    seen_keys = set()
    for row in rows:
        for field in FIELDNAMES:
            assert row[field] != ""
        key = (row["algorithm"], row["nproc"], row["mode"], row["seed"])
        assert key not in seen_keys
        seen_keys.add(key)
        assert float(row["best_length"]) > 0
        assert float(row["elapsed_sec"]) > 0
        groups.setdefault((row["mode"], row["nproc"]), set()).add(row["seed"])

    for group in [("serial", "1"), ("mpi", "2"), ("mpi", "4")]:
        assert groups.get(group) == expected_seeds
    assert groups.get(("mpi", "6")) == expected_seeds or groups.get(("mpi", "8")) == expected_seeds

    if FINAL_SUMMARY.exists():
        summary_rows = read_csv(FINAL_SUMMARY)
        assert all("beats_version_a_mean" not in row for row in summary_rows)
        assert all("beats_version_a_best" not in row for row in summary_rows)
        assert all(row.get("gap_to_tsplib_optimum_pct") for row in summary_rows)
