# GenResearch-Servidor — AV2 de Sistemas Operacionais (UFS, 2026.2)

Mini serviço de RAG (recuperação + geração) em Python, construído para medir como o Linux
administra **memória, memória virtual, armazenamento, cache, filas e sincronização** sob uma
carga inspirada em IA generativa. O objetivo não é a qualidade da resposta, e sim observar e
explicar o que o sistema operacional faz por baixo.

**Disciplina:** Sistemas Operacionais (COMP0472) · **Professor:** Glauco de Figueiredo Carneiro ·
**Equipe 07**

**Pergunta norteadora:** como memória principal, memória virtual, armazenamento, caches, filas
compartilhadas e mecanismos de sincronização afetam o desempenho, a estabilidade e a correção de
uma aplicação de IA generativa ou de RAG?

## Vídeo da atividade

**URL:** `<COLAR URL AQUI>` (também em [VIDEO.md](VIDEO.md) e no relatório)

## Equipe e contribuição individual

| Integrante | Frente | Contribuição |
|---|---|---|
| Mikael Douglas Santos Farias | 1 — Núcleo do sistema | Repositório, README e instruções de reprodução, documentação da arquitetura e dos dados, demonstração do núcleo no vídeo |
| Douglas de Oliveira Deda | 2 — Fila e atendentes | _a preencher_ |
| Lucas Conceição Celestino | 3 — Cache e sincronização | _a preencher_ |
| Mateus do Rosario Costa | 4 — Memória e arquivos | Implementação do código e execução das medições C1–C6 e Parte D (_completar_) |
| Paulo Gabriel de Oliveira Cardoso | 5 — Ambiente e medições | _a preencher_ |
| Cadmo Octavio José do Nascimento Neto | 6 — Relatório e apresentação | _a preencher_ |

## Arquitetura

Um único processo Python com várias threads:

```
gen_corpus ──► ingest ──► data/<conjunto>/
                          ├─ vectors.bin   (float32, n × 128)
                          ├─ meta.sqlite   (id, documento, texto do trecho)
                          └─ manifest.json (tamanhos e tempos da ingestão)

produtores (2 threads) ──► fila limitada ──► workers (1–8 threads)
                                              │
                                              ├─ cache compartilhado LRU/FIFO (lock) ── acerto? responde
                                              ├─ recuperação top-k: vetores (read ou mmap) + SQLite
                                              ├─ geração simulada (sleep = E/S, laço Python = CPU)
                                              └─ log de eventos (lock)
```

| Componente | Arquivo | Recurso do SO envolvido |
|---|---|---|
| Geração do corpus | `genresearch/gen_corpus.py` | escrita de arquivos |
| Ingestão (fragmentação, embeddings, gravação) | `genresearch/ingest.py` | E/S de disco, page cache |
| Armazenamento | `genresearch/store.py` | `read()` × `mmap`, paginação sob demanda, file descriptors |
| Fila, produtores, workers, falhas injetáveis, métricas | `genresearch/server.py` | escalonador, futex, GIL |
| Cache compartilhado | `genresearch/cache.py` | seção crítica (mutex) |
| Log concorrente | `genresearch/logger.py` | escrita concorrente em arquivo (mutex) |
| Métricas de SO | `genresearch/common.py` | `/proc/meminfo`, `/proc/vmstat`, `getrusage` |
| Experimentos C1–C6 e Parte D | `experiments/*.py` | — |
| Ambiente, monitoramento e evidências | `scripts/*.sh`, `run_all.sh` | `vmstat`, `iostat`, `strace`, `ps -L`, `/proc/PID` |

## Dados

O corpus é **sintético** (sem dados pessoais nem documentos reais) e gerado com semente fixa, então
é sempre o mesmo. Os documentos têm palavras de 50 tópicos; cada trecho de ~500 caracteres vira um
vetor de 128 dimensões por *feature hashing* (CRC32), sem modelo de linguagem e sem GPU. Isso
preserva o que interessa ao SO (volume em disco e memória, padrão de acesso, custo de cálculo).

