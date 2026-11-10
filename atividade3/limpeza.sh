#!/usr/bin/env bash
# Remove somente conteineres deste laboratorio (rotulo so.atv3), caso algum
# tenha ficado para tras depois de um Ctrl+C. Nao apaga registros nem a imagem.
set -uo pipefail
ids="$(docker ps -aq --filter label=so.atv3)"
if [ -z "$ids" ]; then
  echo "Nenhum conteiner do laboratorio encontrado."
else
  docker ps -a --filter label=so.atv3 --format '{{.Names}}\t{{.Status}}'
  # shellcheck disable=SC2086
  docker rm -f $ids >/dev/null && echo "Removidos."
fi
echo "Para remover tambem a imagem (opcional): docker image rm python:3.12-slim"
