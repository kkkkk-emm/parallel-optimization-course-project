#ifndef TSP_SCRATCH_CORE_H
#define TSP_SCRATCH_CORE_H

#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif

#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

typedef struct {
    int n;
    double *x;
    double *y;
    int *dist;
} ScratchTsp;

typedef struct {
    unsigned long long state;
} ScratchRng;

typedef struct {
    int best_length;
    long iterations;
    int *best_tour;
} ScratchSearchResult;

static double scratch_seconds(void)
{
#ifdef _WIN32
    static LARGE_INTEGER frequency;
    static int initialized = 0;
    LARGE_INTEGER counter;
    if (!initialized) {
        QueryPerformanceFrequency(&frequency);
        initialized = 1;
    }
    QueryPerformanceCounter(&counter);
    return (double)counter.QuadPart / (double)frequency.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
#endif
}

static void scratch_rng_seed(ScratchRng *rng, unsigned long long seed)
{
    rng->state = seed ? seed : 0x9e3779b97f4a7c15ULL;
}

static unsigned int scratch_rng_next(ScratchRng *rng)
{
    unsigned long long x = rng->state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    rng->state = x;
    return (unsigned int)(x >> 32);
}

static int scratch_rng_int(ScratchRng *rng, int limit)
{
    if (limit <= 1) {
        return 0;
    }
    return (int)(scratch_rng_next(rng) % (unsigned int)limit);
}

static int scratch_distance_at(const ScratchTsp *tsp, int a, int b)
{
    return tsp->dist[a * tsp->n + b];
}

static void scratch_free_tsp(ScratchTsp *tsp)
{
    if (!tsp) {
        return;
    }
    free(tsp->x);
    free(tsp->y);
    free(tsp->dist);
    tsp->x = NULL;
    tsp->y = NULL;
    tsp->dist = NULL;
    tsp->n = 0;
}

static int scratch_alloc_tsp(ScratchTsp *tsp, int n)
{
    memset(tsp, 0, sizeof(*tsp));
    if (n <= 1) {
        return 0;
    }
    tsp->n = n;
    tsp->x = (double *)calloc((size_t)n, sizeof(double));
    tsp->y = (double *)calloc((size_t)n, sizeof(double));
    tsp->dist = (int *)calloc((size_t)n * (size_t)n, sizeof(int));
    if (!tsp->x || !tsp->y || !tsp->dist) {
        scratch_free_tsp(tsp);
        return 0;
    }
    return 1;
}

static void scratch_build_distances(ScratchTsp *tsp)
{
    for (int i = 0; i < tsp->n; ++i) {
        for (int j = 0; j < tsp->n; ++j) {
            if (i == j) {
                tsp->dist[i * tsp->n + j] = 0;
            } else {
                double dx = tsp->x[i] - tsp->x[j];
                double dy = tsp->y[i] - tsp->y[j];
                tsp->dist[i * tsp->n + j] = (int)(sqrt(dx * dx + dy * dy) + 0.5);
            }
        }
    }
}

static int scratch_read_tsp(const char *path, ScratchTsp *tsp, char *err, size_t err_size)
{
    FILE *fp = fopen(path, "r");
    if (!fp) {
        snprintf(err, err_size, "failed to open %s: %s", path, strerror(errno));
        return 0;
    }

    int n = 0;
    if (fscanf(fp, "%d", &n) != 1 || n <= 1) {
        snprintf(err, err_size, "failed to read city count from %s", path);
        fclose(fp);
        return 0;
    }
    if (!scratch_alloc_tsp(tsp, n)) {
        snprintf(err, err_size, "failed to allocate TSP instance with %d cities", n);
        fclose(fp);
        return 0;
    }

    for (int i = 0; i < n; ++i) {
        int city_id = 0;
        double x = 0.0;
        double y = 0.0;
        if (fscanf(fp, "%d%lf%lf", &city_id, &x, &y) != 3) {
            snprintf(err, err_size, "failed to read city row %d from %s", i + 1, path);
            scratch_free_tsp(tsp);
            fclose(fp);
            return 0;
        }
        tsp->x[i] = x;
        tsp->y[i] = y;
    }
    fclose(fp);
    scratch_build_distances(tsp);
    return 1;
}

