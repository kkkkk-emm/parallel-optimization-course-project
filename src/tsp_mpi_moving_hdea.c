#include <errno.h>
#include <math.h>
#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define N_COLONY 100
#define CITY 442
#define LOCAL_TAG 101

int xColony = 100;
int xCity = CITY;
double probab1 = 0.02;
long NOCHANGE = 200000;
long maxGen = 1000;
long localMigrationInterval = 100;
long localToGlobalRatio = 5;
int numGroups = 2;
unsigned long baseSeed = 12345;
unsigned long rankSeed = 12345;

int colony[N_COLONY * 2][CITY], colony2[N_COLONY][CITY];
double cityXY[CITY][2];
double city_dis[CITY][CITY];
double dis_p[N_COLONY * 2];
double sumbest, sumTemp;
double worstDistance;
int temp[CITY], ibest, iworst;
long GenNum, Ni;

static const char *inputPath = "data/pcb442.tsp";
static const char *outputPath = "results/moving_hdea_result.csv";
static const char *tourOutputPath = NULL;
static int mpiRank = 0;
static int mpiSize = 1;
static int verbose = 0;
static int logMigration = 0;
static int groupId = 0;
static int localId = 0;
static int subpopsPerGroup = 0;
static long localMigrationCount = 0;
static int movingPosition = 0;
static int *groupMembers = NULL;

static void configure(int argc, char **argv);
static long parse_positive_long(const char *text, const char *name);
static int parse_positive_int(const char *text, const char *name);
static unsigned long parse_seed(const char *text, const char *name);
static void usage(const char *program);
static int validate_hdea_config(void);
static void configure_logging_from_env(void);
static void apply_runtime_flag(const char *flag);
static void fail_all(const char *message);
static void fail_all_errno(const char *path);
static void init(void);
static int position(int *tmp, int C);
static void invert(int pos_start, int pos_end);
static void select1(void);
static void update_best_worst(void);
static double compute_path_length(const int route[]);
static void evolve_one_generation(void);
static void migrate_individual(const char *label, int sendTo, int recvFrom, int tag);
static void migrate_local_ring(void);
static void init_group_members(void);
static int group_member(int group, int pos);
static void set_group_member(int group, int pos, int rank);
static void find_logical_position(int rank, int *logicalGroup, int *logicalPos);
static void print_group_members(const char *prefix);
static void print_local_migration_plan(void);
static void move_colony_ring(void);
static int file_has_content(const char *path);
static void append_csv(double globalBest, double elapsedSec);
static void write_tour_file(const char *path, const int route[], double bestLength, int bestRank);