| Conjunto | Comando | `vectors.bin` | Trechos |
|---|---|---|---|
| small | `--size-mb 20 --docs 200` | ~21 MB | ~42 mil |
| medium | `--size-mb 200 --docs 1000` | ~206 MB | ~420 mil |
| large (opcional) | `--size-mb 2000 --docs 2000`, ingestão `--embed random` | ~2 GB | ~4,2 milhões |

A pasta `data/` não vai para o Git (`.gitignore`); ela é regerada pelos comandos abaixo.

## Como reproduzir

**Requisito: Linux** (nativo, VM, WSL2 ou contêiner). O servidor e os experimentos leem `/proc`,
então **não rodam no macOS nem no Windows fora do WSL**. No WSL2, trabalhe no disco Linux (`~/`),
nunca em `/mnt/c`, porque o acesso ao disco do Windows distorce as medições de `mmap` e cache.

### 1. Preparar o ambiente

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv sysstat strace psmisc git
git clone https://github.com/mikaeldouglas/SO_UFS_2026_2_Farias_Mikael_Costa_Mateus.git && cd SO_UFS_2026_2_Farias_Mikael_Costa_Mateus
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
scripts/wsl_check.sh           # confere caminho, RAM/swap, CPUs e ferramentas
scripts/env_info.sh normal     # Parte A: registra o ambiente em results/env_normal.txt
```

No WSL2, os limites de memória da VM são definidos no `.wslconfig` (modelo em
[`wslconfig.exemplo`](wslconfig.exemplo)): perfil normal com 16 GB e perfil restrito com 4 GB,
usado só na fase 2 do C5. Depois de trocar o arquivo, rode `wsl --shutdown` no PowerShell.

### 2. Gerar os dados e testar o núcleo

```bash
python -m genresearch.gen_corpus --size-mb 20 --docs 200 --out data/raw_small
python -m genresearch.ingest --raw data/raw_small --out data/small
python -m genresearch.server --data data/small --requests 100 --workers 2 --tag teste
head results/logs/teste.log
```

O servidor imprime um JSON com vazão, latências (média, mediana, p95), acertos de cache, RSS e
faltas de página. O log registra cada evento: `cache_hit`, `cache_miss`, `retrieval`,
`generation`, `retry_*`, `failure` e `shutdown`.

### 3. Rodar todos os experimentos

```bash
./run_all.sh     # C1–C4, C6, Parte D e C5 fase 1, com 3 repetições (40–90 min)
```

Ou um por um:

| Config | Comando | O que varia |
|---|---|---|
| C1 × C2 | `scripts/monitor.sh c1c2 python -m experiments.c1_c2_read_vs_mmap --datasets data/small data/medium --reps 3` | `read` × `mmap`, sequencial × aleatório, frio × quente, tamanho |
| C3 | `scripts/monitor.sh c3 python -m experiments.c3_concurrency --data data/small --reps 3 --workers 1 2 4 8` | workers, capacidade da fila, carga de E/S × CPU |
| C3b | `python -m experiments.c3b_gil_threads_vs_processes --reps 3 --workers 1 2 4 8` | threads × processos (GIL) |
| C4 | `scripts/monitor.sh c4 python -m experiments.c4_cache --data data/small --reps 3` | consultas repetidas × distintas, capacidade, LRU × FIFO |
| C5 fase 1 | `scripts/monitor.sh c5 python -m experiments.c5_memory_pressure --datasets data/small data/medium --max-mb 10000 --reps 3` | corpus e lote |
| C5 fase 2 | `scripts/monitor.sh c5_swap python -m experiments.c5_memory_pressure --datasets data/large --batches 64 128 256 --allow-swap --max-mb 7000 --reps 1` | lote com a VM em 4 GB (swap) |
| C6 | `python -m experiments.c6_failures --data data/small --reps 3` | arquivo ausente, índice indisponível, fila saturada, falha do serviço de geração |
| Parte D | `python -m experiments.d_sync --reps 3` | com × sem mutex: cache, log, buffer limitado, deadlock |
| Evidências | `scripts/evidence.sh data/small` | `strace`, `ps -L`, `/proc/PID/status`, `smaps_rollup` |
| Gráficos | `python -m experiments.plots` | tabelas-resumo e figuras |

A fase 2 do C5 exige o perfil restrito do `.wslconfig` e o conjunto `large`. O passo a passo
detalhado de cada etapa está em [GUIA.md](GUIA.md).

### Saídas

| Caminho | Conteúdo |
|---|---|
| `results/*.csv` | resultados brutos, uma linha por execução |
| `results/summary_*.csv` | média, mediana e p95 por configuração |
| `results/figures/*.png` | gráficos |
| `results/logs/` | logs de eventos de cada execução (gerados ao rodar; não versionados) |
| `results/monitor/` | `vmstat`, `iostat` e `/proc/meminfo` antes e depois |
| `results/evidence/` | `strace`, threads e memória do processo (saída de `scripts/evidence.sh`) |
| `results/env_*.txt` | ambiente de cada perfil (saída de `scripts/env_info.sh`) |

**Resultados das medições entregues** (17–18/10/2026, máquina descrita abaixo): os CSVs brutos e
resumos estão em `results/`, as figuras em `results/figures/`, o monitoramento em
`results/monitor/` e as evidências do sistema em `results/evidencias/` (`env_normal.txt`,
`env_restrita.txt`, `env_venv.txt`, `server_processos_threads.txt`, `strace_read_resumo.txt` e
`strace_mmap_resumo.txt`).

## Ambiente das medições

Windows com WSL2 (Ubuntu 26.04, kernel 6.18 WSL2); host Intel Xeon E5-2680 v4 (14 núcleos /
28 threads, 2,40 GHz), 32 GB de RAM e GPU RTX 3060 12 GB (não usada na carga simulada). VM com
8 vCPUs e dois perfis: normal (16 GB de RAM + 8 GB de swap) e restrito (4 GB + 4 GB, só no C5
fase 2). Python 3.14, NumPy, pandas, psutil e matplotlib. Detalhes completos em
`results/evidencias/env_normal.txt` e `results/evidencias/env_restrita.txt`.

## Principais resultados

- **C1 × C2:** `mmap` foi 22× mais rápido na varredura sequencial quente de 2 GB (sem a cópia do
  `read()`) e 2,4× no acesso aleatório frio, mas o readahead trouxe ~200× mais dados que o usado.
- **C3:** com carga de espera, 8 workers deram 7,7× mais vazão; com CPU em Python puro, a vazão
  caiu 9% por causa do GIL, enquanto 8 processos chegaram a 5,4×. Fila de 128 posições não
  aumentou a vazão e elevou o p95 de 395 ms para 4,4 s.
- **C4:** cache de 100 posições com 20 consultas repetidas teve 94% de acerto e reduziu o tempo de
  6,68 s para 0,43 s; com consultas distintas, o acerto é zero.
- **C5:** o mesmo lote levou ~4 s com 16 GB e 72 s com 4 GB, com swap cheio e sinais de thrashing.
- **C6:** retentativas com backoff zeraram as falhas de índice; com a fila saturada, `reject`
  descarta trabalho e `block` preserva o trabalho à custa de espera.
- **Parte D:** sem exclusão mútua, 63% das atualizações de contador, 96,9% das linhas de log e
  37,7% dos itens do buffer foram perdidos ou corrompidos; com mutex, zero erros. O deadlock foi
  detectado por timeout e resolvido com ordem global de aquisição.

A análise completa está no relatório.

## Limitações

Vetores e geração são simulados; WSL2 é virtualizado e tem cache duplo (o Windows também guarda o
disco virtual), então leituras frias são otimistas; uma única máquina, sem GPU na carga, sem
múltiplas GPUs nem ambiente distribuído; a fase de 4 GB do C5 teve uma repetição.

## Uso de IA generativa e créditos

O código foi escrito pela equipe com apoio de IA generativa (Claude). Cada sugestão foi conferida
executando os experimentos e comparando com a documentação do Linux e do Python. A declaração
detalhada está no relatório.

Referências: SILBERSCHATZ, GALVIN e GAGNE, *Operating System Concepts*; man pages `mmap(2)`,
`read(2)`, `posix_fadvise(2)` e `proc(5)`; documentação do Python para `threading`, `queue` e
`multiprocessing`; documentação da Microsoft sobre o `.wslconfig`.
