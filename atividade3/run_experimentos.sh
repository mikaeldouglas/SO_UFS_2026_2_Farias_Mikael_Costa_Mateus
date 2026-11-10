#!/usr/bin/env bash
# Parte C: seis execucoes (C1 = 0,5 CPU, C2 = 1,0 CPU; 3 repeticoes cada),
# alternando a ordem das condicoes. Mesma imagem, mesmo trabalho, 256 MiB de
# RAM, RAM+swap 256 MiB e pids-limit 64 nas duas condicoes.
#
# Uso:
#   export ITERACOES=20000000
#   PILOTO=1 bash run_experimentos.sh   # 1 execucao por condicao, para calibrar N
#   bash run_experimentos.sh            # as 6 execucoes principais
#
# Saida: registros/sessao_<data>/ (ou piloto_<data>/) com, para cada execucao,
#   NN_Cx_rY.json (medicao de dentro do conteiner), NN_Cx_rY.meta (host)
#   e NN_Cx_rY.stderr. Execucoes com erro sao mantidas.
set -uo pipefail

cd "$(dirname "$0")" || exit 1
[ -z "${IMAGEM_LAB:-}" ] && [ -r imagem.env ] && . ./imagem.env
: "${IMAGEM_LAB:?defina IMAGEM_LAB ou rode coleta_ambiente.sh}"
: "${ITERACOES:?defina ITERACOES, por exemplo: export ITERACOES=20000000}"
REPETICOES="${REPETICOES:-3}"
LIMITE_SEGUNDOS="${LIMITE_SEGUNDOS:-60}"
TIMEOUT_HOST="${TIMEOUT_HOST:-90}"
PAUSA="${PAUSA:-3}"
MEMORIA="256m"; MEMORIA_SWAP="256m"; PIDS=64
declare -A CPUS=([C1]=0.5 [C2]=1.0)

DATA="$(date +%Y%m%d_%H%M%S)"
if [ "${PILOTO:-0}" = "1" ]; then
  SESSAO="piloto_$DATA"; ORDEM=("1:C2" "1:C1")
else
  SESSAO="sessao_$DATA"; ORDEM=()
  for ((r=1; r<=REPETICOES; r++)); do
    if (( r % 2 == 1 )); then ORDEM+=("$r:C1" "$r:C2"); else ORDEM+=("$r:C2" "$r:C1"); fi
  done
fi
DIR="registros/$SESSAO"
mkdir -p "$DIR"

if command -v timeout >/dev/null 2>&1; then TMO=(timeout "$TIMEOUT_HOST"); else
  TMO=(); echo "Aviso: GNU timeout ausente; resta o limite interno de ${LIMITE_SEGUNDOS}s" >&2; fi

COMMIT="$(git rev-parse HEAD 2>/dev/null || echo sem_git)"
cat > "$DIR/parametros.txt" <<EOF
sessao=$SESSAO
inicio=$(date -Is)
imagem=$IMAGEM_LAB
iteracoes=$ITERACOES
repeticoes=$REPETICOES
memoria=$MEMORIA
memoria_swap=$MEMORIA_SWAP
pids_limit=$PIDS
cpus_C1=${CPUS[C1]}
cpus_C2=${CPUS[C2]}
limite_interno_s=$LIMITE_SEGUNDOS
timeout_host_s=$TIMEOUT_HOST
ordem=${ORDEM[*]}
commit=$COMMIT
EOF

ATUAL=""
limpar() { [ -n "$ATUAL" ] && docker rm -f "$ATUAL" >/dev/null 2>&1; true; }
trap limpar EXIT INT TERM

n=0
for item in "${ORDEM[@]}"; do
  rep="${item%%:*}"; cond="${item#*:}"; n=$((n+1))
  base="$(printf '%02d_%s_r%s' "$n" "$cond" "$rep")"
  nome="so_atv3_cg_${DATA}_${base}"
  ATUAL="$nome"
  load="$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo indisponivel)"
  echo "[$n/${#ORDEM[@]}] $cond rep $rep (cpus=${CPUS[$cond]}, N=$ITERACOES)..."

  ini="$(date -Is)"; t0="$(date +%s.%N)"
  "${TMO[@]}" docker run --name "$nome" --label so.atv3=cgroups \
    --network none \
    --cpus "${CPUS[$cond]}" --memory "$MEMORIA" --memory-swap "$MEMORIA_SWAP" \
    --pids-limit "$PIDS" \
    --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges:true \
    -e ITERACOES="$ITERACOES" -e LIMITE_SEGUNDOS="$LIMITE_SEGUNDOS" \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$PWD/carga_cpu.py:/lab/carga_cpu.py:ro" \
    -v "$PWD/medir_cgroup.py:/lab/medir_cgroup.py:ro" \
    "$IMAGEM_LAB" python3 /lab/medir_cgroup.py \
    > "$DIR/$base.json" 2> "$DIR/$base.stderr"
  codigo=$?
  t1="$(date +%s.%N)"
  pedido="$(docker inspect --format 'NanoCpus={{.HostConfig.NanoCpus}} CpuQuota={{.HostConfig.CpuQuota}} CpuPeriod={{.HostConfig.CpuPeriod}} Memory={{.HostConfig.Memory}} MemorySwap={{.HostConfig.MemorySwap}} PidsLimit={{.HostConfig.PidsLimit}} OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}}' "$nome" 2>&1)"
  docker rm -f "$nome" >/dev/null 2>&1; ATUAL=""

  cat > "$DIR/$base.meta" <<EOF
ordem=$n
condicao=$cond
repeticao=$rep
cpus_pedido=${CPUS[$cond]}
iteracoes=$ITERACOES
inicio=$ini
codigo_saida=$codigo
wall_host_s=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')
loadavg_antes=$load
docker_inspect=$pedido
EOF
  if [ "$codigo" -ne 0 ]; then
    echo "    ERRO (codigo $codigo; 124 = timeout do host). Registro mantido em $DIR/$base.*"
  else
    python3 - "$DIR/$base.json" <<'PY' 2>/dev/null || true
import json, sys
d = json.load(open(sys.argv[1])); c = d["carga"]; s = d["delta_cpu_stat"]
print(f"    wall={c['wall_s']:.2f}s cpu={c['cpu_processo_s']:.2f}s correto={c['correto']} "
      f"cpu.max='{d['config_cgroup']['cpu.max']}' nr_throttled={s.get('nr_throttled')}")
PY
  fi
  sleep "$PAUSA"
done

echo "fim=$(date -Is)" >> "$DIR/parametros.txt"
if [ "${PILOTO:-0}" = "1" ]; then
  python3 - "$DIR" <<'PY' || true
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*_C2_*.json")):
    try:
        c = json.load(open(f))["carga"]
    except Exception:
        continue
    if c.get("status") == "ok":
        n = int(round(c["trabalho_por_s"] * 12, -6))
        print(f"Piloto: C2 fez {c['trabalho_por_s']/1e6:.1f} M iter/s.")
        print(f"Sugestao: export ITERACOES={n}  (C2 ~12 s, C1 ~24 s; abaixo do limite de 60 s)")
PY
  echo "Piloto nao entra na comparacao. Congele ITERACOES e rode sem PILOTO=1."
else
  echo "Pronto. Registros em $DIR. Agora: python3 resumo.py $DIR"
fi
