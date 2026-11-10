#!/usr/bin/env bash
# Partes B e D: evidencias de namespaces (PID, mount, network) em dois
# conteineres da mesma imagem e teste de montagem somente leitura.
# Remove apenas os conteineres que ele mesmo criou.
#
# Uso: bash evidencia_ns_mount.sh      (le IMAGEM_LAB de imagem.env)
# Saida: registros/namespaces/<data>/ e registros/readonly/<data>/
set -uo pipefail

cd "$(dirname "$0")" || exit 1
[ -z "${IMAGEM_LAB:-}" ] && [ -r imagem.env ] && . ./imagem.env
if [ -z "${IMAGEM_LAB:-}" ]; then
  echo "IMAGEM_LAB vazio. Rode antes: bash coleta_ambiente.sh" >&2
  exit 2
fi
case "$IMAGEM_LAB" in *@sha256:*) ;; *) echo "Aviso: IMAGEM_LAB sem digest: $IMAGEM_LAB" >&2 ;; esac

DATA="$(date +%Y%m%d_%H%M%S)"
A="so_atv3_ns_A_${DATA}"
B="so_atv3_ns_B_${DATA}"
CRIADOS=()
limpar() {
  for c in "${CRIADOS[@]}"; do docker rm -f "$c" >/dev/null 2>&1 || true; done
}
trap limpar EXIT INT TERM

# ---------------------------------------------------------------- Parte B
DNS="registros/namespaces/$DATA"
mkdir -p "$DNS"

for c in "$A" "$B"; do
  if docker run -d --name "$c" --label so.atv3=namespaces \
       --network none --memory 64m --pids-limit 16 \
       "$IMAGEM_LAB" sleep 300 >/dev/null; then
    CRIADOS+=("$c")
  else
    echo "Falha ao criar $c" >&2; exit 1
  fi
done
sleep 1

coletar() {  # $1 = nome, $2 = rotulo
  local c="$1" r="$2" pid
  pid="$(docker inspect --format '{{.State.Pid}}' "$c")"
  {
    echo "conteiner=$c ($r)"
    echo "coletado_em=$(date -Is)"
    echo "imagem=$IMAGEM_LAB"
    echo "PID_host=$pid   (PID no namespace do host do daemon)"
    echo "id=$(docker inspect --format '{{.Id}}' "$c" | cut -c1-12)"
    echo "comm_pid1=$(docker exec "$c" cat /proc/1/comm)"
    echo "pid_ns=$(docker exec "$c" readlink /proc/1/ns/pid)"
    echo "mnt_ns=$(docker exec "$c" readlink /proc/1/ns/mnt)"
    echo "net_ns=$(docker exec "$c" readlink /proc/1/ns/net)"
    echo "--- processos visiveis dentro (PIDs em /proc) ---"
    docker exec "$c" sh -c 'for p in /proc/[0-9]*; do printf "%s %s\n" "${p#/proc/}" "$(cat $p/comm 2>/dev/null)"; done'
    echo "--- interfaces de rede visiveis (/proc/net/dev) ---"
    docker exec "$c" sh -c 'tail -n +3 /proc/net/dev | cut -d: -f1'
    echo "--- hostname (UTS) ---"
    docker exec "$c" hostname
  } > "$DNS/$r.txt" 2>&1
  echo "$pid"
}

PID_A="$(coletar "$A" A)"
PID_B="$(coletar "$B" B)"

campo() { grep "^$1=" "$DNS/$2.txt" | head -1 | cut -d= -f2- | cut -d' ' -f1; }

