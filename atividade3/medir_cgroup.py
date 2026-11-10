#!/usr/bin/env python3
"""Roda DENTRO do conteiner: le o cgroup v2 do proprio conteiner antes e
depois da carga, executa carga_cpu.py como subprocesso e imprime um JSON.

Com cgroup v2 e cgroupns privado (padrao do Docker em v2), /sys/fs/cgroup
dentro do conteiner e a raiz do cgroup do proprio conteiner. Assim os
arquivos lidos aqui sao os limites efetivamente aplicados pelo kernel, e nao
apenas as flags pedidas ao Docker.

Variaveis: ITERACOES, LIMITE_SEGUNDOS, CGROUP_DIR (padrao /sys/fs/cgroup).
"""
import json
import os
import subprocess
import sys
import time

CG = os.environ.get("CGROUP_DIR", "/sys/fs/cgroup")
AQUI = os.path.dirname(os.path.abspath(__file__))

ARQUIVOS_UNICOS = ["cpu.max", "cpu.weight", "memory.max", "memory.swap.max",
                   "memory.high", "pids.max", "cgroup.controllers"]
ARQUIVOS_STAT = ["cpu.stat"]
ARQUIVOS_MEM = ["memory.current", "memory.peak", "pids.current", "pids.peak"]


def ler(nome):
    try:
        with open(os.path.join(CG, nome)) as f:
            return f.read().strip()
    except OSError as e:
        return f"INDISPONIVEL ({e.__class__.__name__})"


def ler_stat(nome):
    bruto = ler(nome)
    d = {}
    if bruto.startswith("INDISPONIVEL"):
        return d
    for linha in bruto.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[1].lstrip("-").isdigit():
            d[partes[0]] = int(partes[1])
    return d


def ler_memoria_evento():
    return ler_stat("memory.events")


def instantaneo():
    s = {n: ler(n) for n in ARQUIVOS_MEM}
    s["cpu.stat"] = ler_stat("cpu.stat")
    s["memory.events"] = ler_memoria_evento()
    s["t_monotonic"] = time.monotonic()
    return s


def main():
    cfg = {n: ler(n) for n in ARQUIVOS_UNICOS}
    try:
        with open("/proc/self/cgroup") as f:
            cfg["proc_self_cgroup"] = f.read().strip()
    except OSError:
        cfg["proc_self_cgroup"] = "INDISPONIVEL"

    antes = instantaneo()
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, os.path.join(AQUI, "carga_cpu.py")],
                          capture_output=True, text=True)
    t1 = time.monotonic()
    depois = instantaneo()

    try:
        carga = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        carga = {"status": "saida_invalida", "stdout": proc.stdout[-500:]}

    delta = {}
    for k, v in depois["cpu.stat"].items():
        if k in antes["cpu.stat"]:
            delta[k] = v - antes["cpu.stat"][k]

    print(json.dumps({
        "config_cgroup": cfg,
        "antes": antes,
        "depois": depois,
        "delta_cpu_stat": delta,
        "carga": carga,
        "carga_returncode": proc.returncode,
        "carga_stderr": proc.stderr[-1000:],
        "wall_subprocesso_s": round(t1 - t0, 6),
    }))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
