# GUIA — Como executar a AV2 do zero (GenResearch-Servidor) — versão WSL2

## 0-A. Preparar o WSL2 (faça ANTES de tudo; ~30 min)
O WSL2 é uma VM leve do Windows. Isso muda **como interpretar** memória, cache e disco, então configurem e documentem. A **máquina principal de testes** (referência para os números finais): Windows + WSL2, **32 GB de RAM**, **Intel Xeon E5-2680 v4 (14 núcleos/28 threads, 2,40 GHz)**, **GPU NVIDIA RTX 3060 12 GB**. Os demais integrantes desenvolvem e testam em escala pequena (`small`); **não misturem números de máquinas diferentes** nos mesmos gráficos.

**1. Distribuição e versão.** Ubuntu 22.04/24.04 no WSL2. No PowerShell: `wsl -l -v` (VERSION deve ser 2), `wsl --version` e `wsl --update`.

**2. Trabalhe SEMPRE no filesystem Linux (`~/`), nunca em `/mnt/c/...`.** O `/mnt/c` é o disco do Windows via protocolo 9P: lento e distorce `mmap`, cache e E/S (os resultados de C1/C2 ficariam inválidos). Clonem o repositório em `~/` e confirmem `ext4` com `df -hT .`:
```bash
cd ~ && git clone <URL_DO_REPO> && cd <repo>
scripts/wsl_check.sh      # confere: WSL, caminho, RAM/swap/CPUs, GPU, ferramentas, systemd
```
Reservem **~20 GB livres** no SSD do Windows (o disco virtual do WSL cresce sob demanda): corpus grande + índice + SQLite.

**3. Limites de recursos com `.wslconfig` (no Windows).** Arquivo `C:\Users\<usuario>\.wslconfig` (modelo: `wslconfig.exemplo`). **Perfil NORMAL** (C1–C4, C6, Parte D e C5 fase 1):
```ini
[wsl2]
memory=16GB
processors=8
swap=8GB

[experimental]
autoMemoryReclaim=disabled
```
Aplique com `wsl --shutdown` (PowerShell), reabra o Ubuntu e confira: `free -h` (≈16 GB), `nproc` (8), `swapon --show` (8 GB). Por quê:
- **`memory=16GB`:** o padrão do WSL2 é ~50% da RAM, então já seria 16 GB, mas **fixar** torna a configuração explícita e reprodutível. Deixa 16 GB para o Windows: nunca falta memória no host e cabe um corpus de vários GB.
- **`processors=8`:** o Xeon tem 28 threads lógicas; fixar 8 dá reprodutibilidade, folga para o Windows e headroom para testar 1/2/4 workers (e 8 como extra) sem competir com o próprio host.
- **`autoMemoryReclaim=disabled`:** impede o WSL de devolver cache ao Windows durante o teste (estabiliza `Cached`/`MemAvailable`).

**4. Dois perfis.** Perfil **normal** (acima) e perfil **restrito**, só para a fase 2 do C5 (pressão de memória/swap):
```ini
[wsl2]
memory=4GB
processors=8
swap=4GB
```
Com 4 GB, um corpus de ~2 GB mais um lote grande já passam da RAM e forçam paginação, **sem risco para o Windows** (a VM é limitada). Registrem o ambiente de cada perfil e copiem o `.wslconfig` para o relatório:
```bash
scripts/env_info.sh normal      # -> results/env_normal.txt
scripts/env_info.sh restrita    # -> results/env_restrita.txt
```

**5. Ferramentas.** `sudo apt update && sudo apt install -y python3 python3-pip python3-venv sysstat strace psmisc git`; `python3 -m venv .venv && source .venv/bin/activate`. `strace` e `iostat` funcionam no WSL2.

**6. GPU (opcional, mas registrem na Parte A).** O driver NVIDIA fica **no Windows**; não instale driver Linux no WSL. Teste `nvidia-smi` e registre: `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv` (RTX 3060, 12 GB). O GenResearch-Servidor usa vetores e geração **simulados** e não depende de GPU (permitido). Se quiserem uma demo com modelo real (ex.: Ollama com modelo pequeno), acompanhem a VRAM com `nvidia-smi --query-gpu=memory.used --format=csv -l 1`, **não** commitem pesos e documentem versão/modelo. Gancho para a análise: runtimes como llama.cpp/Ollama carregam arquivos de pesos (GGUF) por **mmap**, o mesmo mecanismo do C2.