# Visao do host: so funciona se este terminal estiver no mesmo Linux do daemon
{
  echo "Tentativa de ler os namespaces pelo /proc do terminal."
  echo "Em Docker Desktop/daemon remoto o PID_host nao existe neste /proc."
  echo "self_pid_ns=$(readlink /proc/self/ns/pid 2>&1)"
  echo "self_mnt_ns=$(readlink /proc/self/ns/mnt 2>&1)"
  echo "self_net_ns=$(readlink /proc/self/ns/net 2>&1)"
  for par in "A:$PID_A" "B:$PID_B"; do
    r="${par%%:*}"; p="${par#*:}"
    for ns in pid mnt net; do
      v="$(readlink "/proc/$p/ns/$ns" 2>&1 || true)"
      [ -z "$v" ] && v="sem permissao/inexistente (tente sudo readlink /proc/$p/ns/$ns)"
      echo "host_${r}_${ns}=$v"
    done
    echo "host_${r}_comm=$(cat "/proc/$p/comm" 2>&1)"
  done
} > "$DNS/visao_host.txt"

# Tabela comparativa
{
  echo "recurso,handle_A,handle_B,iguais"
  for ns in pid mnt net; do
    va="$(campo "${ns}_ns" A)"; vb="$(campo "${ns}_ns" B)"
    [ "$va" = "$vb" ] && ig=sim || ig=nao
    echo "$ns,$va,$vb,$ig"
  done
  ca="$(campo comm_pid1 A)"; cb="$(campo comm_pid1 B)"
  echo "pid1_comm,$ca,$cb,$([ "$ca" = "$cb" ] && echo sim || echo nao)"
  echo "PID_host,$PID_A,$PID_B,$([ "$PID_A" = "$PID_B" ] && echo sim || echo nao)"
} > "$DNS/namespaces.csv"

echo "== Namespaces ($DNS) =="
column -t -s, "$DNS/namespaces.csv" 2>/dev/null || cat "$DNS/namespaces.csv"

# ---------------------------------------------------------------- Parte D
DRO="registros/readonly/$DATA"
mkdir -p "$DRO" dados_demo
[ -f dados_demo/texto.txt ] || printf '%s\n' 'Documento sintetico' > dados_demo/texto.txt
chmod a+rx dados_demo; chmod a+r dados_demo/texto.txt
ls -la dados_demo > "$DRO/host_antes.txt"

R="so_atv3_ro_${DATA}"
CRIADOS+=("$R")
docker run --name "$R" --label so.atv3=readonly \
  --network none --user 65534:65534 --cap-drop ALL \
  --security-opt no-new-privileges:true --memory 64m --pids-limit 16 \
  -v "$PWD/dados_demo:/dados:ro" \
  "$IMAGEM_LAB" sh -c '
    echo "== identidade =="; id
    echo "== capabilities e no_new_privs do processo =="
    grep -E "^(CapEff|CapPrm|CapBnd|NoNewPrivs)" /proc/self/status
    echo "== montagem de /dados (procure ro) =="
    grep " /dados " /proc/self/mountinfo
    echo "== leitura =="
    cat /dados/texto.txt; echo "leitura_codigo=$?"
    echo "== tentativa de escrita em /dados =="
    touch /dados/novo.txt 2>&1; echo "escrita_dados_codigo=$?"
    echo "== controle: escrita em /tmp do proprio conteiner =="
    touch /tmp/controle.txt 2>&1; echo "escrita_tmp_codigo=$?"
    echo "== conteudo de /dados depois =="; ls -la /dados
  ' > "$DRO/readonly.txt" 2>&1
echo "codigo_saida_conteiner=$?" >> "$DRO/readonly.txt"
docker inspect --format 'SecurityOpt={{json .HostConfig.SecurityOpt}} CapDrop={{json .HostConfig.CapDrop}} User={{.Config.User}} Mounts={{json .Mounts}}' "$R" \
  | sed "s#$HOME#~#g" > "$DRO/inspect_resumo.txt"
ls -la dados_demo > "$DRO/host_depois.txt"

echo
echo "== Read-only ($DRO) =="
grep -E 'uid=|NoNewPrivs|CapEff|leitura_codigo|escrita_|Read-only|denied' "$DRO/readonly.txt"
echo
echo "Registros em $DNS e $DRO. Os conteineres criados aqui serao removidos agora."