int main(int argc, char **argv)
{
    double startTime, localElapsed, elapsedSec = 0.0;
    double *allBest = NULL;
    int *allTours = NULL;
    double globalBest = 0.0;
    int i, bestRank = 0;

    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &mpiRank);
    MPI_Comm_size(MPI_COMM_WORLD, &mpiSize);

    configure(argc, argv);
    if (!validate_hdea_config()) {
        MPI_Finalize();
        return EXIT_FAILURE;
    }

    subpopsPerGroup = mpiSize / numGroups;
    groupId = mpiRank / subpopsPerGroup;
    localId = mpiRank % subpopsPerGroup;
    rankSeed = baseSeed + (unsigned long)mpiRank * 10007UL;
    init_group_members();

    if (mpiRank == 0) {
        printf("MPI size: %d\n", mpiSize);
        printf("num_groups=%d subpops_per_group=%d maxGen=%ld local_migration_interval=%ld local_to_global_ratio=%ld base_seed=%lu output=%s\n",
               numGroups, subpopsPerGroup, maxGen, localMigrationInterval,
               localToGlobalRatio, baseSeed, outputPath);
        printf("input=%s\n", inputPath);
        if (verbose || logMigration) {
            print_group_members("initial group_members");
        }
        fflush(stdout);
    }

    MPI_Barrier(MPI_COMM_WORLD);
    startTime = MPI_Wtime();

    init();

    for (GenNum = 0; GenNum < maxGen;) {
        evolve_one_generation();
        if (localMigrationInterval > 0 && GenNum % localMigrationInterval == 0) {
            migrate_local_ring();
            localMigrationCount++;
            if (localMigrationCount % localToGlobalRatio == 0) {
                move_colony_ring();
            }
        }
    }

    localElapsed = MPI_Wtime() - startTime;
    if (verbose) {
        printf("[rank %d] final local best: %.0f\n", mpiRank, sumbest);
        fflush(stdout);
    }
    if (mpiRank == 0) {
        allBest = (double *)malloc(sizeof(double) * (size_t)mpiSize);
        allTours = (int *)malloc(sizeof(int) * (size_t)mpiSize * (size_t)xCity);
        if (allBest == NULL || allTours == NULL) {
            fail_all("Failed to allocate gather buffer");
        }
    }

    MPI_Gather(&sumbest, 1, MPI_DOUBLE, allBest, 1, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    MPI_Gather(&colony[ibest][0], xCity, MPI_INT, allTours, xCity, MPI_INT, 0, MPI_COMM_WORLD);
    MPI_Reduce(&localElapsed, &elapsedSec, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);

    if (mpiRank == 0) {
        globalBest = allBest[0];
        for (i = 1; i < mpiSize; i++) {
            if (allBest[i] < globalBest) {
                globalBest = allBest[i];
                bestRank = i;
            }
        }

        printf("[rank 0] final global best: %.0f\n", globalBest);
        printf("[rank 0] elapsed time: %.6f sec\n", elapsedSec);
        fflush(stdout);
        append_csv(globalBest, elapsedSec);
        if (tourOutputPath != NULL && tourOutputPath[0] != '\0') {
            write_tour_file(tourOutputPath, allTours + ((size_t)bestRank * (size_t)xCity), globalBest, bestRank);
        }
        free(allBest);
        free(allTours);
    }

    free(groupMembers);
    MPI_Finalize();
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
        localMigrationInterval = parse_positive_long(argv[3], "local_migration_interval");
    }
    if (argc > 4) {
        localToGlobalRatio = parse_positive_long(argv[4], "local_to_global_ratio");
    }
    if (argc > 5) {
        numGroups = parse_positive_int(argv[5], "num_groups");
    }
    if (argc > 6) {
        baseSeed = parse_seed(argv[6], "base_seed");
    }
    if (argc > 7) {
        outputPath = argv[7];
    }
    argi = 8;
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

static long parse_positive_long(const char *text, const char *name)
{
    char *end = NULL;
    long value;

    errno = 0;
    value = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value <= 0) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid %s: %s\n", name, text);
            usage("tsp_mpi_hdea");
        }
        fail_all("Invalid numeric argument");
    }

    return value;
}

static int parse_positive_int(const char *text, const char *name)
{
    long value = parse_positive_long(text, name);
    if (value > 2147483647L) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid %s: %s is too large\n", name, text);
        }
        fail_all("Invalid integer argument");
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
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid %s: %s\n", name, text);
            usage("tsp_mpi_hdea");
        }
        fail_all("Invalid seed argument");
    }

    return value;
}

static void usage(const char *program)
{
    fprintf(stderr,
            "Usage: %s [input.tsp] [maxGen] [local_migration_interval] [local_to_global_ratio] [num_groups] [base_seed] [output.csv] [local_colony_size] [tour_output] [--verbose] [--log-migration]\n",
            program);
}

static void configure_logging_from_env(void)
{
    const char *verboseEnv = getenv("TSP_VERBOSE");
    const char *migrationEnv = getenv("TSP_LOG_MIGRATION");
    verbose = (verboseEnv != NULL && strcmp(verboseEnv, "0") != 0 && strcmp(verboseEnv, "") != 0);
    logMigration = (migrationEnv != NULL && strcmp(migrationEnv, "0") != 0 && strcmp(migrationEnv, "") != 0);
}