**7. systemd (opcional).** `systemd-run` só funciona se `/etc/wsl.conf` tiver `[boot]` `systemd=true` (WSL recente) — `wsl_check.sh` mostra o PID 1. **Se não tiver, ignorem o `systemd-run`**: o `.wslconfig` já faz o papel de limite.

**8. Rotina antes de cada bateria de medições** (citem no relatório): (a) Windows em plano **Alto desempenho**, máquina na tomada; (b) fechar navegador, jogos, Docker Desktop, outras distros WSL (**compartilham a mesma VM/memória**), Teams, antivírus em varredura, OneDrive e Windows Update; (c) `wsl --shutdown`, reabrir e rodar `scripts/wsl_check.sh`; (d) rodar a bateria inteira na mesma sessão, sem usar o PC, e anotar o horário.

### O que muda na interpretação no WSL2 (escreva na seção “Limitações”)
- `MemTotal`, swap e CPUs que o Linux vê são os **da VM** (16 GB e 8 vCPUs), não da máquina; o swap é um arquivo virtual (`swap.vhdx`) no disco do Windows.
- `lsblk`/`iostat` mostram **discos virtuais**: o Windows também mantém cache do arquivo VHDX. Por isso a leitura “fria” (cache do Linux limpo) pode ainda ser servida pelo cache do Windows → diferenças cold×warm menores que em Linux nativo. **Isso é um achado válido**, discutam-no.
- Faltas de página, `RSS`/`VSZ`, `strace`, threads e sincronização são **medidos dentro do kernel Linux** e valem normalmente.
- Há overhead de virtualização (Hyper-V); os números absolutos não generalizam para hardware nativo nem para outros processadores (o Xeon E5-2680 v4 é de 2016, 2,4 GHz base: laços Python puros serão relativamente lentos). Compare **configurações entre si**.
- A **GPU não participa** da carga medida (VRAM, PCIe e múltiplas GPUs ficam fora do escopo): citem como limitação.
- Para validar a fria: `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'` costuma funcionar no WSL2 (mais “pura” que o `fadvise` padrão do código); documentem qual usaram.

