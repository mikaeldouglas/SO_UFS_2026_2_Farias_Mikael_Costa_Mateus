#!/usr/bin/env python3
"""Carga deterministica de CPU com trabalho fixo e correcao verificavel.

Calcula soma(i*i) para i em [0, N) modulo P = 2**61 - 1 com um laco Python
(gasta CPU de verdade) e compara com a formula fechada (N-1)N(2N-1)/6 mod P.
Se os dois valores baterem, o trabalho foi feito por completo e corretamente.

Limite interno de seguranca: aborta com status "timeout" depois de
LIMITE_SEGUNDOS (padrao 60 s), conferindo o relogio a cada BLOCO iteracoes.

Uso:  python3 carga_cpu.py --iteracoes 20000000
Saida: uma linha JSON em stdout.
"""
import argparse
import json
import os
import resource
import sys
import time

P = (1 << 61) - 1
BLOCO = 1_000_000


def esperado(n: int) -> int:
    """Valor de referencia pela formula fechada."""
    return ((n - 1) * n * (2 * n - 1) // 6) % P if n > 0 else 0


def trabalhar(n: int, limite_s: float) -> dict:
    inicio_wall = time.perf_counter()
    inicio_cpu = time.process_time()
    acc = 0
    feitos = 0
    status = "ok"
    while feitos < n:
        fim = min(feitos + BLOCO, n)
        for i in range(feitos, fim):
            acc = (acc + i * i) % P
        feitos = fim
        if time.perf_counter() - inicio_wall > limite_s:
            status = "timeout"
            break
    wall = time.perf_counter() - inicio_wall
    cpu = time.process_time() - inicio_cpu
    ref = esperado(n)
    correto = status == "ok" and acc == ref
    if status == "ok" and not correto:
        status = "checksum_invalido"
    return {
        "iteracoes": n,
        "iteracoes_feitas": feitos,
        "checksum": acc,
        "checksum_esperado": ref,
        "correto": correto,
        "status": status,
        "wall_s": round(wall, 6),
        "cpu_processo_s": round(cpu, 6),
        "trabalho_por_s": round(feitos / wall, 2) if wall > 0 else None,
        # ru_maxrss em Linux vem em KiB: pico de RSS deste processo
        "rss_pico_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "pid_no_namespace": os.getpid(),
        "python": sys.version.split()[0],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iteracoes", type=int,
                    default=int(os.environ.get("ITERACOES", "20000000")))
    ap.add_argument("--limite", type=float,
                    default=float(os.environ.get("LIMITE_SEGUNDOS", "60")))
    args = ap.parse_args()
    if args.iteracoes <= 0:
        print("iteracoes deve ser > 0", file=sys.stderr)
        return 2
    r = trabalhar(args.iteracoes, args.limite)
    print(json.dumps(r))
    return 0 if r["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
