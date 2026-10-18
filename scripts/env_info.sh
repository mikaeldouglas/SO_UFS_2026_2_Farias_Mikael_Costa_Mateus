#!/usr/bin/env bash
# Parte A: registra o ambiente em results/env.txt
mkdir -p results; OUT=results/env${1:+_$1}.txt   # uso: scripts/env_info.sh [rotulo]  ex.: normal | restrita
{
echo "## data/hora: $(date -Is)"
echo "## commit: $(git rev-parse HEAD 2>/dev/null || echo 'sem git')"
for c in "uname -a" "cat /etc/os-release" "lscpu" "free -h" "cat /proc/meminfo" "lsblk" "df -hT ." \
         "swapon --show" "cat /proc/sys/vm/swappiness" "python3 --version" "pip freeze" "nvidia-smi -L" \
         "systemd-detect-virt" "cat /proc/version" "cat /etc/wsl.conf" "wslinfo" \
         "wsl.exe --version | iconv -f utf-16le -t utf-8" "cat /proc/swaps" "nproc" \
         "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv"; do
  echo; echo "### $c"; eval "$c" 2>&1 || echo "(indisponivel)"
done
echo; echo "### host Windows (CPU/RAM física)"
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | Format-List; [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)" 2>&1 | tr -d '\r' || echo "(indisponivel)"
echo; echo "### .wslconfig"
WU=$(cmd.exe /c "echo %USERPROFILE%" 2>/dev/null | tr -d '\r'); [ -n "$WU" ] && cat "$(wslpath "$WU")/.wslconfig" 2>&1 || echo "(.wslconfig nao encontrado: padrao do WSL2)"
echo; echo "### vmstat (5 amostras)"; vmstat 1 5
echo; echo "### iostat (3 amostras)"; (iostat -xz 1 3 2>&1 || echo "instale: sudo apt install sysstat")
} > "$OUT"
echo "gravado em $OUT"
