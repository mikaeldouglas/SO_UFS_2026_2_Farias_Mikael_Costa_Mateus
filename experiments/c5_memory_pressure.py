"""C5: pressão de memória. Aumenta corpus (datasets) e lote (batch de consultas pontuadas de uma vez).
Cada passo roda em subprocesso. Há TRAVAS DE SEGURANÇA: o passo é pulado se a memória prevista exceder
--max-mb ou 85% de MemAvailable (use --allow-swap só em VM/limite de cgroup descartável)."""
import argparse, json, time
import numpy as np
from genresearch.common import (ROOT, RESULTS, Sampler, append_csv, meminfo, now, proc_snapshot, run_module,
                                to_args, vmstat)

KEYS = ["status", "need_mb", "t_load", "t_compute", "peak_rss_mb", "min_avail_mb", "max_swap_mb",
        "d_minflt", "d_majflt", "d_pswpin", "d_pswpout", "d_read_mb"]


def child(a):
    m = json.load(open(ROOT / a.data / "manifest.json"))
    n, dim = m["n"], m["dim"]
    need = (n * dim * 4 + n * a.batch * 4) / 2**20
    avail = meminfo()["MemAvailable"] / 1024
    out = dict.fromkeys(KEYS, 0); out["need_mb"] = need
    if need > a.max_mb or (not a.allow_swap and need > 0.85 * avail):
        out["status"] = "guard_skipped"; print(json.dumps(out)); return
    smp = Sampler(0.05); smp.start()
    p0, v0, pc = proc_snapshot(), vmstat(), time.perf_counter
    out["status"] = "ok"
    try:
        t = pc(); vecs = np.fromfile(ROOT / a.data / "vectors.bin", dtype=np.float32).reshape(n, dim); out["t_load"] = pc() - t
        Q = np.random.default_rng(0).standard_normal((dim, a.batch)).astype(np.float32)
        t = pc(); S = vecs @ Q; float(S.max()); out["t_compute"] = pc() - t
    except MemoryError:
        out["status"] = "MemoryError"
    smp.stop(); p1, v1 = proc_snapshot(), vmstat()
    out.update(peak_rss_mb=smp.peak_rss, min_avail_mb=smp.min_avail, max_swap_mb=smp.max_swap,
               d_minflt=p1["minflt"] - p0["minflt"], d_majflt=p1["majflt"] - p0["majflt"],
               d_pswpin=v1["pswpin"] - v0["pswpin"], d_pswpout=v1["pswpout"] - v0["pswpout"],
               d_read_mb=p1["io_read_mb"] - p0["io_read_mb"])
    print(json.dumps(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", action="store_true"); ap.add_argument("--data", default="data/small")
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--datasets", nargs="+", default=["data/small"])
    ap.add_argument("--batches", nargs="+", type=int, default=[1, 16, 64, 256, 1024])
    ap.add_argument("--max-mb", type=float, default=4096); ap.add_argument("--allow-swap", action="store_true")
    ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    if a.child:
        return child(a)
    for rep in range(1, a.reps + 1):
        for ds in a.datasets:
            for b in a.batches:
                try:
                    r = run_module("experiments.c5_memory_pressure",
                                   to_args(child=True, data=ds, batch=b, max_mb=a.max_mb, allow_swap=a.allow_swap))
                except RuntimeError as e:  # ex.: OOM killer (rc -9)
                    r = dict.fromkeys(KEYS, 0); r["status"] = "killed_or_error"; print(str(e)[:200])
                append_csv(RESULTS / "c5_memory.csv", {"experiment": "C5", "rep": rep, "timestamp": now(),
                                                       "dataset": ds, "batch": b, **r})
                print(f"rep{rep} {ds} batch={b}: {r['status']} need={r['need_mb']:.0f}MB peak={r['peak_rss_mb']:.0f}MB "
                      f"t={r['t_compute']:.2f}s majflt={r['d_majflt']} swapout={r['d_pswpout']}")


if __name__ == "__main__":
    main()