static int scratch_tour_is_valid(const int *tour, int n)
{
    char *seen = (char *)calloc((size_t)n, sizeof(char));
    if (!seen) {
        return 0;
    }
    for (int i = 0; i < n; ++i) {
        int city = tour[i];
        if (city < 0 || city >= n || seen[city]) {
            free(seen);
            return 0;
        }
        seen[city] = 1;
    }
    free(seen);
    return 1;
}

static int scratch_tour_length(const ScratchTsp *tsp, const int *tour)
{
    int total = 0;
    for (int i = 0; i < tsp->n - 1; ++i) {
        total += scratch_distance_at(tsp, tour[i], tour[i + 1]);
    }
    total += scratch_distance_at(tsp, tour[tsp->n - 1], tour[0]);
    return total;
}

static void scratch_reverse_segment(int *tour, int left, int right)
{
    while (left < right) {
        int tmp = tour[left];
        tour[left] = tour[right];
        tour[right] = tmp;
        ++left;
        --right;
    }
}

static int scratch_two_opt_first(const ScratchTsp *tsp, int *tour, int length)
{
    int n = tsp->n;
    int improved = 1;
    while (improved) {
        improved = 0;
        for (int i = 0; i < n - 1; ++i) {
            int a = tour[i];
            int b = tour[(i + 1) % n];
            for (int k = i + 2; k < n; ++k) {
                if (i == 0 && k == n - 1) {
                    continue;
                }
                int c = tour[k];
                int d = tour[(k + 1) % n];
                int delta = scratch_distance_at(tsp, a, c) + scratch_distance_at(tsp, b, d)
                    - scratch_distance_at(tsp, a, b) - scratch_distance_at(tsp, c, d);
                if (delta < 0) {
                    scratch_reverse_segment(tour, i + 1, k);
                    length += delta;
                    improved = 1;
                    goto next_pass;
                }
            }
        }
next_pass:
        ;
    }
    return length;
}

static void scratch_shuffle_tour(int *tour, int n, ScratchRng *rng)
{
    for (int i = 0; i < n; ++i) {
        tour[i] = i;
    }
    for (int i = n - 1; i > 0; --i) {
        int j = scratch_rng_int(rng, i + 1);
        int tmp = tour[i];
        tour[i] = tour[j];
        tour[j] = tmp;
    }
}

static void scratch_nearest_neighbor_tour(const ScratchTsp *tsp, int start, int randomized, ScratchRng *rng, int *tour)
{
    int n = tsp->n;
    char *used = (char *)calloc((size_t)n, sizeof(char));
    int current = start;
    tour[0] = current;
    used[current] = 1;

    for (int pos = 1; pos < n; ++pos) {
        int best_city[8];
        int best_dist[8];
        int best_count = 0;
        for (int i = 0; i < 8; ++i) {
            best_city[i] = -1;
            best_dist[i] = 2147483647;
        }

        for (int city = 0; city < n; ++city) {
            if (used[city]) {
                continue;
            }
            int d = scratch_distance_at(tsp, current, city);
            int limit = randomized ? 5 : 1;
            for (int slot = 0; slot < limit; ++slot) {
                if (d < best_dist[slot]) {
                    for (int move = limit - 1; move > slot; --move) {
                        best_dist[move] = best_dist[move - 1];
                        best_city[move] = best_city[move - 1];
                    }
                    best_dist[slot] = d;
                    best_city[slot] = city;
                    if (best_count < limit) {
                        ++best_count;
                    }
                    break;
                }
            }
        }

        int choice = randomized && best_count > 1 ? scratch_rng_int(rng, best_count) : 0;
        current = best_city[choice];
        tour[pos] = current;
        used[current] = 1;
    }
    free(used);
}