static void apply_runtime_flag(const char *flag)
{
    if (strcmp(flag, "--verbose") == 0) {
        verbose = 1;
    } else if (strcmp(flag, "--log-migration") == 0) {
        logMigration = 1;
    } else if (strcmp(flag, "--quiet") == 0) {
        verbose = 0;
        logMigration = 0;
    } else {
        if (mpiRank == 0) {
            fprintf(stderr, "Unknown option: %s\n", flag);
            usage("tsp_mpi_moving_hdea");
        }
        fail_all("Unknown command line option");
    }
}

static int validate_hdea_config(void)
{
    int valid = 1;

    if (mpiSize < 4) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid MOVING_HDEA configuration: at least 4 MPI ranks are required\n");
        }
        valid = 0;
    }

    if (numGroups < 2) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid MOVING_HDEA configuration: num_groups must be at least 2\n");
        }
        valid = 0;
    }

    if (numGroups > mpiSize) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid MOVING_HDEA configuration: num_groups must not exceed nproc\n");
        }
        valid = 0;
    }

    if (numGroups > 0 && mpiSize % numGroups != 0) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid MOVING_HDEA configuration: nproc must be divisible by num_groups\n");
        }
        valid = 0;
    }

    if (valid) {
        int computedSubpopsPerGroup = mpiSize / numGroups;
        if (computedSubpopsPerGroup < 2) {
            if (mpiRank == 0) {
                fprintf(stderr, "Invalid MOVING_HDEA configuration: each group must contain at least 2 ranks\n");
            }
            valid = 0;
        }
    }

    return valid;
}

static void fail_all(const char *message)
{
    fprintf(stderr, "[rank %d] %s\n", mpiRank, message);
    fflush(stderr);
    MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
}

static void fail_all_errno(const char *path)
{
    fprintf(stderr, "[rank %d] %s: %s\n", mpiRank, path, strerror(errno));
    fflush(stderr);
    MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
}

