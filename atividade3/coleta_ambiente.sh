#!/usr/bin/env bash
# Parte A: registra o ambiente do terminal E do daemon Docker, baixa a imagem
# e fixa o digest em imagem.env. Saida: registros/ambiente/ambiente_<data>.txt
#
# Uso: bash coleta_ambiente.sh            (precisa de internet so no 1o pull)
#      IMAGEM_BASE=python:3.12-slim bash coleta_ambiente.sh
set -uo pipefail

cd "$(dirname "$0")" || exit 1
IMAGEM_BASE="${IMAGEM_BASE:-python:3.12-slim}"
DATA="$(date +%Y%m%d_%H%M%S)"
DIR="registros/ambiente"
mkdir -p "$DIR"
OUT="$DIR/ambiente_${DATA}.txt"

secao() { printf '\n===== %s =====\n' "$1"; }
roda()  { printf '$ %s\n' "$*"; "$@" 2>&1 || printf '[falhou: codigo %s]\n' "$?"; }

{
  secao "Data da coleta"
  date -Is

  secao "Terminal (onde o comando foi digitado)"
  roda uname -a
  [ -r /etc/os-release ] && roda cat /etc/os-release
  roda nproc
  if [ -r /proc/meminfo ]; then grep -E 'MemTotal|SwapTotal' /proc/meminfo; fi
  if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Indicio: kernel WSL2 (/proc/version cita Microsoft)"
  fi
  if command -v systemd-detect-virt >/dev/null 2>&1; then
    printf 'systemd-detect-virt: %s\n' "$(systemd-detect-virt 2>/dev/null || echo none)"
  fi
  if [ -r /sys/fs/cgroup/cgroup.controllers ]; then
    echo "cgroup v2 no terminal. Controladores na raiz:"
    cat /sys/fs/cgroup/cgroup.controllers
  else
    echo "Sem /sys/fs/cgroup/cgroup.controllers no terminal (v1, macOS/Windows ou acesso restrito)"
  fi

  secao "Docker: versoes"
  roda docker version --format 'Cliente={{.Client.Version}} Servidor={{.Server.Version}} API={{.Server.APIVersion}}'
  roda docker compose version

  secao "Docker: daemon (o Linux que realmente roda os conteineres)"
  # Campos escolhidos; nao publicar 'docker info' integral (tem nomes/caminhos)
  roda docker info --format 'SO_do_daemon={{.OperatingSystem}}
Kernel_do_daemon={{.KernelVersion}}
Arquitetura={{.Architecture}}
CPUs_daemon={{.NCPU}}
RAM_daemon_bytes={{.MemTotal}}
Cgroup={{.CgroupVersion}}
Driver={{.CgroupDriver}}
Runtime_padrao={{.DefaultRuntime}}
Opcoes_seguranca={{json .SecurityOptions}}
Avisos={{json .Warnings}}'

  secao "Imagem"
  roda docker pull "$IMAGEM_BASE"
  IMAGEM_LAB="$(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGEM_BASE" 2>/dev/null || true)"
  if [ -n "$IMAGEM_LAB" ]; then
    printf 'IMAGEM_LAB=%s\n' "$IMAGEM_LAB"
    printf 'export IMAGEM_LAB=%q\n' "$IMAGEM_LAB" > imagem.env
    echo "Digest gravado em imagem.env"
  else
    echo "ERRO: nao foi possivel obter o digest de $IMAGEM_BASE"
  fi

  if [ -n "$IMAGEM_LAB" ]; then
    secao "Visao de dentro de um conteiner (--network none)"
    roda docker run --rm --network none "$IMAGEM_LAB" sh -c '
      echo "kernel visto no conteiner: $(uname -r)";
      echo "/proc/self/cgroup: $(cat /proc/self/cgroup)";
      printf "controladores no cgroup do conteiner: ";
      cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null || echo "INDISPONIVEL";
      grep " /sys/fs/cgroup " /proc/self/mountinfo || true'
  fi

  secao "Codigo"
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'commit=%s\n' "$(git rev-parse HEAD)"
    git status --short | head -20
  else
    echo "Fora de um repositorio git"
  fi
} | tee "$OUT"

echo
echo "Registro salvo em $OUT. Revise antes de publicar (hostname, usuario, caminhos)."
