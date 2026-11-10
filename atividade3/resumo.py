#!/usr/bin/env python3
"""Consolida uma sessao de run_experimentos.sh.

Uso: python3 resumo.py [registros/sessao_AAAAMMDD_HHMMSS]
     (sem argumento usa a sessao_* mais recente)

Gera dentro da pasta da sessao:
  resultados.csv          uma linha por execucao, inclusive as com erro
  resumo_condicoes.csv    mediana, minimo, maximo e amplitude por condicao
  tabela.md               as duas tabelas em Markdown para o relatorio
  grafico_c1_c2.png       trabalho/s e tempos por condicao (precisa matplotlib)
"""
import csv
import glob
import json
import os
import statistics as st
import sys

ESPERADO = {  # o que o kernel deve mostrar para cada condicao
    "C1": {"cpu.max": "50000 100000"},
    "C2": {"cpu.max": "100000 100000"},
    "comum": {"memory.max": str(256 * 1024 * 1024), "memory.swap.max": "0",
              "pids.max": "64"},
}
CORES = {"C1": "#2a78d6", "C2": "#eb6834"}
ROTULO = {"C1": "C1 (0,5 CPU)", "C2": "C2 (1,0 CPU)"}


def ler_meta(caminho):
    d = {}
    with open(caminho) as f:
        for linha in f:
            if "=" in linha:
                k, v = linha.rstrip("\n").split("=", 1)
                d[k] = v
    return d


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def linha_execucao(meta_path):
    base = meta_path[:-5]
    m = ler_meta(meta_path)
    r = {"execucao": os.path.basename(base), "ordem": int(m.get("ordem", 0)),
         "condicao": m.get("condicao"), "repeticao": m.get("repeticao"),
         "cpus_pedido": m.get("cpus_pedido"), "iteracoes": m.get("iteracoes"),
         "codigo_saida": m.get("codigo_saida"), "wall_host_s": m.get("wall_host_s"),
         "loadavg_antes": m.get("loadavg_antes"), "inicio": m.get("inicio")}
    try:
        with open(base + ".json") as f:
            d = json.loads(f.read().strip().splitlines()[-1])
    except (OSError, ValueError, IndexError):
        r.update(status="sem_json_valido", valida=False, observacao="ver .stderr")
        return r

    c, cfg = d.get("carga", {}), d.get("config_cgroup", {})
    dl, dep = d.get("delta_cpu_stat", {}), d.get("depois", {})
    wall = num(c.get("wall_s"))
    usage = dl.get("usage_usec")
    r.update({
        "status": c.get("status"), "correto": c.get("correto"),
        "checksum": c.get("checksum"), "iteracoes_feitas": c.get("iteracoes_feitas"),
        "wall_s": wall, "cpu_processo_s": c.get("cpu_processo_s"),
        "trabalho_por_s": c.get("trabalho_por_s"),
        "cpu.max": cfg.get("cpu.max"), "memory.max": cfg.get("memory.max"),
        "memory.swap.max": cfg.get("memory.swap.max"), "pids.max": cfg.get("pids.max"),
        "delta_usage_usec": usage, "delta_nr_periods": dl.get("nr_periods"),
        "delta_nr_throttled": dl.get("nr_throttled"),
        "delta_throttled_usec": dl.get("throttled_usec"),
        # CPUs efetivas = tempo de CPU do grupo / tempo de parede
        "cpus_efetivas": round(usage / 1e6 / wall, 3) if usage and wall else None,
        "rss_pico_processo_kib": c.get("rss_pico_kib"),
        "memory.current_depois_bytes": dep.get("memory.current"),
        "memory.peak_bytes": dep.get("memory.peak"),
        "pids.peak": dep.get("pids.peak"),
    })
    esp = dict(ESPERADO["comum"], **ESPERADO.get(r["condicao"], {}))
    falhas = [k for k, v in esp.items() if str(r.get(k)) != v]
    r["limites_confirmados"] = not falhas
    r["valida"] = (r["codigo_saida"] == "0" and r["status"] == "ok"
                   and r["correto"] is True)
    obs = []
    if falhas:
        obs.append("limite diferente do esperado: " + ", ".join(
            f"{k}={r.get(k)!r}" for k in falhas))
    if not r["valida"]:
        obs.append("execucao invalida (status/codigo/checksum)")
    r["observacao"] = "; ".join(obs)
    return r