---
## 0. Antes de tudo (30 min, equipe toda)
1. **Ambiente oficial: WSL2** configurado conforme a seção 0-A (VM de 16 GB/8 vCPUs). A máquina principal de testes gera **todos os números finais**.
2. Criem o repositório público no GitHub com o nome exigido pelo docente e façam `git commit` do projeto.
3. Dentro do WSL (no **disco Linux**, veja 0-A):
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv sysstat strace psmisc git
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/wsl_check.sh      # confere memória, CPUs, sistema de arquivos e avisa o que estiver fora do plano
```
4. Divisão sugerida (7 pessoas): (1) ambiente/Parte A · (2) corpus+ingestão · (3) servidor/fila/workers · (4) cache+Parte D · (5) C1/C2/C5 · (6) C3/C4/C6+gráficos · (7) relatório/slides/vídeo. **Todos** devem dominar o código todo: a banca pergunta a qualquer um.

---
## 1. Parte A — Ambiente (evidência)
```bash
./scripts/env_info.sh        # gera results/env.txt
```
O script registra: uname, `/proc/version` (mostra `microsoft-standard-WSL2`), os-release, `lscpu`, `nproc`, `free`, `/proc/meminfo`, `lsblk`, `df -hT`, swap, versões de Python/bibliotecas, commit, `vmstat`, `iostat`, **GPU/VRAM (`nvidia-smi`)** e, quando acessível pelo WSL, informações do **host Windows** (CPU, RAM física, versão do WSL e o conteúdo do `.wslconfig`).
Na tabela de ambiente do relatório informem: Windows (versão), WSL2 (versão e kernel), Ubuntu, CPU do host e vCPUs alocadas, RAM do host e RAM/swap da VM, disco/ext4, GPU (RTX 3060, 12 GB, driver), Python e bibliotecas, commit e data.

No relatório explique (com suas palavras e com números do `env.txt`):
- **MemFree** = RAM totalmente ociosa. **MemAvailable** = estimativa do que pode ser usado por novos programas sem swap (inclui cache recuperável). **Cache** (page cache) guarda blocos de arquivos lidos/escritos. **Swap** = área em disco para páginas anônimas (no WSL2, um arquivo VHDX).
- Cache de páginas **não é desperdício**: acelera a 2ª leitura e é descartado sob pressão. Por isso MemFree baixo ≠ problema. (No WSL2 isso fica visível: depois de ler um arquivo grande, `free -h` mostra o cache alto.)
- Relevância para IA: datasets, índices vetoriais, embeddings e checkpoints são arquivos grandes; a leitura passa pelo page cache, e `mmap` mapeia o arquivo no espaço de endereçamento com **paginação por demanda** (faltas de página).

---
## 2. Gerar os dados (sintéticos)
Tudo dentro de `~/genresearch-servidor` (ext4, não `/mnt/c`).
```bash
python -m genresearch.gen_corpus --size-mb 20  --docs 200  --out data/raw_small
python -m genresearch.gen_corpus --size-mb 200 --docs 1000 --out data/raw_medium
python -m genresearch.ingest --raw data/raw_small  --out data/small
python -m genresearch.ingest --raw data/raw_medium --out data/medium
```
Cada `data/<nome>/` contém `vectors.bin` (float32, n×dim), `meta.sqlite` (id, doc, texto) e `manifest.json` (tamanho do corpus/índice e tempos de leitura/embedding/escrita → métrica de **ingestão**).

**Dataset grande (para C1/C2/C5), dimensionado para a VM de 16 GB:**
```bash
python -m genresearch.gen_corpus --size-mb 2000 --docs 2000 --out data/raw_large   # ~10+ min nesse Xeon; deixe rodando
python -m genresearch.ingest --raw data/raw_large --out data/large --embed random   # random acelera a ingestão
rm -rf data/raw_large                                                                # libera ~2 GB
```
Resultado aproximado: ~4,2 milhões de fragmentos, `vectors.bin` ≈ 2,1 GB, SQLite ≈ 2,5 GB (confira no `manifest.json`). Quem não é o responsável pelos dados deve usar apenas `small`.

*Bônus opcional (mmap maior que a RAM):* com a VM em 4 GB (config do C5) e um corpus de ~6 GB, o `mmap` consegue varrer o arquivo (o kernel vai evictando páginas), enquanto a leitura convencional inteira esgota memória. É uma demonstração forte, mas custa ~20 GB de disco e tempo; só faça se sobrar prazo e rode apenas `--mode mmap`.

Dados NÃO vão para o Git (`data/` está no `.gitignore`); o README explica como regerar (semente fixa = reprodutível).

Teste rápido do servidor:
```bash
python -m genresearch.server --data data/small --requests 100 --workers 2 --tag teste
head results/logs/teste.log        # eventos de ingestão/consulta/recuperação/cache/geração/falha/encerramento
```

---
## 3. Experimentos (rodar 3 repetições cada; já está no código)
Use o monitor para gravar `vmstat`, `iostat` e `/proc/meminfo` em paralelo:
```bash
scripts/monitor.sh c1c2 python -m experiments.c1_c2_read_vs_mmap --datasets data/small data/medium data/large --reps 3
scripts/monitor.sh c3   python -m experiments.c3_concurrency --data data/small --reps 3 --workers 1 2 4 8   # 8 é extra (VM com 8 vCPUs)
python -m experiments.c3b_gil_threads_vs_processes --reps 3 --workers 1 2 4 8
scripts/monitor.sh c4   python -m experiments.c4_cache --data data/small --reps 3
scripts/monitor.sh c5   python -m experiments.c5_memory_pressure --datasets data/small data/medium data/large --max-mb 10000 --reps 3   # FASE 1, VM de 16 GB (veja abaixo)
python -m experiments.c6_failures --data data/small --reps 3
python -m experiments.d_sync --reps 3
scripts/evidence.sh data/small          # strace, ps -L, /proc/PID/status, smaps_rollup
python -m experiments.plots             # tabelas (mediana, p95) e gráficos
```
Os resultados brutos ficam em `results/*.csv` (uma linha por execução, com timestamp). **Se mudar colunas, apague o CSV antigo.**

| Config | Script | Fatores variados | O que olhar |
|---|---|---|---|
| **C1 / C2** read × mmap | `c1_c2_read_vs_mmap` | modo, padrão (seq/aleatório), fria/quente, tamanho do dataset | `t_open`, `t_load`, `t_scan`, `rss_mb`, `vsz_mb`, `d_minflt`, `d_majflt`, `d_read_mb` |
| **C3** fila + workers | `c3_concurrency` (+`c3b`) | workers 1/2/4, capacidade da fila 8/128, carga `sleep` × `cpu` | `throughput_rps`, `total_p95_ms`, `wait_mean_ms`, `utilization`, `queue_max` |
| **C4** cache | `c4_cache` | repetidas × distintas, capacidade 0/10/100, LRU × FIFO | `cache_hit_rate`, `cache_evictions`, `cache_saved_s`, `wall_s` |
| **C5** pressão de memória | `c5_memory_pressure` | corpus, **lote** (1…1024) | `peak_rss_mb`, `t_compute`, `d_majflt`, `d_pswpout`, `max_swap_mb`, status |
| **C6** falhas | `c6_failures` | arquivo ausente, índice fora, fila cheia, serviço externo | `failed`, `dropped`, `retries`, recuperação |
| **Parte D** | `d_sync` | com × sem lock/mutex | contagens perdidas, log corrompido, itens perdidos/duplicados, deadlock |

### Cuidados importantes
- **C1/C2 "fria"**: o script usa `posix_fadvise(DONTNEED)` (funciona sem root). Alternativa: `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'` antes da medição (funciona no WSL2) — documentem qual usaram. Lembrem do **cache duplo do host Windows** (seção 0-A (“O que muda na interpretação”)): a leitura fria é otimista.
- **C1/C2 no WSL2 de 16 GB:** o dataset `large` (~2 GB) cabe inteiro no page cache; por isso a leitura "quente" será muito rápida e a diferença read × mmap vai aparecer principalmente em **faltas de página, RSS/VSZ e syscalls** (`strace -c`), não só em tempo.
- **C3 / C3b:** com 8 vCPUs, o `cpu` (Python puro) **não escala com threads** (GIL) mas escala com processos até ~8; o `sleep` escala com threads. Isso responde diretamente "em que ponto gerou contenção".
- **C5: duas fases, para pressão de memória SEGURA no WSL2.**
  *Fase 1 (VM 16 GB, padrão do experimento):* rode o comando acima. O guard pula passos acima de 85% da memória disponível ou de `--max-mb`; com `large`, lotes ≥ 256 já chegam a vários GB e o 1024 será pulado — registre isso. Você verá RSS e tempo crescendo com o lote e o corpus, sem swap.
  *Fase 2 (VM de 4 GB + swap, para provocar paginação):* edite o `.wslconfig` temporariamente:
  ```ini
  [wsl2]
  memory=4GB
  processors=8
  swap=4GB
  ```
  `wsl --shutdown`, reabra, confira `free -h` (≈4 GB) e rode:
  ```bash
  scripts/monitor.sh c5_swap python -m experiments.c5_memory_pressure --datasets data/large \
      --batches 64 128 256 --allow-swap --max-mb 7000 --reps 1
  ```
  Com `large` (~2,1 GB) e lote 256 a demanda é ~6,4 GB > 4 GB: deve haver swap (`d_pswpout`, `max_swap_mb`, colunas `si/so` do vmstat) e tempo muito maior (pode levar minutos; mantenham `--reps 1` ou 2). O Windows fica protegido porque a VM está limitada. Se o kernel matar o processo (OOM), o CSV registra `killed_or_error`; guardem a evidência com `dmesg | tail -20` (mensagem "Out of memory: Killed process"). **Depois, restaurem o `.wslconfig` de 16 GB** e rodem `wsl --shutdown`.
  Se o swap não for observado, justifiquem tecnicamente (permitido) e usem a Fase 1 como "alternativa equivalente".
- **Ruído**: feche programas pesados no Windows e siga a rotina da seção 0-A, item 8; mesma sessão, mesma carga; registre o horário.
- Não alterem corpus entre configurações (semente fixa).

---
## 4. Parte D — o que cada demonstração prova
1. **Cache sem lock** (`d_cache_race`): com 8 threads, `hits+misses` < operações (**atualização perdida**) e, às vezes, o cache excede a capacidade. Com `Lock`, zero perdas, porém **mais lento** (trade-off: serialização/contenção). A variante `gap=True` força o entrelaçamento (`time.sleep(0)` entre ler e escrever); `gap=False` mostra que, mesmo sem forçar, ainda ocorre perda.
2. **Log intercalado** (`d_log_race`): sem lock, a mesma linha é escrita em 3 pedaços e linhas se misturam → corrompidas. Com lock, 0.
3. **Buffer limitado** (`d_buffer`): `empty`/`full`/`mutex`. Sem `mutex`, os índices `in/out` sofrem corrida → itens **perdidos e duplicados**. Com mutex, correto.
4. **Deadlock isolado** (`d_deadlock`): dois locks em ordem oposta → espera circular detectada por **timeout**; recuperação por **ordem global de aquisição**. As quatro condições de Coffman: exclusão mútua, posse e espera, não-preempção, espera circular (quebrar uma resolve).
5. No servidor real: `queue.Queue` (mutex + condições internas) é o buffer limitado; `Cache` usa `Lock`; `Logger` usa `Lock`; SQLite é aberto **só para leitura, uma conexão por thread**.

> Python tem GIL; por isso atualizações “simples” às vezes parecem seguras. A demonstração mostra que **ler-modificar-escrever não é atômico** e que o resultado depende do escalonador.

---
## 5. Como interpretar (respostas às “Questões de análise”)
| Pergunta | Onde buscar | O que esperar/argumentar |
|---|---|---|
| Corpus/lote vs RAM e latência | `c5_*.png`, `summary_c5.csv` | RSS cresce ~linearmente com corpus (read) e com `n×lote×4 B`; tempo sobe; com pouca RAM surgem faltas maiores/swap (ou guard/MemoryError). |
| read × mmap | `c1c2_*.png` | **Fria**: mmap abre rápido e “paga” depois em faltas de página (majflt) durante o acesso; read paga na leitura inteira (RSS ≈ tamanho do arquivo, anônimo). **Quente**: ambos rápidos; mmap compartilha páginas do cache (RSS conta páginas mapeadas, VSZ ≈ arquivo inteiro). **Aleatório**: mmap evita 1 syscall por leitura. Use `strace -c` como prova. |
| Cache reduziu tempo? | `c4_*.png` | Alta taxa em “repetidas_20”; ≈ 0 em “distintas”. Cache pequeno + padrão amplo → evicções; compare LRU × FIFO. Duplicação de cômputo: `computes − unique_computed` (dois workers perdem a mesma chave ao mesmo tempo). |
| Concorrência aumentou vazão? | `c3_*.png`, `c3b_gil.png` | `sleep` (E/S): vazão ~escala até 4 workers. `cpu` (Python puro): **não escala** por causa do GIL; processos escalam (c3b). Fila pequena → produtores bloqueiam; utilização do worker perto de 1. Em retrieval com NumPy, a banda de memória limita o ganho. |
| Recurso compartilhado exigindo exclusão mútua | seção 4 | cache, log, buffer. |
| Paginação/swap | C5, `vmstat` (colunas `si/so`), `/proc/vmstat` | Mostre `d_majflt`, `d_pswpout`, `max_swap_mb`; se não ocorreu, diga que não ocorreu e por quê. |
| Relação com RAG/checkpoints | seção 7 do relatório | índice vetorial grande = arquivo mapeado; checkpoints = leitura sequencial grande (page cache, cold start); cache de respostas/KV; fila + lotes = servidores de inferência. |
| Limitações | | Vetores e geração simulados, um nó, **GPU RTX 3060 (12 GB) não usada na carga** (sem VRAM, PCIe, múltiplas GPUs ou distribuído), corpus de poucos GB, GIL, **virtualização do WSL2 e cache duplo do host Windows**, VM limitada a 16 GB/8 vCPUs, `drop_caches` vs `fadvise`, resultados específicos do Xeon E5-2680 v4. |

**Dica de correção metodológica:** reporte **média, mediana e p95** (`summary_*.csv`), cite o nº de repetições, e comente variabilidade (barras de erro nos gráficos de C3). Evite conclusões fortes com diferenças menores que o desvio-padrão.

