#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

#define N_COLONY 100
#define CITY 442

int xColony = 100;
int xCity = CITY;
double probab1 = 0.02;
long NOCHANGE = 200000;
long maxGen = 1000;
unsigned long baseSeed = 12345;

int colony[N_COLONY * 2][CITY], colony2[N_COLONY][CITY];
double cityXY[CITY][2];
double city_dis[CITY][CITY];
double dis_p[N_COLONY * 2];
double sumbest, sumTemp;
int temp[CITY], ibest;
long GenNum, Ni;

static const char *inputPath = "pcb442.tsp";
static const char *outputPath = "serial_result.csv";
static const char *tourOutputPath = NULL;
static int verbose = 0;

static void configure(int argc, char **argv);
static void usage(const char *program);
static long parse_positive_long(const char *text, const char *name);
static int parse_positive_int(const char *text, const char *name);
static unsigned long parse_seed(const char *text, const char *name);
static void configure_logging_from_env(void);
static void apply_runtime_flag(const char *flag);
static double wall_seconds(void);
static void init(void);
static int position(int *tmp, int C);
static void invert(int pos_start, int pos_end);
static void select1(void);
static void update_best(void);
static double compute_path_length(const int route[]);
static void evolve_one_generation(void);
static int file_has_content(const char *path);
static void append_csv(double elapsedSec);
static void write_tour_file(const char *path, const int route[], double bestLength);

int main(int argc, char **argv)
{
    double startSeconds;
    configure(argc, argv);
    startSeconds = wall_seconds();
    init();

    while (GenNum < maxGen) {
        evolve_one_generation();
    }

    {
        double elapsedSec = wall_seconds() - startSeconds;
        printf("SERIAL final best: %.0f\n", sumbest);
        printf("SERIAL elapsed time: %.6f sec\n", elapsedSec);
        append_csv(elapsedSec);
        if (tourOutputPath != NULL && tourOutputPath[0] != '\0') {
            write_tour_file(tourOutputPath, colony[ibest], sumbest);
        }
    }

    return EXIT_SUCCESS;
}

static void configure(int argc, char **argv)
{
    int argi;
    configure_logging_from_env();
    if (argc > 1) {
        inputPath = argv[1];
    }
    if (argc > 2) {
        maxGen = parse_positive_long(argv[2], "maxGen");
    }
    if (argc > 3) {
        baseSeed = parse_seed(argv[3], "base_seed");
    }
    if (argc > 4) {
        outputPath = argv[4];
    }
    argi = 5;
    if (argi < argc && argv[argi][0] != '-') {
        xColony = parse_positive_int(argv[argi], "local_colony_size");
        argi++;
    }
    if (argi < argc && argv[argi][0] != '-') {
        tourOutputPath = argv[argi];
        argi++;
    }
    for (; argi < argc; argi++) {
        apply_runtime_flag(argv[argi]);
    }
}

static void usage(const char *program)
{
    fprintf(stderr, "Usage: %s [input.tsp] [maxGen] [base_seed] [output.csv] [local_colony_size] [tour_output] [--verbose]\n", program);
}

static long parse_positive_long(const char *text, const char *name)
{
    char *end = NULL;
    long value;

    errno = 0;
    value = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value <= 0) {
        fprintf(stderr, "Invalid %s: %s\n", name, text);
        usage("tsp_serial_exp");
        exit(EXIT_FAILURE);
    }

    return value;
}

static int parse_positive_int(const char *text, const char *name)
{
    long value = parse_positive_long(text, name);
    if (value > N_COLONY) {
        fprintf(stderr, "Invalid %s: %s exceeds %d\n", name, text, N_COLONY);
        usage("tsp_serial_exp");
        exit(EXIT_FAILURE);
    }
    return (int)value;
}

static unsigned long parse_seed(const char *text, const char *name)
{
    char *end = NULL;
    unsigned long value;

    errno = 0;
    value = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        fprintf(stderr, "Invalid %s: %s\n", name, text);
        usage("tsp_serial_exp");
        exit(EXIT_FAILURE);
    }

    return value;
}

static void configure_logging_from_env(void)
{
    const char *env = getenv("TSP_VERBOSE");
    verbose = (env != NULL && strcmp(env, "0") != 0 && strcmp(env, "") != 0);
}

static void apply_runtime_flag(const char *flag)
{
    if (strcmp(flag, "--verbose") == 0) {
        verbose = 1;
    } else if (strcmp(flag, "--quiet") == 0) {
        verbose = 0;
    } else {
        fprintf(stderr, "Unknown option: %s\n", flag);
        usage("tsp_serial_exp");
        exit(EXIT_FAILURE);
    }
}