def resumir(linhas):
    out = []
    for cond in ("C1", "C2"):
        v = [l for l in linhas if l["condicao"] == cond and l.get("valida")]
        if not v:
            out.append({"condicao": cond, "n_validas": 0})
            continue
        tps = [l["trabalho_por_s"] for l in v]
        wall = [l["wall_s"] for l in v]
        med = st.median(tps)
        out.append({
            "condicao": cond, "n_validas": len(v),
            "n_total": sum(1 for l in linhas if l["condicao"] == cond),
            "trabalho_por_s_mediana": round(med, 1),
            "trabalho_por_s_min": round(min(tps), 1),
            "trabalho_por_s_max": round(max(tps), 1),
            "amplitude_relativa_pct": round(100 * (max(tps) - min(tps)) / med, 2),
            "wall_s_mediana": round(st.median(wall), 3),
            "cpu_processo_s_mediana": round(st.median(l["cpu_processo_s"] for l in v), 3),
            "cpus_efetivas_mediana": _med(v, "cpus_efetivas"),
            "nr_throttled_mediana": _med(v, "delta_nr_throttled"),
            "throttled_s_mediana": (round(_med(v, "delta_throttled_usec") / 1e6, 3)
                                    if _med(v, "delta_throttled_usec") is not None else None),
            "memory_peak_mib_max": _max_mib(v, "memory.peak_bytes"),
            "rss_pico_mib_max": (round(max(l["rss_pico_processo_kib"] for l in v) / 1024, 1)),
        })
    return out


def _med(v, k):
    xs = [l[k] for l in v if isinstance(l.get(k), (int, float))]
    return round(st.median(xs), 3) if xs else None


def _max_mib(v, k):
    xs = [int(l[k]) for l in v if str(l.get(k, "")).isdigit()]
    return round(max(xs) / 2**20, 1) if xs else None


def md_tabela(linhas, colunas):
    s = "| " + " | ".join(colunas) + " |\n|" + "---|" * len(colunas) + "\n"
    for l in linhas:
        s += "| " + " | ".join("" if l.get(c) is None else str(l.get(c)) for c in colunas) + " |\n"
    return s


