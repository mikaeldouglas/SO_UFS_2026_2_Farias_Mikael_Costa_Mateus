#!/usr/bin/env bash
# Evidências exigidas: chamadas de sistema (strace), threads/processos e memória do processo.
D=${1:-data/small}; E=results/evidence; mkdir -p $E
command -v strace >/dev/null || echo "AVISO: instale strace (sudo apt install strace strace sysstat psmisc)"
echo "== strace C1 (read) vs C2 (mmap): contagem de syscalls =="
for M in read mmap; do
  strace -f -c -o $E/strace_${M}_resumo.txt python -m experiments.c1_c2_read_vs_mmap --child --mode $M --pattern seq --cold --data $D >/dev/null
  strace -f -e trace=openat,read,pread64,mmap,munmap,madvise,fadvise64 -o $E/strace_${M}_trace.txt \
     python -m experiments.c1_c2_read_vs_mmap --child --mode $M --pattern seq --data $D >/dev/null
done
echo "== threads/processos/memória do servidor em execução =="
python -m genresearch.server --data $D --workers 4 --requests 3000 --gen-ms 30 --cache-cap 0 --query-pool 0 --tag evidence >/dev/null & PID=$!
sleep 2
{ echo "### ps -L (threads)"; ps -L -o pid,tid,pcpu,stat,nlwp,comm -p $PID
  echo; echo "### /proc/$PID/status"; grep -E 'Name|Threads|VmSize|VmRSS|VmSwap|voluntary' /proc/$PID/status
  echo; echo "### smaps_rollup"; cat /proc/$PID/smaps_rollup
  echo; echo "### arquivos abertos"; ls -l /proc/$PID/fd | head -30
  echo; echo "### pstree"; pstree -p $PID 2>/dev/null; } > $E/server_processos_threads.txt
wait $PID; echo "evidências em $E"