static void scratch_double_bridge(int *tour, int n, ScratchRng *rng)
{
    if (n < 12) {
        scratch_shuffle_tour(tour, n, rng);
        return;
    }

    int a = 1 + scratch_rng_int(rng, n / 4);
    int b = a + 1 + scratch_rng_int(rng, n / 4);
    int c = b + 1 + scratch_rng_int(rng, n / 4);
    int d = c + 1 + scratch_rng_int(rng, n - c - 1);
    int *copy = (int *)malloc((size_t)n * sizeof(int));
    int p = 0;
    if (!copy) {
        return;
    }
    for (int i = 0; i < a; ++i) copy[p++] = tour[i];
    for (int i = c; i < d; ++i) copy[p++] = tour[i];
    for (int i = b; i < c; ++i) copy[p++] = tour[i];
    for (int i = a; i < b; ++i) copy[p++] = tour[i];
    for (int i = d; i < n; ++i) copy[p++] = tour[i];
    memcpy(tour, copy, (size_t)n * sizeof(int));
    free(copy);
}

static const char *scratch_algorithm_label(const char *algorithm)
{
    if (strcmp(algorithm, "nn2opt") == 0) {
        return "SCRATCH_NN_2OPT";
    }
    if (strcmp(algorithm, "greedy2opt") == 0) {
        return "SCRATCH_GREEDY_2OPT";
    }
    if (strcmp(algorithm, "ils2opt") == 0) {
        return "SCRATCH_ILS_2OPT";
    }
    return algorithm;
}

static int scratch_run_search(
    const ScratchTsp *tsp,
    const char *algorithm,
    unsigned long long seed,
    double time_budget_sec,
    long iteration_budget,
    ScratchSearchResult *result)
{
    int n = tsp->n;
    int *tour = (int *)malloc((size_t)n * sizeof(int));
    int *current = (int *)malloc((size_t)n * sizeof(int));
    int *best_tour = (int *)malloc((size_t)n * sizeof(int));
    ScratchRng rng;
    double start_time = scratch_seconds();
    long iterations = 0;
    int best_length = 2147483647;

    if (!tour || !current || !best_tour) {
        free(tour);
        free(current);
        free(best_tour);
        return 0;
    }
    scratch_rng_seed(&rng, seed ^ 0x6a09e667f3bcc909ULL);

    if (iteration_budget <= 0) {
        iteration_budget = 1;
    }
    if (time_budget_sec <= 0.0) {
        time_budget_sec = 86400.0;
    }

    while (iterations < iteration_budget && (scratch_seconds() - start_time) < time_budget_sec) {
        if (strcmp(algorithm, "nn2opt") == 0) {
            int start = (int)((seed + (unsigned long long)iterations) % (unsigned long long)n);
            scratch_nearest_neighbor_tour(tsp, start, 0, &rng, tour);
        } else if (strcmp(algorithm, "greedy2opt") == 0) {
            int start = scratch_rng_int(&rng, n);
            scratch_nearest_neighbor_tour(tsp, start, 1, &rng, tour);
        } else {
            if (iterations == 0 || iterations % 25 == 0 || best_length == 2147483647) {
                int start = scratch_rng_int(&rng, n);
                scratch_nearest_neighbor_tour(tsp, start, 1, &rng, current);
                int current_length = scratch_two_opt_first(tsp, current, scratch_tour_length(tsp, current));
                if (current_length < best_length) {
                    best_length = current_length;
                    memcpy(best_tour, current, (size_t)n * sizeof(int));
                }
            }
            memcpy(tour, best_tour, (size_t)n * sizeof(int));
            scratch_double_bridge(tour, n, &rng);
        }

        int length = scratch_tour_length(tsp, tour);
        length = scratch_two_opt_first(tsp, tour, length);
        if (length < best_length) {
            best_length = length;
            memcpy(best_tour, tour, (size_t)n * sizeof(int));
        }
        ++iterations;
    }

    result->best_length = best_length;
    result->iterations = iterations;
    result->best_tour = best_tour;
    free(tour);
    free(current);
    return best_length < 2147483647;
}

static void scratch_free_search_result(ScratchSearchResult *result)
{
    if (!result) {
        return;
    }
    free(result->best_tour);
    result->best_tour = NULL;
    result->best_length = 0;
    result->iterations = 0;
}

