#!/usr/bin/env bash
# uso: scripts/monitor.sh <tag> <comando...>   (grava vmstat/iostat/meminfo durante o comando)
TAG=$1; shift; D=results/monitor; mkdir -p "$D"
cp /proc/meminfo "$D/${TAG}_meminfo_antes.txt"; cp /proc/vmstat "$D/${TAG}_vmstat_antes.txt"
vmstat -t 1 > "$D/${TAG}_vmstat.log" & P1=$!
P2=""; if command -v iostat >/dev/null; then iostat -xz 1 > "$D/${TAG}_iostat.log" & P2=$!; fi
"$@"; RC=$?
cp /proc/meminfo "$D/${TAG}_meminfo_depois.txt"; cp /proc/vmstat "$D/${TAG}_vmstat_depois.txt"
kill $P1 $P2 2>/dev/null; wait 2>/dev/null; exit $RC
