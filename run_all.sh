#!/usr/bin/env bash
# Reprodução completa. Ajuste os tamanhos ao seu hardware. Tempo estimado: 40-90 min. C5 deve rodar à parte no perfil restrito do .wslconfig (ver GUIA).
set -e
scripts/wsl_check.sh
pip install -r requirements.txt
scripts/env_info.sh normal
# ---- dados (sintéticos): pequeno / médio / grande ----
python -m genresearch.gen_corpus --size-mb 20  --docs 200  --out data/raw_small
python -m genresearch.gen_corpus --size-mb 200 --docs 1000 --out data/raw_medium
python -m genresearch.ingest --raw data/raw_small  --out data/small
python -m genresearch.ingest --raw data/raw_medium --out data/medium
# grande (opcional; VM de 16 GB; ~10 min): embeddings aleatórios aceleram a ingestão
# python -m genresearch.gen_corpus --size-mb 2000 --docs 2000 --out data/raw_large
# python -m genresearch.ingest --raw data/raw_large --out data/large --embed random && rm -rf data/raw_large
# ---- experimentos ----
scripts/monitor.sh c1c2 python -m experiments.c1_c2_read_vs_mmap --datasets data/small data/medium --reps 3
scripts/monitor.sh c3   python -m experiments.c3_concurrency --data data/small --reps 3 --workers 1 2 4 8
python -m experiments.c3b_gil_threads_vs_processes --reps 3 --workers 1 2 4 8
scripts/monitor.sh c4   python -m experiments.c4_cache --data data/small --reps 3
scripts/monitor.sh c5   python -m experiments.c5_memory_pressure --datasets data/small data/medium --max-mb 10000 --reps 3   # FASE 1 (VM 16 GB). Fase 2 (4 GB + swap): ver GUIA seção 3
python -m experiments.c6_failures --data data/small --reps 3
python -m experiments.d_sync --reps 3
scripts/evidence.sh data/small
python -m experiments.plots
echo "Pronto: veja results/ e results/figures/"
