import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
RESULTS = ROOT / "results"


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def write_final_fixture(path: Path):
    rows = [
        ("SERIAL", 1, 1000, 0, 0, 0, 101, 100.0, 1.0),
        ("SERIAL", 1, 1000, 0, 0, 0, 202, 110.0, 1.1),
        ("SERIAL", 1, 1000, 0, 0, 0, 303, 120.0, 1.2),
        ("DEA", 2, 1000, 100, 0, 0, 101, 90.0, 2.0),
        ("DEA", 2, 1000, 100, 0, 0, 202, 95.0, 2.1),
        ("DEA", 2, 1000, 100, 0, 0, 303, 99.0, 2.2),
        ("HDEA", 4, 1000, 100, 5, 2, 101, 92.0, 2.5),
        ("HDEA", 4, 1000, 100, 5, 2, 202, 93.0, 2.6),
        ("HDEA", 4, 1000, 100, 5, 2, 303, 94.0, 2.7),
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
                "base_seed",
                "global_best",
                "elapsed_sec",
            ]
        )
        writer.writerows(rows)


def write_tour_fixture(data_path: Path, results_path: Path, tour_dir: Path):
    data_path.write_text(
        "\n".join(
            [
                "4",
                "1 0 0",
                "2 10 0",
                "3 10 10",
                "4 0 10",
                "EOF",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with results_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
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
        )
        writer.writerow(["SERIAL", 1, 10, 0, 0, 0, 101, 40, 0.1])
        writer.writerow(["DEA", 2, 10, 5, 0, 0, 101, 40, 0.2])

    tour_dir.mkdir()
    (tour_dir / "best_SERIAL_n1_seed101.tour").write_text(
        "# algorithm=SERIAL\n# nproc=1\n# seed=101\n# best_length=40\n1 2 3 4\n",
        encoding="utf-8",
    )
    (tour_dir / "best_DEA_n2_seed101.tour").write_text(
        "# algorithm=DEA\n# nproc=2\n# seed=101\n# best_length=40\n1 2 3 4\n",
        encoding="utf-8",
    )


def test_paired_statistics_analyzer_outputs_required_fields(tmp_path):
    analyzer = SCRIPTS / "analyze_paired_statistics.py"
    input_csv = tmp_path / "final_fixture.csv"
    output_csv = tmp_path / "paired.csv"
    output_txt = tmp_path / "paired.txt"
    write_final_fixture(input_csv)

    result = subprocess.run(
        [sys.executable, str(analyzer), str(input_csv), str(output_csv), str(output_txt)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    rows = read_csv(output_csv)
    assert rows
    required = {
        "comparison",
        "paired_count",
        "mean_diff",
        "ci95_low",
        "ci95_high",
        "paired_t_p_value",
        "wilcoxon_p_value",
        "holm_adjusted_p_value",
        "cohens_dz",
        "welch_p_value_sensitivity",
    }
    assert required.issubset(rows[0].keys())
    assert any(row["comparison"] == "SERIAL n=1 vs DEA n=2" for row in rows)
    assert "Holm-Bonferroni" in output_txt.read_text(encoding="utf-8")


def test_version_a_tour_verifier_accepts_fixture(tmp_path):
    verifier = SCRIPTS / "verify_version_a_tours.py"
    data_path = tmp_path / "tiny.tsp"
    results_path = tmp_path / "results.csv"
    tour_dir = tmp_path / "tours"
    write_tour_fixture(data_path, results_path, tour_dir)

    result = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--data",
            str(data_path),
            "--results",
            str(results_path),
            "--tour-dir",
            str(tour_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "VERSION_A_TOUR_VERIFY_OK" in result.stdout
    assert "verified_tours=2" in result.stdout


def test_version_a_sources_use_portable_random_and_optional_tour_output():
    source_names = [
        "tsp_serial_exp.c",
        "tsp_mpi_dea.c",
        "tsp_mpi_hdea.c",
        "tsp_mpi_moving_hdea.c",
    ]
    for name in source_names:
        text = (SRC / name).read_text(encoding="utf-8-sig")
        assert "rand() / 32768.0" not in text
        assert "RAND_MAX + 1.0" in text
        assert "tourOutputPath" in text
        assert "write_tour_file" in text
        if name.startswith("tsp_mpi"):
            assert "MPI_Gather(colony[ibest]" in text or "MPI_Gather(&colony[ibest][0]" in text
            assert "verbose" in text


def test_equal_budget_runner_and_results_contract():
    runner = SCRIPTS / "run_equal_budget_experiment.ps1"
    analyzer = SCRIPTS / "analyze_equal_budget.py"
    assert runner.exists()
    assert analyzer.exists()

    runner_text = runner.read_text(encoding="utf-8-sig")
    assert "results/equal_budget_results.csv" in runner_text
    assert "results/final_experiment_results.csv" in runner_text
    assert "Assert-NotProtectedResultPath" in runner_text
    assert "LocalColonySize = 100" in runner_text
    assert "LocalColonySize = 50" in runner_text
    assert "LocalColonySize = 25" in runner_text

    if (RESULTS / "equal_budget_results.csv").exists():
        rows = read_csv(RESULTS / "equal_budget_results.csv")
        assert len(rows) >= 15
        assert {row["total_colony_size"] for row in rows} == {"100"}
        assert {row["local_colony_size"] for row in rows}.issuperset({"100", "50", "25"})


def test_dependency_manifest_declares_analysis_and_test_dependencies():
    requirements = ROOT / "requirements.txt"
    assert requirements.exists()
    text = requirements.read_text(encoding="utf-8").lower()
    for package in ["numpy", "matplotlib", "scipy", "pytest"]:
        assert package in text
    assert "python" in text

