"""Gera tabelas-resumo (média, mediana, p95) e gráficos PNG em results/figures a partir dos CSVs brutos."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from genresearch.common import RESULTS

FIG = RESULTS / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def p95(s):
    return s.quantile(0.95)


def load(name):
    p = RESULTS / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


def summarize(df, by, cols, name):
    g = df.groupby(by)[cols].agg(["mean", "median", p95])
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    g.round(4).to_csv(RESULTS / f"summary_{name}.csv")


def save(name):
    plt.tight_layout(); plt.savefig(FIG / name, dpi=150, bbox_inches="tight"); plt.close()


def bars(df, index, columns, value, title, ylabel, fname, logy=False, labels=False):
    pv = df.pivot_table(index=index, columns=columns, values=value, aggfunc="mean")
    ax = pv.plot.bar(figsize=(10, 4.5), logy=logy)
    ax.set_title(title); ax.set_ylabel(ylabel); plt.xticks(rotation=35, ha="right")
    ax.legend(title=pv.columns.name, bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)  # legenda fora das barras
    if labels:  # mostra os valores (inclusive 0, que a escala log não desenha)
        for c in ax.containers:
            ax.bar_label(c, fmt="%.0f", fontsize=6, rotation=90, padding=2)
    save(fname)


def c1c2():
    df = load("c1_c2")
    if df is None:
        return
    df["cfg"] = df["mode"] + "/" + df["pattern"] + "/" + df["cold"].map({True: "fria", False: "quente"})
    summarize(df, ["dataset", "cfg"], ["t_total", "rss_mb", "vsz_mb", "d_minflt", "d_majflt", "d_read_mb"], "c1_c2")
    for m, yl, ln in (("t_total", "Tempo total (s)", True), ("rss_mb", "RSS (MB)", False),
                      ("vsz_mb", "VSZ (MB)", False), ("d_majflt", "Faltas de página maiores", True),
                      ("d_minflt", "Faltas de página menores", True)):
        bars(df, "cfg", "dataset", m, f"C1 (read) x C2 (mmap): {yl}", yl, f"c1c2_{m}.png", logy=ln, labels=m.startswith("d_"))


def c3():
    df = load("c3_concurrency")
    if df is None:
        return
    summarize(df, ["gen_mode", "queue_cap", "workers"],
              ["throughput_rps", "total_p95_ms", "wait_mean_ms", "utilization", "queue_mean", "queue_max"], "c3")
    for m, yl in (("throughput_rps", "Vazão (req/s)"), ("total_p95_ms", "Latência p95 (ms)"), ("queue_max", "Fila: tamanho máximo")):
        plt.figure(figsize=(7, 4.5))
        for (gm, qc), g in df.groupby(["gen_mode", "queue_cap"]):
            s = g.groupby("workers")[m].agg(["mean", "std"]).fillna(0)
            plt.errorbar(s.index, s["mean"], yerr=s["std"], marker="o" if gm == "sleep" else "s",
                         ls="-" if qc == 8 else "--", capsize=3, label=f"{gm}, fila={qc}")
        plt.xticks(sorted(df["workers"].unique())); plt.xlabel("Workers"); plt.ylabel(yl); plt.title(f"C3: {yl} x workers"); plt.legend()
        save(f"c3_{m}.png")


def c3b():
    df = load("c3b_gil")
    if df is None:
        return
    summarize(df, ["kind", "task", "workers"], ["wall_s", "tasks_per_s"], "c3b")
    df["cfg"] = df["kind"] + "/" + df["task"]
    bars(df, "workers", "cfg", "tasks_per_s", "Threads x processos (GIL)", "Tarefas por segundo", "c3b_gil.png")


def c4():
    df = load("c4_cache")
    if df is None:
        return
    df["cfg"] = "cap=" + df["cache_cap"].astype(str) + "/" + df["cache_policy"]
    df["dup_computes"] = df["computes"] - df["unique_computed"]
    summarize(df, ["scenario", "cfg"], ["cache_hit_rate", "wall_s", "cache_evictions", "cache_saved_s", "dup_computes"], "c4")
    bars(df, "scenario", "cfg", "cache_hit_rate", "C4: taxa de acerto do cache", "Taxa de acerto", "c4_hit_rate.png")
    bars(df, "scenario", "cfg", "wall_s", "C4: tempo total", "Tempo (s)", "c4_wall.png")


def c5():
    df = load("c5_memory")
    if df is None:
        return
    ok = df[df["status"] == "ok"].copy()
    if "perfil" not in ok:  # perfil da VM inferido: no perfil restrito (4 GB) MemAvailable cai a poucas dezenas de MB
        ok["perfil"] = ok["min_avail_mb"].apply(lambda v: "restrito 4GB" if v < 1000 else "normal 16GB")
    cols = ["peak_rss_mb", "t_compute", "d_majflt", "d_pswpout", "max_swap_mb"]
    summarize(ok, ["dataset", "perfil", "batch"], cols, "c5_por_perfil")
    for m, yl in (("peak_rss_mb", "RSS de pico (MB)"), ("t_compute", "Tempo de cálculo (s)"),
                  ("d_majflt", "Faltas maiores"), ("d_pswpout", "Páginas enviadas ao swap"),
                  ("max_swap_mb", "Swap usado, pico (MB)")):
        plt.figure(figsize=(8, 4.8))
        for (ds, pf), g in ok.groupby(["dataset", "perfil"]):
            s_ = g.groupby("batch")[m].mean()
            plt.plot(s_.index, s_.values, marker="o", ls="--" if pf.startswith("restrito") else "-",
                     label=f"{ds.split('/')[-1]} ({pf})")
        plt.xscale("log")
        plt.yscale("log" if m == "t_compute" else "symlog", **({} if m == "t_compute" else {"linthresh": 1}))
        plt.xlabel("Lote (consultas por vez)"); plt.ylabel(yl); plt.title(f"C5: {yl} (por perfil de memória)")
        plt.legend(fontsize=8); save(f"c5_{m}.png")


def c6():
    df = load("c6_failures")
    if df is None:
        return
    for c in ("completed", "failed", "dropped", "retries"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    summarize(df, "scenario", ["completed", "failed", "dropped", "retries", "wall_s"], "c6")
    pv = df.groupby("scenario")[["completed", "failed", "dropped"]].mean()
    pv.plot.bar(stacked=True, figsize=(9, 4.5), title="C6: resultado por cenário de falha")
    plt.xticks(rotation=35, ha="right"); save("c6_failures.png")


def dsync():
    df = load("d_cache_race")
    if df is not None:
        df["cfg"] = df["safe"].map({True: "com lock", False: "sem lock"}) + "/gap=" + df["gap"].astype(str)
        summarize(df, "cfg", ["lost_counter_updates", "max_len", "wall_s"], "d_cache_race")
        ax = df.groupby("cfg")["lost_counter_updates"].mean().plot.bar(figsize=(7, 4), title="Parte D: atualizações perdidas (cache)")
        ax.set_ylabel("Contagens perdidas"); plt.xticks(rotation=25, ha="right"); save("d_cache_lost.png")
        ax = df.groupby("cfg")["wall_s"].mean().plot.bar(figsize=(7, 4), logy=True, title="Parte D: custo do lock (tempo)")
        ax.set_ylabel("Tempo (s)"); plt.xticks(rotation=25, ha="right"); save("d_cache_cost.png")
    df = load("d_log_race")
    if df is not None:
        df["cfg"] = df["safe"].map({True: "com lock", False: "sem lock"})
        summarize(df, "cfg", ["corrupted_lines", "wall_s"], "d_log_race")
        df.groupby("cfg")["corrupted_lines"].mean().plot.bar(figsize=(5, 4), title="Parte D: linhas de log corrompidas")
        save("d_log_corrupted.png")
    df = load("d_buffer")
    if df is not None:
        df["cfg"] = df["safe"].map({True: "com mutex", False: "sem mutex"})
        summarize(df, "cfg", ["lost", "duplicated", "wall_s"], "d_buffer")
        df.groupby("cfg")[["lost", "duplicated"]].mean().plot.bar(figsize=(6, 4), title="Parte D: buffer limitado, itens perdidos/duplicados")
        save("d_buffer.png")


if __name__ == "__main__":
    for f in (c1c2, c3, c3b, c4, c5, c6, dsync):
        f()
    print("figuras em", FIG)