static double wall_seconds(void)
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

static void init(void)
{
    int i, j, t, sign, mod, array[CITY];
    double x, y;
    double d;
    FILE *fp;

    srand((unsigned int)baseSeed);

    fp = fopen(inputPath, "r");
    if (fp == NULL) {
        perror(inputPath);
        exit(EXIT_FAILURE);
    }

    if (fscanf(fp, "%d", &xCity) != 1) {
        fprintf(stderr, "Failed to read city count from %s\n", inputPath);
        fclose(fp);
        exit(EXIT_FAILURE);
    }

    if (xCity <= 0 || xCity > CITY) {
        fprintf(stderr, "City count %d is outside supported range 1..%d\n", xCity, CITY);
        fclose(fp);
        exit(EXIT_FAILURE);
    }

    if (xColony <= 0 || xColony > N_COLONY) {
        fprintf(stderr, "Colony count %d is outside supported range 1..%d\n", xColony, N_COLONY);
        fclose(fp);
        exit(EXIT_FAILURE);
    }

    for (i = 0; i < xCity; i++) {
        int cityId;
        if (fscanf(fp, "%d%lf%lf", &cityId, &x, &y) != 3) {
            fprintf(stderr, "Failed to read city row %d from %s\n", i + 1, inputPath);
            fclose(fp);
            exit(EXIT_FAILURE);
        }
        cityXY[i][0] = x;
        cityXY[i][1] = y;
    }
    fclose(fp);
    if (verbose) {
        printf("SERIAL read %d cities from %s\n", xCity, inputPath);
    }

    for (i = 0; i < xCity; i++) {
        for (j = 0; j < xCity; j++) {
            if (j > i) {
                d = (cityXY[i][0] - cityXY[j][0]) * (cityXY[i][0] - cityXY[j][0]) +
                    (cityXY[i][1] - cityXY[j][1]) * (cityXY[i][1] - cityXY[j][1]);
                city_dis[i][j] = (int)(sqrt(d) + 0.5);
                continue;
            }
            if (j == i) {
                city_dis[i][j] = 0;
                continue;
            }
            if (j < i) {
                city_dis[i][j] = city_dis[j][i];
            }
        }
    }
    if (verbose) {
        printf("SERIAL distance matrix initialized\n");
    }

    mod = xCity;
    for (i = 0; i < xCity; i++) {
        array[i] = i;
    }

    for (i = 0; i < xColony; i++, mod = xCity) {
        for (j = 0; j < xCity; j++) {
            sign = rand() % mod;
            colony[i][j] = array[sign];
            t = array[mod - 1];
            array[mod - 1] = array[sign];
            array[sign] = t;
            mod--;
            if (mod == 1) {
                colony[i][++j] = array[0];
            }
        }
    }
    if (verbose) {
        printf("SERIAL colony initialized: %d individuals\n", xColony);
    }

    for (i = 0; i < xColony; i++) {
        dis_p[i] = compute_path_length(colony[i]);
    }

    update_best();
    sumTemp = sumbest * 5;
    GenNum = 0;
    Ni = 0;
    if (verbose) {
        printf("SERIAL initial best: %.0f (individual %d, seed=%lu, maxGen=%ld)\n",
               sumbest, ibest, baseSeed, maxGen);
    }
}

static void evolve_one_generation(void)
{
    int i, j, k, pos_C, pos_C1;
    int k1, k2, l1, l2, pos_flag;
    double disChange;

    for (i = 0; i < xColony; i++) {
        for (j = 0; j < xCity; j++) {
            temp[j] = colony[i][j];
        }
        disChange = 0;
        pos_flag = 0;
        pos_C = rand() % xCity;

        for (;;) {
            if (((double)rand() / ((double)RAND_MAX + 1.0)) < probab1) {
                do {
                    pos_C1 = rand() % xCity;
                } while (pos_C1 == pos_C);
            } else {
                int other;
                int nextCity;
                do {
                    other = rand() % xColony;
                } while (other == i);
                k = position(colony[other], temp[pos_C]);
                nextCity = colony[other][(k + 1) % xCity];
                pos_C1 = position(temp, nextCity);
            }

            if ((pos_C + 1) % xCity == pos_C1 ||
                (pos_C - 1 + xCity) % xCity == pos_C1) {
                break;
            }

            k1 = temp[pos_C];
            k2 = temp[(pos_C + 1) % xCity];
            l1 = temp[pos_C1];
            l2 = temp[(pos_C1 + 1) % xCity];
            disChange += city_dis[k1][l1] + city_dis[k2][l2] -
                         city_dis[k1][k2] - city_dis[l1][l2];
            invert(pos_C, pos_C1);
            pos_flag++;

            if (pos_flag > xCity - 1) {
                break;
            }

            pos_C++;
            if (pos_C >= xCity) {
                pos_C = 0;
            }
        }

        dis_p[N_COLONY + i] = dis_p[i] + disChange;
        for (j = 0; j < xCity; j++) {
            colony[N_COLONY + i][j] = temp[j];
        }
    }

    select1();
    Ni++;
    GenNum++;
    update_best();
}