static int scratch_write_tour_file(
    const char *path,
    const char *algorithm,
    int nproc,
    const char *mode,
    unsigned long long seed,
    int best_length,
    const int *tour,
    int n)
{
    FILE *fp = fopen(path, "w");
    if (!fp) {
        fprintf(stderr, "failed to open tour output %s: %s\n", path, strerror(errno));
        return 0;
    }
    fprintf(fp, "# algorithm=%s\n", scratch_algorithm_label(algorithm));
    fprintf(fp, "# nproc=%d\n", nproc);
    fprintf(fp, "# mode=%s\n", mode);
    fprintf(fp, "# seed=%llu\n", seed);
    fprintf(fp, "# best_length=%d\n", best_length);
    fprintf(fp, "# city_count=%d\n", n);
    for (int i = 0; i < n; ++i) {
        fprintf(fp, "%d%s", tour[i] + 1, (i + 1 == n) ? "\n" : " ");
    }
    fclose(fp);
    return 1;
}

static int scratch_file_has_content(const char *path)
{
    FILE *fp = fopen(path, "rb");
    long size = 0;
    if (!fp) {
        return 0;
    }
    if (fseek(fp, 0, SEEK_END) == 0) {
        size = ftell(fp);
    }
    fclose(fp);
    return size > 0;
}

static int scratch_append_result(
    const char *path,
    const char *algorithm,
    int nproc,
    const char *mode,
    unsigned long long seed,
    double time_budget_sec,
    long iteration_budget,
    int best_length,
    double elapsed_sec)
{
    int need_header = !scratch_file_has_content(path);
    FILE *fp = fopen(path, "a");
    if (!fp) {
        fprintf(stderr, "failed to open output CSV %s: %s\n", path, strerror(errno));
        return 0;
    }
    if (need_header) {
        fprintf(fp, "algorithm,nproc,mode,seed,time_budget_sec,iteration_budget,best_length,elapsed_sec\n");
    }
    fprintf(fp, "%s,%d,%s,%llu,%.6f,%ld,%d,%.6f\n",
            scratch_algorithm_label(algorithm),
            nproc,
            mode,
            seed,
            time_budget_sec,
            iteration_budget,
            best_length,
            elapsed_sec);
    fclose(fp);
    return 1;
}

static int scratch_smoke_test(void)
{
    ScratchTsp tsp;
    int valid_tour[] = {0, 1, 2, 3};
    int invalid_tour[] = {0, 1, 1, 3};
    int tour[4];
    ScratchRng rng;
    ScratchSearchResult result;

    if (!scratch_alloc_tsp(&tsp, 4)) {
        fprintf(stderr, "smoke allocation failed\n");
        return 1;
    }
    tsp.x[0] = 0.0; tsp.y[0] = 0.0;
    tsp.x[1] = 0.0; tsp.y[1] = 10.0;
    tsp.x[2] = 10.0; tsp.y[2] = 10.0;
    tsp.x[3] = 10.0; tsp.y[3] = 0.0;
    scratch_build_distances(&tsp);

    if (scratch_tour_length(&tsp, valid_tour) != 40) {
        fprintf(stderr, "smoke length failed\n");
        scratch_free_tsp(&tsp);
        return 1;
    }
    if (!scratch_tour_is_valid(valid_tour, 4) || scratch_tour_is_valid(invalid_tour, 4)) {
        fprintf(stderr, "smoke validity failed\n");
        scratch_free_tsp(&tsp);
        return 1;
    }
    scratch_rng_seed(&rng, 12345);
    scratch_nearest_neighbor_tour(&tsp, 0, 0, &rng, tour);
    if (!scratch_tour_is_valid(tour, 4)) {
        fprintf(stderr, "smoke nearest-neighbor validity failed\n");
        scratch_free_tsp(&tsp);
        return 1;
    }
    memset(&result, 0, sizeof(result));
    if (!scratch_run_search(&tsp, "ils2opt", 12345, 1.0, 5, &result) || result.best_length != 40 ||
        !scratch_tour_is_valid(result.best_tour, 4)) {
        fprintf(stderr, "smoke search failed: %d\n", result.best_length);
        scratch_free_search_result(&result);
        scratch_free_tsp(&tsp);
        return 1;
    }
    scratch_free_search_result(&result);

    scratch_free_tsp(&tsp);
    printf("SCRATCH_SMOKE_OK\n");
    return 0;
}

#endif
