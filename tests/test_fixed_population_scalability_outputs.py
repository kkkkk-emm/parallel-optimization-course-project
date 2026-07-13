import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
RESULTS = ROOT / "results"
REPORT = ROOT / "reports" / "final_report_draft.md"


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def write_fixed_population_fixture(path: Path):
    rows = [
        ("SERIAL", 1, 1000, 0, 0, 0, 400, 400, 101, 100.0, 4.0, 0.0, 0.0, 0.0, 4.0, 0.0),
        ("SERIAL", 1, 1000, 0, 0, 0, 400, 400, 202, 102.0, 4.2, 0.0, 0.0, 0.0, 4.2, 0.0),
        ("DEA", 2, 1000, 100, 0, 0, 200, 400, 101, 91.0, 2.4, 0.10, 0.05, 0.15, 2.25, 0.0625),
        ("DEA", 2, 1000, 100, 0, 0, 200, 400, 202, 93.0, 2.6, 0.11, 0.05, 0.16, 2.44, 0.0615),
        ("DEA", 4, 1000, 100, 0, 0, 100, 400, 101, 88.0, 1.8, 0.15, 0.07, 0.22, 1.58, 0.1222),
        ("DEA", 4, 1000, 100, 0, 0, 100, 400, 202, 86.0, 1.9, 0.16, 0.07, 0.23, 1.67, 0.1211),
    ]
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "algorithm",
                "nproc",
                "maxGen",
                "migration_interval",
                "local_to_global_ratio",
                "num_groups",
                "local_colony_size",
                "total_colony_size",
                "base_seed",
                "global_best",
                "elapsed_sec",
                "migration_comm_sec",
                "final_collective_comm_sec",
                "mpi_comm_sec",
                "computation_sec",
                "comm_ratio",
            ]
        )
        writer.writerows(rows)


def test_fixed_population_analyzer_outputs_scalability_and_comm_metrics(tmp_path):
    analyzer = SCRIPTS / "analyze_fixed_population.py"
    input_csv = tmp_path / "fixed_population_results.csv"
    summary_csv = tmp_path / "fixed_population_summary.csv"
    summary_txt = tmp_path / "fixed_population_summary.txt"
    write_fixed_population_fixture(input_csv)

    result = subprocess.run(
        [sys.executable, str(analyzer), str(input_csv), str(summary_csv), str(summary_txt)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    rows = read_csv(summary_csv)
    assert rows
    required = {
        "total_colony_size",
        "avg_migration_comm_sec",
        "avg_mpi_comm_sec",
        "avg_computation_sec",
        "avg_comm_ratio",
        "speedup_vs_serial",
        "efficiency_vs_serial",
        "improvement_vs_fixed_serial_mean_pct",
    }
    assert required.issubset(rows[0].keys())
    dea4 = next(row for row in rows if row["algorithm"] == "DEA" and row["nproc"] == "4")
    assert float(dea4["speedup_vs_serial"]) > 1.0
    assert float(dea4["efficiency_vs_serial"]) > 0.0
    text = summary_txt.read_text(encoding="utf-8")
    assert "Fixed population experiment summary" in text
    assert "communication time" in text


def test_fixed_population_runner_contract_and_protected_outputs():
    runner = SCRIPTS / "run_fixed_population_experiment.ps1"
    assert runner.exists()
    text = runner.read_text(encoding="utf-8-sig")
    assert "results/fixed_population_results.csv" in text
    assert "SERIAL"; assert "N_COLONY=400" in text
    assert "DEA"; assert "N_COLONY=200" in text
    assert "TotalColonySize = 400" in text
    assert "LocalColonySize = 400" in text
    assert "LocalColonySize = 200" in text
    assert "LocalColonySize = 100" in text
    assert "migration_comm_sec" in text
    assert "results/final_experiment_results.csv" in text
    assert "Assert-NotProtectedResultPath" in text


def test_version_a_sources_support_colony_override_and_comm_timing():
    serial = (SRC / "tsp_serial_exp.c").read_text(encoding="utf-8-sig")
    assert "#ifndef N_COLONY" in serial
    assert "int xColony = N_COLONY;" in serial

    for name in ["tsp_mpi_dea.c", "tsp_mpi_hdea.c", "tsp_mpi_moving_hdea.c"]:
        text = (SRC / name).read_text(encoding="utf-8-sig")
        assert "#ifndef N_COLONY" in text
        assert "int xColony = N_COLONY;" in text
        assert "migrationCommElapsed" in text
        assert "finalCollectiveCommElapsed" in text
        assert "migration_comm_sec" in text
        assert "final_collective_comm_sec" in text
        assert "mpi_comm_sec" in text
        assert "comm_ratio" in text


def test_scalability_figures_and_report_references_exist_when_generated():
    figure_script = SCRIPTS / "generate_report_figures.py"
    text = figure_script.read_text(encoding="utf-8-sig")
    assert "fixed_population_summary.csv" in text
    assert "fig_fixed_population_scalability.png" in text
    assert "fig_fixed_population_comm_breakdown.png" in text

    report = REPORT.read_text(encoding="utf-8-sig")
    assert "Fixed population experiment" in report
    assert "communication time" in report
    assert "speedup" in report
    assert "efficiency" in report

    for filename in ["fig_fixed_population_scalability.png", "fig_fixed_population_comm_breakdown.png"]:
        path = RESULTS / "figures" / filename
        if path.exists():
            assert path.stat().st_size > 1000
