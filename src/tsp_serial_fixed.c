#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define N_COLONY 100
#define CITY 442

int xColony = 100;
int xCity = CITY;
double probab1 = 0.02;
long NOCHANGE = 200000;
long maxGen = 100;

int colony[N_COLONY * 2][CITY], colony2[N_COLONY][CITY];
double cityXY[CITY][2];
double city_dis[CITY][CITY];
double dis_p[N_COLONY * 2];
double sumbest, sumTemp;
int temp[CITY], ibest;
clock_t timeStart, timeNow, timeTemp;
long GenNum, Ni;

static const char *inputPath = "pcb442.tsp";
static const char *outputPath = "serial_result.txt";

void init(void);
int position(int *tmp, int C);
void invert(int pos_start, int pos_end);
void printBest(long GenNum);
void select1(void);
double path(int tmp[], int k1, int k2);

static void usage(const char *program)
{
    fprintf(stderr, "Usage: %s [input.tsp] [maxGen] [output.txt]\n", program);
}

static void configure(int argc, char **argv)
{
    if (argc > 1) {
        inputPath = argv[1];
    }

    if (argc > 2) {
        char *end = NULL;
        errno = 0;
        long parsed = strtol(argv[2], &end, 10);
        if (errno != 0 || end == argv[2] || *end != '\0' || parsed <= 0) {
            usage(argv[0]);
            fprintf(stderr, "Invalid maxGen: %s\n", argv[2]);
            exit(EXIT_FAILURE);
        }
        maxGen = parsed;
    }

    if (argc > 3) {
        outputPath = argv[3];
    }

    if (argc > 4) {
        usage(argv[0]);
        exit(EXIT_FAILURE);
    }
}

int main(int argc, char **argv)
{
    register int C1, j, k, pos_C, pos_C1;
    int k1, k2, l1, l2, pos_flag;
    register double disChange;
    static int i = 0;

    configure(argc, argv);
    timeStart = timeNow = timeTemp = clock();
    init();

    for (;;) {
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
                C1 = colony[i][pos_C1];
            } else {
                do {
                    j = rand() % xColony;
                } while (j == i);
                k = position(colony[j], temp[pos_C]);
                C1 = colony[j][(k + 1) % xCity];
                pos_C1 = position(temp, C1);
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
        disChange = 0;

        for (j = 0; j < xCity; j++) {
            colony[N_COLONY + i][j] = temp[j];
        }

        i++;
        if (i >= xColony) {
            select1();
            Ni++;
            GenNum++;
            i = 0;

            sumbest = dis_p[0];
            for (j = 0; j < N_COLONY; j++) {
                if (sumbest > dis_p[j]) {
                    sumbest = dis_p[j];
                }
            }

            printf("%ld:%f\n", GenNum, sumbest);

            if (GenNum % 2000 == 0 && GenNum < maxGen) {
                printBest(GenNum);
            }

            if (GenNum >= maxGen) {
                timeNow = clock();
                printf("Final solution: %f\n", sumbest);
                printBest(GenNum);
                return EXIT_SUCCESS;
            }
        }
    }
}

void select1(void)
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

void init(void)
{
    int i, j, t, sign, mod, array[CITY];
    double x, y;
    double d;
    FILE *fp;

    srand((unsigned)time(NULL));

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
    printf("read %d cities from %s\n", xCity, inputPath);

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
    printf("distance matrix initialized\n");

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
    printf("colony initialized: %d individuals\n", xColony);

    for (i = 0; i < xColony; i++) {
        dis_p[i] = 0;
        for (j = 0; j < xCity - 1; j++) {
            dis_p[i] = dis_p[i] + city_dis[colony[i][j]][colony[i][j + 1]];
        }
        dis_p[i] = dis_p[i] + city_dis[colony[i][0]][colony[i][xCity - 1]];
    }

    ibest = 0;
    sumbest = dis_p[0];
    for (i = 1; i < xColony; i++) {
        if (dis_p[i] < sumbest) {
            ibest = i;
            sumbest = dis_p[i];
        }
    }
    sumTemp = sumbest * 5;
    GenNum = 0;
    Ni = 0;
    printf("initial best: %f (individual %d)\n", sumbest, ibest);
    printf("init success!!! maxGen=%ld output=%s\n", maxGen, outputPath);
}

void invert(int pos_start, int pos_end)
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

int position(int *tmp, int C)
{
    int j;
    for (j = 0; j < xCity; j++) {
        if (tmp[j] == C) {
            break;
        }
    }
    return j;
}

void printBest(long GenNum)
{
    FILE *fpme;
    timeNow = clock();

    fpme = fopen(outputPath, "a");
    if (fpme == NULL) {
        perror(outputPath);
        exit(EXIT_FAILURE);
    }

    fprintf(fpme, "%ld\t%4.2f\t%d\n",
            GenNum,
            (double)(timeNow - timeStart) / CLOCKS_PER_SEC,
            (int)sumbest);
    fclose(fpme);
}

double path(int tmp[], int k1, int k2)
{
    int j, t1, t2;
    double temp_dis = 0;

    if (k2 > k1) {
        for (j = k1; j < k2; j++) {
            temp_dis += city_dis[tmp[j]][tmp[j + 1]];
        }
    } else {
        for (j = k1; j < k2 + xCity; j++) {
            t1 = j % xCity;
            t2 = (j + 1) % xCity;
            temp_dis += city_dis[tmp[t1]][tmp[t2]];
        }
    }

    return temp_dis;
}