def grafico(linhas, resumo, destino, iteracoes):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib ausente: sudo apt-get install -y python3-matplotlib (grafico nao gerado)")
        return False
    validas = [l for l in linhas if l.get("valida")]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150)
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e4e3dd", linewidth=0.8)
        ax.set_axisbelow(True)

    # Painel 1: trabalho por segundo, cada repeticao como ponto + mediana
    for i, cond in enumerate(("C1", "C2")):
        ys = [l["trabalho_por_s"] / 1e6 for l in validas if l["condicao"] == cond]
        if not ys:
            continue
        xs = [i + d for d in (-0.08, 0, 0.08)][:len(ys)]
        a1.scatter(xs, ys, s=46, color=CORES[cond], edgecolor="white",
                   linewidth=1.5, zorder=3)
        m = st.median(ys)
        a1.hlines(m, i - 0.25, i + 0.25, color=CORES[cond], linewidth=2, zorder=2)
        a1.annotate(f"mediana {m:.2f}\nn = {len(ys)}", (i + 0.28, m),
                    va="center", fontsize=8, color="#3d3d3a")
    a1.set_xticks([0, 1], [ROTULO["C1"], ROTULO["C2"]])
    a1.set_xlim(-0.5, 1.9)
    topo = max(l["trabalho_por_s"] for l in validas) / 1e6 if validas else 1
    a1.set_ylim(0, topo * 1.15)
    a1.set_ylabel("Trabalho concluido (milhoes de iteracoes/s)")
    a1.set_title("Vazao por repeticao", fontsize=10, loc="left")

    # Painel 2: tempo de parede x tempo de CPU (medianas, mesma unidade: s)
    largura = 0.34
    for i, cond in enumerate(("C1", "C2")):
        r = next((x for x in resumo if x["condicao"] == cond and x.get("n_validas")), None)
        if not r:
            continue
        a2.bar(i - largura / 2 - 0.01, r["wall_s_mediana"], largura,
               color=CORES[cond], label=None)
        a2.bar(i + largura / 2 + 0.01, r["cpu_processo_s_mediana"], largura,
               color=CORES[cond], alpha=0.45, hatch="//", edgecolor="white")
        a2.text(i - largura / 2 - 0.01, r["wall_s_mediana"], f"{r['wall_s_mediana']:.2f}",
                ha="center", va="bottom", fontsize=8)
        a2.text(i + largura / 2 + 0.01, r["cpu_processo_s_mediana"],
                f"{r['cpu_processo_s_mediana']:.2f}", ha="center", va="bottom", fontsize=8)
    a2.set_xticks([0, 1], [ROTULO["C1"], ROTULO["C2"]])
    a2.set_ylabel("Segundos (mediana de n repeticoes)")
    a2.set_title("Barra cheia: tempo de parede   Hachurada: tempo de CPU",
                 fontsize=9, loc="left")
    fig.suptitle(f"C1 x C2, mesmo trabalho (N = {iteracoes} iteracoes), "
                 "256 MiB, pids-limit 64", fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(destino)
    plt.close(fig)
    return True


def main():
    if len(sys.argv) > 1:
        sessao = sys.argv[1].rstrip("/")
    else:
        cand = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "registros", "sessao_*")))
        if not cand:
            sys.exit("Nenhuma registros/sessao_* encontrada.")
        sessao = cand[-1]
    metas = sorted(glob.glob(os.path.join(sessao, "*.meta")))
    if not metas:
        sys.exit(f"Nenhum .meta em {sessao}")
    linhas = sorted((linha_execucao(m) for m in metas), key=lambda l: l["ordem"])
    resumo = resumir(linhas)

    cols = list(dict.fromkeys(k for l in linhas for k in l))
    with open(os.path.join(sessao, "resultados.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)
    rcols = list(dict.fromkeys(k for r in resumo for k in r))
    with open(os.path.join(sessao, "resumo_condicoes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rcols); w.writeheader(); w.writerows(resumo)

    c1 = next((r for r in resumo if r["condicao"] == "C1" and r.get("n_validas")), None)
    c2 = next((r for r in resumo if r["condicao"] == "C2" and r.get("n_validas")), None)
    razao = (round(c2["trabalho_por_s_mediana"] / c1["trabalho_por_s_mediana"], 3)
             if c1 and c2 else None)

    exec_cols = ["ordem", "condicao", "repeticao", "status", "correto", "wall_s",
                 "cpu_processo_s", "trabalho_por_s", "cpus_efetivas", "cpu.max",
                 "delta_nr_throttled", "delta_throttled_usec", "memory.peak_bytes",
                 "rss_pico_processo_kib", "limites_confirmados", "valida"]
    md = "## Execucoes\n\n" + md_tabela(linhas, exec_cols)
    md += "\n## Resumo por condicao\n\n" + md_tabela(resumo, rcols)
    md += f"\nRazao das medianas de trabalho/s (C2/C1): {razao}\n"
    with open(os.path.join(sessao, "tabela.md"), "w") as f:
        f.write(md)
    print(md)

    invalidas = [l["execucao"] for l in linhas if not l.get("valida")]
    if invalidas:
        print("ATENCAO: execucoes invalidas mantidas nos registros:", ", ".join(invalidas))
    sem_conf = [l["execucao"] for l in linhas if l.get("limites_confirmados") is False]
    if sem_conf:
        print("ATENCAO: limites nao confirmados em:", ", ".join(sem_conf))
    n_iter = linhas[0].get("iteracoes")
    if grafico(linhas, resumo, os.path.join(sessao, "grafico_c1_c2.png"), n_iter):
        print("Grafico:", os.path.join(sessao, "grafico_c1_c2.png"))


if __name__ == "__main__":
    main()
