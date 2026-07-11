#include <mpi.h>

#include "tsp_scratch_core.h"

static void print_usage(const char *program, int rank)
{
    if (rank == 0) {
        fprintf(stderr,
                "Usage: %s input.tsp algorithm seed time_budget_sec iteration_budget output.csv [tour_output]\n"
                "Algorithms: nn2opt, greedy2opt, ils2opt\n",
                program);
    }
}

int main(int argc, char **argv)
{
    int rank = 0;
    int size = 1;
    ScratchTsp tsp;
    ScratchSearchResult local_result;
    char err[512];
    const char *input_path;
    const char *algorithm;
    const char *output_path;
    const char *tour_output_path = NULL;
    unsigned long long base_seed;
    unsigned long long rank_seed;
    double time_budget_sec;
    long iteration_budget;
    double start;
    double local_elapsed;
    double elapsed;
    int global_best;
    int *all_lengths = NULL;
    int *all_tours = NULL;

    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    if (argc != 7 && argc != 8) {
        print_usage(argv[0], rank);
        MPI_Finalize();
        return 2;
    }

    input_path = argv[1];
    algorithm = argv[2];
    base_seed = strtoull(argv[3], NULL, 10);
    time_budget_sec = strtod(argv[4], NULL);
    iteration_budget = strtol(argv[5], NULL, 10);
    output_path = argv[6];
    if (argc == 8) {
        tour_output_path = argv[7];
    }
    rank_seed = base_seed + (unsigned long long)(rank + 1) * 1000003ULL;

    if (strcmp(algorithm, "nn2opt") != 0 &&
        strcmp(algorithm, "greedy2opt") != 0 &&
        strcmp(algorithm, "ils2opt") != 0) {
        if (rank == 0) {
            fprintf(stderr, "unknown scratch algorithm: %s\n", algorithm);
        }
        MPI_Finalize();
        return 2;
    }

    memset(&tsp, 0, sizeof(tsp));
    if (!scratch_read_tsp(input_path, &tsp, err, sizeof(err))) {
        fprintf(stderr, "[rank %d] %s\n", rank, err);
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }

    MPI_Barrier(MPI_COMM_WORLD);
    start = scratch_seconds();
    memset(&local_result, 0, sizeof(local_result));
    if (!scratch_run_search(&tsp, algorithm, rank_seed, time_budget_sec, iteration_budget, &local_result)) {
        fprintf(stderr, "[rank %d] scratch search failed\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }
    local_elapsed = scratch_seconds() - start;

    MPI_Reduce(&local_result.best_length, &global_best, 1, MPI_INT, MPI_MIN, 0, MPI_COMM_WORLD);
    MPI_Reduce(&local_elapsed, &elapsed, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
    if (rank == 0) {
        all_lengths = (int *)malloc((size_t)size * sizeof(int));
        all_tours = (int *)malloc((size_t)size * (size_t)tsp.n * sizeof(int));
        if (!all_lengths || !all_tours) {
            fprintf(stderr, "failed to allocate MPI tour gather buffers\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
            return 1;
        }
    }
    MPI_Gather(&local_result.best_length, 1, MPI_INT, all_lengths, 1, MPI_INT, 0, MPI_COMM_WORLD);
    MPI_Gather(local_result.best_tour, tsp.n, MPI_INT, all_tours, tsp.n, MPI_INT, 0, MPI_COMM_WORLD);

    if (rank == 0) {
        int best_rank = 0;
        for (int i = 1; i < size; ++i) {
            if (all_lengths[i] < all_lengths[best_rank]) {
                best_rank = i;
            }
        }
        if (!scratch_append_result(output_path, algorithm, size, "mpi", base_seed, time_budget_sec,
                                   iteration_budget, global_best, elapsed)) {
            MPI_Abort(MPI_COMM_WORLD, 1);
            return 1;
        }
        if (tour_output_path &&
            !scratch_write_tour_file(tour_output_path, algorithm, size, "mpi", base_seed,
                                     global_best, all_tours + ((size_t)best_rank * (size_t)tsp.n), tsp.n)) {
            MPI_Abort(MPI_COMM_WORLD, 1);
            return 1;
        }
        printf("SCRATCH_MPI algorithm=%s nproc=%d seed=%llu best_length=%d elapsed=%.6f\n",
               scratch_algorithm_label(algorithm),
               size,
               base_seed,
               global_best,
               elapsed);
        free(all_lengths);
        free(all_tours);
    }

    scratch_free_search_result(&local_result);
    scratch_free_tsp(&tsp);
    MPI_Finalize();
    return 0;
}
