## Execucoes

| ordem | condicao | repeticao | status | correto | wall_s | cpu_processo_s | trabalho_por_s | cpus_efetivas | cpu.max | delta_nr_throttled | delta_throttled_usec | memory.peak_bytes | rss_pico_processo_kib | limites_confirmados | valida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | C1 | 1 | ok | True | 29.570929 | 14.767123 | 2029019.8 | 0.508 | 50000 100000 | 301 | 15041466 | 21127168 | 16156 | True | True |
| 2 | C2 | 1 | ok | True | 9.341447 | 9.340717 | 6422988.02 | 1.021 | 100000 100000 | 0 | 0 | 21327872 | 16244 | True | True |
| 3 | C2 | 2 | ok | True | 9.233713 | 9.232427 | 6497927.47 | 1.019 | 100000 100000 | 0 | 0 | 21393408 | 16276 | True | True |
| 4 | C1 | 2 | ok | True | 30.016358 | 15.015418 | 1998910.07 | 0.506 | 50000 100000 | 304 | 15191101 | 21348352 | 16292 | True | True |
| 5 | C1 | 3 | ok | True | 30.296945 | 15.145169 | 1980397.69 | 0.507 | 50000 100000 | 307 | 15344493 | 21475328 | 16248 | True | True |
| 6 | C2 | 3 | ok | True | 10.118798 | 10.117154 | 5929558.11 | 1.021 | 100000 100000 | 0 | 0 | 21688320 | 16272 | True | True |

## Resumo por condicao

| condicao | n_validas | n_total | trabalho_por_s_mediana | trabalho_por_s_min | trabalho_por_s_max | amplitude_relativa_pct | wall_s_mediana | cpu_processo_s_mediana | cpus_efetivas_mediana | nr_throttled_mediana | throttled_s_mediana | memory_peak_mib_max | rss_pico_mib_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 3 | 3 | 1998910.1 | 1980397.7 | 2029019.8 | 2.43 | 30.016 | 15.015 | 0.507 | 304 | 15.191 | 20.5 | 15.9 |
| C2 | 3 | 3 | 6422988.0 | 5929558.1 | 6497927.5 | 8.85 | 9.341 | 9.341 | 1.021 | 0 | 0.0 | 20.7 | 15.9 |

Razao das medianas de trabalho/s (C2/C1): 3.213
