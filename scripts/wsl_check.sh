#!/usr/bin/env bash
# Verificação de prontidão do WSL2 (rode antes de qualquer experimento)
grep -qi microsoft /proc/version && echo "[ok] WSL detectado: $(uname -r)" || echo "[aviso] não parece WSL"
case "$(pwd -P)" in
  /mnt/*) echo "[ERRO] projeto em /mnt/... (disco do Windows via 9P: lento e distorce mmap/cache). Mova para ~/ (ex.: cp -r para ~/genresearch-servidor)";;
  *) echo "[ok] projeto no filesystem Linux: $(pwd -P)";;
esac
echo "[info] CPUs: $(nproc) | RAM/swap:"; free -h | sed -n '1,3p'
SW=$(awk '/SwapTotal/{print $2}' /proc/meminfo); [ "${SW:-0}" -gt 0 ] && echo "[ok] swap ativo" || echo "[aviso] sem swap (defina swap em .wslconfig se for estudar swap no C5)"
echo "[info] PID 1 = $(ps -p 1 -o comm= 2>/dev/null) (systemd => 'systemd'; necessário só para systemd-run)"
for t in python3 pip strace iostat vmstat pstree git; do command -v $t >/dev/null && echo "[ok] $t" || echo "[FALTA] $t -> sudo apt install -y python3-pip sysstat strace psmisc git"; done
echo "[info] disco livre aqui:"; df -h . | tail -1
[ -w /proc/sys/vm/drop_caches ] && echo "[ok] drop_caches gravável" || echo "[info] drop_caches exige sudo (o código usa fadvise por padrão)"
echo "[info] swappiness: $(cat /proc/sys/vm/swappiness)"
MT=$(awk '/MemTotal/{printf "%d", $2/1048576}' /proc/meminfo)
if [ "$MT" -ge 14 ]; then echo "[info] perfil NORMAL detectado (~${MT} GB na VM)"; elif [ "$MT" -le 5 ]; then echo "[info] perfil RESTRITO detectado (~${MT} GB na VM): use para C5 fase 2"; else echo "[aviso] RAM da VM (~${MT} GB) não corresponde a nenhum perfil do guia (16 GB ou 4 GB)"; fi
[ "$(nproc)" -eq 8 ] && echo "[ok] 8 vCPUs" || echo "[aviso] $(nproc) vCPUs (guia usa processors=8 no .wslconfig)"
if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then echo "[ok] GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"; else echo "[info] nvidia-smi indisponível (GPU não é necessária para a carga simulada)"; fi
[ -f /proc/pressure/memory ] && echo "[info] PSI memória disponível (/proc/pressure/memory)"
