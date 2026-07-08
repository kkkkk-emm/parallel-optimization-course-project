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
#define GLOBAL_TAG 202

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
clock_t timeStart, timeNow, timeTemp;
long GenNum, Ni;

static const char *inputPath = "pcb442.tsp";
static const char *outputPath = "hdea_result.csv";
static int mpiRank = 0;
static int mpiSize = 1;
static int groupId = 0;
static int localId = 0;
static int subpopsPerGroup = 0;
static long localMigrationCount = 0;

static void configure(int argc, char **argv);
static long parse_positive_long(const char *text, const char *name);
static int parse_positive_int(const char *text, const char *name);
static unsigned long parse_seed(const char *text, const char *name);
static void usage(const char *program);
static int validate_hdea_config(void);
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
static void migrate_global_ring(void);
static int file_has_content(const char *path);
static void append_csv(double globalBest, double elapsedSec);

int main(int argc, char **argv)
{
    double startTime, localElapsed, elapsedSec = 0.0;
    double *allBest = NULL;
    double globalBest = 0.0;
    int i;

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

    if (mpiRank == 0) {
        printf("MPI size: %d\n", mpiSize);
        printf("num_groups=%d subpops_per_group=%d maxGen=%ld local_migration_interval=%ld local_to_global_ratio=%ld base_seed=%lu output=%s\n",
               numGroups, subpopsPerGroup, maxGen, localMigrationInterval,
               localToGlobalRatio, baseSeed, outputPath);
        printf("input=%s\n", inputPath);
        fflush(stdout);
    }

    MPI_Barrier(MPI_COMM_WORLD);
    startTime = MPI_Wtime();
    timeStart = timeNow = timeTemp = clock();

    init();

    for (GenNum = 0; GenNum < maxGen;) {
        evolve_one_generation();
        if (localMigrationInterval > 0 && GenNum % localMigrationInterval == 0) {
            migrate_local_ring();
            localMigrationCount++;
            if (localMigrationCount % localToGlobalRatio == 0) {
                migrate_global_ring();
            }
        }
    }

    printf("[rank %d] final local best: %.0f\n", mpiRank, sumbest);
    fflush(stdout);

    localElapsed = MPI_Wtime() - startTime;
    if (mpiRank == 0) {
        allBest = (double *)malloc(sizeof(double) * (size_t)mpiSize);
        if (allBest == NULL) {
            fail_all("Failed to allocate gather buffer");
        }
    }

    MPI_Gather(&sumbest, 1, MPI_DOUBLE, allBest, 1, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    MPI_Reduce(&localElapsed, &elapsedSec, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);

    if (mpiRank == 0) {
        globalBest = allBest[0];
        for (i = 1; i < mpiSize; i++) {
            if (allBest[i] < globalBest) {
                globalBest = allBest[i];
            }
        }

        printf("[rank 0] final global best: %.0f\n", globalBest);
        printf("[rank 0] elapsed time: %.6f sec\n", elapsedSec);
        fflush(stdout);
        append_csv(globalBest, elapsedSec);
        free(allBest);
    }

    MPI_Finalize();
    return EXIT_SUCCESS;
}

static void configure(int argc, char **argv)
{
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
    if (argc > 8) {
        if (mpiRank == 0) {
            usage(argv[0]);
        }
        fail_all("Too many command line arguments");
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
            "Usage: %s [input.tsp] [maxGen] [local_migration_interval] [local_to_global_ratio] [num_groups] [base_seed] [output.csv]\n",
            program);
}

static int validate_hdea_config(void)
{
    int valid = 1;

    if (mpiSize < 4) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid HDEA configuration: at least 4 MPI ranks are required\n");
        }
        valid = 0;
    }

    if (numGroups < 2) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid HDEA configuration: num_groups must be at least 2\n");
        }
        valid = 0;
    }

    if (numGroups > mpiSize) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid HDEA configuration: num_groups must not exceed nproc\n");
        }
        valid = 0;
    }

    if (numGroups > 0 && mpiSize % numGroups != 0) {
        if (mpiRank == 0) {
            fprintf(stderr, "Invalid HDEA configuration: nproc must be divisible by num_groups\n");
        }
        valid = 0;
    }

    if (valid) {
        int computedSubpopsPerGroup = mpiSize / numGroups;
        if (computedSubpopsPerGroup < 2) {
            if (mpiRank == 0) {
                fprintf(stderr, "Invalid HDEA configuration: each group must contain at least 2 ranks\n");
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

    printf("[rank %d] group_id=%d local_id=%d read %d cities from %s\n",
           mpiRank, groupId, localId, xCity, inputPath);

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
    printf("[rank %d] distance matrix initialized\n", mpiRank);

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
    printf("[rank %d] colony initialized: %d individuals\n", mpiRank, xColony);

    for (i = 0; i < xColony; i++) {
        dis_p[i] = compute_path_length(colony[i]);
    }

    update_best_worst();
    sumTemp = sumbest * 5;
    GenNum = 0;
    Ni = 0;
    printf("[rank %d] group_id=%d local_id=%d initial best: %.0f (individual %d, seed=%lu)\n",
           mpiRank, groupId, localId, sumbest, ibest, rankSeed);
    fflush(stdout);
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
            if ((rand() / 32768.0) < probab1) {
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

    printf("[rank %d] %s migration generation %ld: group_id=%d local_id=%d sent best %.0f to %d, received %.0f from %d, replaced %.0f\n",
           mpiRank, label, GenNum, groupId, localId, sentDistance,
           sendTo, receivedDistance, recvFrom, replacedDistance);
    fflush(stdout);
}

static void migrate_local_ring(void)
{
    int localSendTo = groupId * subpopsPerGroup + (localId + 1) % subpopsPerGroup;
    int localRecvFrom = groupId * subpopsPerGroup + (localId - 1 + subpopsPerGroup) % subpopsPerGroup;
    migrate_individual("local", localSendTo, localRecvFrom, LOCAL_TAG);
}

static void migrate_global_ring(void)
{
    int globalSendGroup = (groupId + 1) % numGroups;
    int globalRecvGroup = (groupId - 1 + numGroups) % numGroups;
    int globalSendTo = globalSendGroup * subpopsPerGroup + localId;
    int globalRecvFrom = globalRecvGroup * subpopsPerGroup + localId;
    migrate_individual("global", globalSendTo, globalRecvFrom, GLOBAL_TAG);
}

static void select1(void)
{
    int j, k;
    for (j = 0; j < N_COLONY; j++) {
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

    fprintf(fp, "HDEA,%d,%ld,%ld,%ld,%d,%lu,%.0f,%.6f\n",
            mpiSize, maxGen, localMigrationInterval, localToGlobalRatio,
            numGroups, baseSeed, globalBest, elapsedSec);
    fclose(fp);
}
