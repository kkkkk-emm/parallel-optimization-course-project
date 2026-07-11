#include "tsp_scratch_core.h"

static void print_usage(const char *program)
{
    fprintf(stderr,
            "Usage: %s --smoke\n"
            "   or: %s input.tsp algorithm seed time_budget_sec iteration_budget output.csv [tour_output]\n"
            "Algorithms: nn2opt, greedy2opt, ils2opt\n",
            program,
            program);
}

int main(int argc, char **argv)
{
    ScratchTsp tsp;
    ScratchSearchResult result;
    char err[512];
    const char *input_path;
    const char *algorithm;
    const char *output_path;
    const char *tour_output_path = NULL;
    unsigned long long seed;
    double time_budget_sec;
    long iteration_budget;
    double start;
    double elapsed;

    if (argc == 2 && strcmp(argv[1], "--smoke") == 0) {
        return scratch_smoke_test();
    }
    if (argc != 7 && argc != 8) {
        print_usage(argv[0]);
        return 2;
    }

    input_path = argv[1];
    algorithm = argv[2];
    seed = strtoull(argv[3], NULL, 10);
    time_budget_sec = strtod(argv[4], NULL);
    iteration_budget = strtol(argv[5], NULL, 10);
    output_path = argv[6];
    if (argc == 8) {
        tour_output_path = argv[7];
    }

    if (strcmp(algorithm, "nn2opt") != 0 &&
        strcmp(algorithm, "greedy2opt") != 0 &&
        strcmp(algorithm, "ils2opt") != 0) {
        fprintf(stderr, "unknown scratch algorithm: %s\n", algorithm);
        return 2;
    }

    memset(&tsp, 0, sizeof(tsp));
    if (!scratch_read_tsp(input_path, &tsp, err, sizeof(err))) {
        fprintf(stderr, "%s\n", err);
        return 1;
    }

    start = scratch_seconds();
    memset(&result, 0, sizeof(result));
    if (!scratch_run_search(&tsp, algorithm, seed, time_budget_sec, iteration_budget, &result)) {
        fprintf(stderr, "scratch search failed\n");
        scratch_free_tsp(&tsp);
        return 1;
    }
    elapsed = scratch_seconds() - start;

    if (!scratch_append_result(output_path, algorithm, 1, "serial", seed, time_budget_sec,
                               iteration_budget, result.best_length, elapsed)) {
        scratch_free_tsp(&tsp);
        scratch_free_search_result(&result);
        return 1;
    }
    if (tour_output_path &&
        !scratch_write_tour_file(tour_output_path, algorithm, 1, "serial", seed,
                                 result.best_length, result.best_tour, tsp.n)) {
        scratch_free_tsp(&tsp);
        scratch_free_search_result(&result);
        return 1;
    }

    printf("SCRATCH_SERIAL algorithm=%s seed=%llu best_length=%d elapsed=%.6f iterations=%ld\n",
           scratch_algorithm_label(algorithm),
           seed,
           result.best_length,
           elapsed,
           result.iterations);
    scratch_free_search_result(&result);
    scratch_free_tsp(&tsp);
    return 0;
}