static void init(void)
{
    int i, j, t, sign, mod, array[CITY];
    double x, y;
    double d;
    FILE *fp;

    srand((unsigned int)rankSeed);

    fp = fopen(inputPath, "r");
    if (fp == NULL) {
        fail_all_errno(inputPath);
    }

    if (fscanf(fp, "%d", &xCity) != 1) {
        fclose(fp);
        fail_all("Failed to read city count");
    }

    if (xCity <= 0 || xCity > CITY) {
        fclose(fp);
        fail_all("City count is outside supported range");
    }

    if (xColony <= 0 || xColony > N_COLONY) {
        fclose(fp);
        fail_all("Colony count is outside supported range");
    }

    for (i = 0; i < xCity; i++) {
        int cityId;
        if (fscanf(fp, "%d%lf%lf", &cityId, &x, &y) != 3) {
            fclose(fp);
            fail_all("Failed to read a city row");
        }
        cityXY[i][0] = x;
        cityXY[i][1] = y;
    }
    fclose(fp);

    if (verbose) {
        int logicalGroup, logicalPos;
        find_logical_position(mpiRank, &logicalGroup, &logicalPos);
        printf("[rank %d] initial logical_group=%d logical_pos=%d physical_group=%d physical_local_id=%d read %d cities from %s\n",
               mpiRank, logicalGroup, logicalPos, groupId, localId, xCity, inputPath);
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
        printf("[rank %d] distance matrix initialized\n", mpiRank);
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
        printf("[rank %d] colony initialized: %d individuals\n", mpiRank, xColony);
    }

    for (i = 0; i < xColony; i++) {
        dis_p[i] = compute_path_length(colony[i]);
    }

    update_best_worst();
    sumTemp = sumbest * 5;
    GenNum = 0;
    Ni = 0;
    if (verbose) {
        int logicalGroup, logicalPos;
        find_logical_position(mpiRank, &logicalGroup, &logicalPos);
        printf("[rank %d] initial logical_group=%d logical_pos=%d initial best: %.0f (individual %d, seed=%lu)\n",
               mpiRank, logicalGroup, logicalPos, sumbest, ibest, rankSeed);
        fflush(stdout);
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
    update_best_worst();
}

static void migrate_individual(const char *label, int sendTo, int recvFrom, int tag)
{
    int sendPath[CITY];
    int recvPath[CITY];
    int j;
    double sentDistance = sumbest;
    double receivedDistance;
    double replacedDistance = dis_p[iworst];

    for (j = 0; j < xCity; j++) {
        sendPath[j] = colony[ibest][j];
    }

    MPI_Sendrecv(sendPath, xCity, MPI_INT, sendTo, tag,
                 recvPath, xCity, MPI_INT, recvFrom, tag,
                 MPI_COMM_WORLD, MPI_STATUS_IGNORE);

    for (j = 0; j < xCity; j++) {
        colony[iworst][j] = recvPath[j];
    }
    receivedDistance = compute_path_length(colony[iworst]);
    dis_p[iworst] = receivedDistance;
    update_best_worst();

    if (logMigration) {
        int logicalGroup, logicalPos;
        find_logical_position(mpiRank, &logicalGroup, &logicalPos);
        printf("[rank %d] %s migration generation %ld: logical_group=%d logical_pos=%d sent best %.0f to %d, received %.0f from %d, replaced %.0f\n",
               mpiRank, label, GenNum, logicalGroup, logicalPos, sentDistance,
               sendTo, receivedDistance, recvFrom, replacedDistance);
        fflush(stdout);
    }
}

static void migrate_local_ring(void)
{
    int logicalGroup, logicalPos;
    int sendPos, recvPos;
    int localSendTo, localRecvFrom;

    if (logMigration) {
        print_local_migration_plan();
    }
    find_logical_position(mpiRank, &logicalGroup, &logicalPos);
    sendPos = (logicalPos + 1) % subpopsPerGroup;
    recvPos = (logicalPos - 1 + subpopsPerGroup) % subpopsPerGroup;
    localSendTo = group_member(logicalGroup, sendPos);
    localRecvFrom = group_member(logicalGroup, recvPos);
    migrate_individual("local", localSendTo, localRecvFrom, LOCAL_TAG);
}

static void init_group_members(void)
{
    int group, pos;

    groupMembers = (int *)malloc(sizeof(int) * (size_t)numGroups * (size_t)subpopsPerGroup);
    if (groupMembers == NULL) {
        fail_all("Failed to allocate group_members");
    }

    for (group = 0; group < numGroups; group++) {
        for (pos = 0; pos < subpopsPerGroup; pos++) {
            set_group_member(group, pos, group * subpopsPerGroup + pos);
        }
    }
}

static int group_member(int group, int pos)
{
    return groupMembers[group * subpopsPerGroup + pos];
}

static void set_group_member(int group, int pos, int rank)
{
    groupMembers[group * subpopsPerGroup + pos] = rank;
}

static void find_logical_position(int rank, int *logicalGroup, int *logicalPos)
{
    int group, pos;

    for (group = 0; group < numGroups; group++) {
        for (pos = 0; pos < subpopsPerGroup; pos++) {
            if (group_member(group, pos) == rank) {
                *logicalGroup = group;
                *logicalPos = pos;
                return;
            }
        }
    }

    fail_all("Current rank is missing from group_members");
}

static void print_group_members(const char *prefix)
{
    int group, pos;

    if (mpiRank != 0) {
        return;
    }

    printf("[rank 0] %s:", prefix);
    for (group = 0; group < numGroups; group++) {
        printf(" group %d=[", group);
        for (pos = 0; pos < subpopsPerGroup; pos++) {
            printf("%d", group_member(group, pos));
            if (pos + 1 < subpopsPerGroup) {
                printf(",");
            }
        }
        printf("]");
    }
    printf("\n");
    fflush(stdout);
}

static void print_local_migration_plan(void)
{
    int group, pos;

    if (mpiRank != 0) {
        return;
    }

    printf("[rank 0] local migration plan generation %ld:", GenNum);
    for (group = 0; group < numGroups; group++) {
        printf(" group %d=[", group);
        for (pos = 0; pos < subpopsPerGroup; pos++) {
            int fromRank = group_member(group, pos);
            int toRank = group_member(group, (pos + 1) % subpopsPerGroup);
            printf("%d->%d", fromRank, toRank);
            if (pos + 1 < subpopsPerGroup) {
                printf(",");
            }
        }
        printf("]");
    }
    printf("\n");
    fflush(stdout);
}

static void move_colony_ring(void)
{
    int group;
    int tmp;

    if (mpiRank == 0 && logMigration) {
        printf("[rank 0] global moving colony generation %ld: moving_position=%d\n",
               GenNum, movingPosition);
        print_group_members("before moving colony");
    }

    /*
     * All ranks call this function after the same deterministic number of
     * local migrations and apply the same ring rotation. Therefore every rank
     * keeps an identical group_members map without broadcasting it.
     */
    tmp = group_member(numGroups - 1, movingPosition);
    for (group = numGroups - 1; group > 0; group--) {
        set_group_member(group, movingPosition, group_member(group - 1, movingPosition));
    }
    set_group_member(0, movingPosition, tmp);

    if (mpiRank == 0 && logMigration) {
        print_group_members("after moving colony");
    }

    movingPosition = (movingPosition + 1) % subpopsPerGroup;
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

static void update_best_worst(void)
{
    int i;

    ibest = 0;
    iworst = 0;
    sumbest = dis_p[0];
    worstDistance = dis_p[0];

    for (i = 1; i < xColony; i++) {
        if (dis_p[i] < sumbest) {
            ibest = i;
            sumbest = dis_p[i];
        }
        if (dis_p[i] > worstDistance) {
            iworst = i;
            worstDistance = dis_p[i];
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

static void append_csv(double globalBest, double elapsedSec)
{
    int needHeader = !file_has_content(outputPath);
    FILE *fp = fopen(outputPath, "a");

    if (fp == NULL) {
        fail_all_errno(outputPath);
    }

    if (needHeader) {
        fprintf(fp, "algorithm,nproc,maxGen,migration_interval,local_to_global_ratio,num_groups,base_seed,global_best,elapsed_sec\n");
    }

    fprintf(fp, "MOVING_HDEA,%d,%ld,%ld,%ld,%d,%lu,%.0f,%.6f\n",
            mpiSize, maxGen, localMigrationInterval, localToGlobalRatio,
            numGroups, baseSeed, globalBest, elapsedSec);
    fclose(fp);
}

static void write_tour_file(const char *path, const int route[], double bestLength, int bestRank)
{
    int j;
    FILE *fp = fopen(path, "w");
    if (fp == NULL) {
        fail_all_errno(path);
    }

    fprintf(fp, "# algorithm=MOVING_HDEA\n");
    fprintf(fp, "# nproc=%d\n", mpiSize);
    fprintf(fp, "# seed=%lu\n", baseSeed);
    fprintf(fp, "# best_rank=%d\n", bestRank);
    fprintf(fp, "# best_length=%.0f\n", bestLength);
    fprintf(fp, "# city_count=%d\n", xCity);
    fprintf(fp, "# local_colony_size=%d\n", xColony);
    fprintf(fp, "# num_groups=%d\n", numGroups);
    for (j = 0; j < xCity; j++) {
        fprintf(fp, "%d%s", route[j] + 1, (j + 1 == xCity) ? "\n" : " ");
    }
    fclose(fp);
}