static void select1(void)
{
    int j, k;
    for (j = 0; j < xColony; j++) {
        if (dis_p[N_COLONY + j] < dis_p[j]) {
            dis_p[j] = dis_p[N_COLONY + j];
            for (k = 0; k < CITY; k++) {
                colony[j][k] = colony[N_COLONY + j][k];
            }
        }
    }
}

static void update_best(void)
{
    int i;

    ibest = 0;
    sumbest = dis_p[0];

    for (i = 1; i < xColony; i++) {
        if (dis_p[i] < sumbest) {
            ibest = i;
            sumbest = dis_p[i];
        }
    }
}

static double compute_path_length(const int route[])
{
    int j;
    double length = 0;

    for (j = 0; j < xCity - 1; j++) {
        length += city_dis[route[j]][route[j + 1]];
    }
    length += city_dis[route[0]][route[xCity - 1]];

    return length;
}

static void invert(int pos_start, int pos_end)
{
    int j, k, t;
    if (pos_start < pos_end) {
        j = pos_start + 1;
        k = pos_end;
        for (; j <= k; j++, k--) {
            t = temp[j];
            temp[j] = temp[k];
            temp[k] = t;
        }
    } else {
        if (xCity - 1 - pos_start <= pos_end + 1) {
            j = pos_end;
            k = pos_start + 1;
            for (; k < xCity; j--, k++) {
                t = temp[j];
                temp[j] = temp[k];
                temp[k] = t;
            }
            k = 0;
            for (; k <= j; k++, j--) {
                t = temp[j];
                temp[j] = temp[k];
                temp[k] = t;
            }
        } else {
            j = pos_end;
            k = pos_start + 1;
            for (; j >= 0; j--, k++) {
                t = temp[j];
                temp[j] = temp[k];
                temp[k] = t;
            }
            j = xCity - 1;
            for (; k <= j; k++, j--) {
                t = temp[j];
                temp[j] = temp[k];
                temp[k] = t;
            }
        }
    }
}

static int position(int *tmp, int C)
{
    int j;
    for (j = 0; j < xCity; j++) {
        if (tmp[j] == C) {
            break;
        }
    }
    return j;
}

static int file_has_content(const char *path)
{
    long size;
    FILE *fp = fopen(path, "rb");
    if (fp == NULL) {
        return 0;
    }

    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return 0;
    }
    size = ftell(fp);
    fclose(fp);

    return size > 0;
}

static void append_csv(double elapsedSec)
{
    int needHeader = !file_has_content(outputPath);
    FILE *fp = fopen(outputPath, "a");

    if (fp == NULL) {
        perror(outputPath);
        exit(EXIT_FAILURE);
    }

    if (needHeader) {
        fprintf(fp, "algorithm,nproc,maxGen,migration_interval,base_seed,global_best,elapsed_sec\n");
    }

    fprintf(fp, "SERIAL,1,%ld,0,%lu,%.0f,%.6f\n",
            maxGen, baseSeed, sumbest, elapsedSec);
    fclose(fp);
}

static void write_tour_file(const char *path, const int route[], double bestLength)
{
    int j;
    FILE *fp = fopen(path, "w");
    if (fp == NULL) {
        perror(path);
        exit(EXIT_FAILURE);
    }

    fprintf(fp, "# algorithm=SERIAL\n");
    fprintf(fp, "# nproc=1\n");
    fprintf(fp, "# seed=%lu\n", baseSeed);
    fprintf(fp, "# best_length=%.0f\n", bestLength);
    fprintf(fp, "# city_count=%d\n", xCity);
    fprintf(fp, "# local_colony_size=%d\n", xColony);
    for (j = 0; j < xCity; j++) {
        fprintf(fp, "%d%s", route[j] + 1, (j + 1 == xCity) ? "\n" : " ");
    }
    fclose(fp);
}
