/*
 * gpio_dispatcher.c  –  Envía dos canales seriales (SIG1 y SIG2) en paralelo, mediante un tercer canal que hace de CLK.
 *
 * Compilación:
 *      gcc gpio_dispatcher.c -o gpio_dispatcher -lgpiod -lm
 *
 * Uso:
 *      sudo ./gpio_dispatcher <signal 1 .bin file> <signal 2 .bin file> <periodo_ms>
 *
 * Requisitos:
 *      · Raspberry Pi 5  (header GPIO “clásico”)
 *      · Pines usados (BCM):
 *          - SIG1  → 23   (physical 16)
 *          - SIG2  → 5    (physical 29)
 *          - CLK   → 17   (physical 11)
 *      · Los dos .bin deben tener **el mismo número de muestras**
 */

#include <gpiod.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>

/* ---------- Configuración GPIO (BCM) ------------------------------ */
#define CONSUMER      "gpio_dispatcher"
const int DATA_PIN_S1 = 23;
const int DATA_PIN_S2 = 5;
const int CLOCK_PIN   = 17;
const int BITS_PER_SAMPLE = 8;

/* ---------- Globals para liberar recursos ------------------------- */
struct gpiod_chip *chip          = NULL;
struct gpiod_line *line_s1       = NULL,
                  *line_s2       = NULL,
                  *line_clk      = NULL;
unsigned char *buf1 = NULL, *buf2 = NULL;
long file_size = 0;

void cleanup(int signo)
{
    printf("\nLiberando recursos...\n");
    free(buf1); free(buf2);
    if (line_s1) gpiod_line_release(line_s1);
    if (line_s2) gpiod_line_release(line_s2);
    if (line_clk) gpiod_line_release(line_clk);
    if (chip) gpiod_chip_close(chip);
    printf("Listo.\n");
    exit(0);
}

/* ---------- Envía un byte sobre ambos canales en paralelo --------- */
void send_parallel_byte(unsigned char v1, unsigned char v2)
{
    for (int i = 0; i < BITS_PER_SAMPLE; i++) {
        gpiod_line_set_value(line_s1, (v1 >> i) & 1);
        gpiod_line_set_value(line_s2, (v2 >> i) & 1);
        usleep(10);                          /* estabilización datos   */
        gpiod_line_set_value(line_clk, 1);   /* flanco ascendente CLK  */
        usleep(50);                          /* ancho de pulso         */
        gpiod_line_set_value(line_clk, 0);
        usleep(100);                         /* tiempo entre bits      */
    }
}

/* ---------- MAIN -------------------------------------------------- */
int main(int argc, char **argv)
{
    if (argc != 4) {
        fprintf(stderr,
          "Uso: %s <sig1.bin> <sig2.bin> <periodo_ms>\n", argv[0]);
        return 1;
    }

    const char *file1 = argv[1];
    const char *file2 = argv[2];
    long period_ms = atol(argv[3]);
    if (period_ms <= 0) {
        fprintf(stderr, "Periodo inválido (debe ser >0 ms).\n");
        return 1;
    }

    signal(SIGINT, cleanup);

    /* ---- Leer ambos archivos ------------------------------------ */
    FILE *f1 = fopen(file1, "rb");
    FILE *f2 = fopen(file2, "rb");
    if (!f1 || !f2) { perror("fopen"); return 1; }

    fseek(f1, 0, SEEK_END); long sz1 = ftell(f1); rewind(f1);
    fseek(f2, 0, SEEK_END); long sz2 = ftell(f2); rewind(f2);
    if (sz1 != sz2) {
        fprintf(stderr, "Los archivos no tienen el mismo tamaño.\n");
        return 1;
    }
    file_size = sz1;

    buf1 = malloc(file_size);
    buf2 = malloc(file_size);
    if (!buf1 || !buf2) { perror("malloc"); return 1; }

    fread(buf1, 1, file_size, f1);
    fread(buf2, 1, file_size, f2);
    fclose(f1); fclose(f2);
    printf("Cargadas %ld muestras por canal.\n", file_size);

    /* ---- Inicializar GPIO --------------------------------------- */
    const char *chipname = "gpiochip4";         /* Pi 5 header */
    chip = gpiod_chip_open_by_name(chipname);
    if (!chip) { perror("gpiod_chip_open_by_name"); cleanup(0); }

    line_s1  = gpiod_chip_get_line(chip, DATA_PIN_S1);
    line_s2  = gpiod_chip_get_line(chip, DATA_PIN_S2);
    line_clk = gpiod_chip_get_line(chip, CLOCK_PIN);
    if (!line_s1 || !line_s2 || !line_clk) {
        fprintf(stderr, "Error obteniendo líneas GPIO.\n"); cleanup(0);
    }
    if (gpiod_line_request_output(line_s1, CONSUMER, 0) < 0 ||
        gpiod_line_request_output(line_s2, CONSUMER, 0) < 0 ||
        gpiod_line_request_output(line_clk, CONSUMER, 0) < 0) {
        fprintf(stderr, "Error configurando GPIOs.\n"); cleanup(0);
    }

    printf("Transmisión iniciada (periodo %ld ms). Ctrl-C para salir.\n",
            period_ms);

    /* ---- Bucle principal ---------------------------------------- */
    while (1) {
        for (long i = 0; i < file_size; i++) {
            send_parallel_byte(buf1[i], buf2[i]);
            usleep(period_ms * 1000);
        }
    }

    /* no se alcanza */
    return 0;
}
