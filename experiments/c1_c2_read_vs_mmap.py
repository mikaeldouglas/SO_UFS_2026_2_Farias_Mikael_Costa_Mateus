"""C1 (read convencional) vs C2 (mmap): sequencial e aleatório, leitura fria e quente.
Cada medição roda em subprocesso novo (RSS/faltas de página limpos). 'Fria' = fadvise(DONTNEED)."""
import argparse, json, mmap, os, time
from pathlib import Path
import numpy as np
from genresearch.common import (ROOT, RESULTS, append_csv, fadvise_dontneed, mem_snapshot, now,
                                proc_snapshot, run_module, to_args, vmstat)

B = 65536


def scan(arr, q):
    return max(float((arr[i:i + B] @ q).max()) for i in range(0, len(arr), B))


def child(a):
    d = ROOT / a.data
    m = json.load(open(d / "manifest.json"))
    n, dim = m["n"], m["dim"]
    path, rb = d / "vectors.bin", dim * 4
    if a.cold:
        os.sync(); fadvise_dontneed(path)
    q = np.random.default_rng(1).standard_normal(dim).astype(np.float32)
    idx = np.random.default_rng(2).integers(0, n, a.rand_reads).tolist()
    p0, v0, m0, pc = proc_snapshot(), vmstat(), mem_snapshot(), time.perf_counter
    t0, t_load, best = pc(), 0.0, 0.0
    if a.mode == "read":
        f = open(path, "rb", buffering=0); t_open = pc() - t0
        if a.pattern == "seq":
            t1 = pc(); data = f.read(); t_load = pc() - t1
            arr = np.frombuffer(data, dtype=np.float32).reshape(n, dim)
            t2 = pc(); best = scan(arr, q); t_scan = pc() - t2
        else:
            t2 = pc()
            for i in idx:
                row = np.frombuffer(os.pread(f.fileno(), rb, i * rb), dtype=np.float32)
                best = max(best, float(row @ q))
            t_scan = pc() - t2
    else:
        f = open(path, "rb"); mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        arr = np.frombuffer(mm, dtype=np.float32).reshape(n, dim); t_open = pc() - t0
        t2 = pc()
        if a.pattern == "seq":
            best = scan(arr, q)
        else:
            for i in idx:
                best = max(best, float(arr[i] @ q))
        t_scan = pc() - t2
    t_total = pc() - t0
    p1, v1, m1 = proc_snapshot(), vmstat(), mem_snapshot()
    print(json.dumps({
        "file_mb": path.stat().st_size / 2**20, "t_open": t_open, "t_load": t_load, "t_scan": t_scan,
        "t_total": t_total, "rss_mb": p1["rss_mb"], "vsz_mb": p1["vsz_mb"], "maxrss_mb": p1["maxrss_mb"],
        "d_minflt": p1["minflt"] - p0["minflt"], "d_majflt": p1["majflt"] - p0["majflt"],
        "d_read_mb": p1["io_read_mb"] - p0["io_read_mb"], "d_pgmajfault_sys": v1["pgmajfault"] - v0["pgmajfault"],
        "d_cached_mb": m1["Cached_MB"] - m0["Cached_MB"], "memavail_before_mb": m0["MemAvailable_MB"],
        "memavail_after_mb": m1["MemAvailable_MB"], "checksum": best}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--mode", default="read"); ap.add_argument("--pattern", default="seq")
    ap.add_argument("--cold", action="store_true"); ap.add_argument("--data", default="data/small")
    ap.add_argument("--rand-reads", type=int, default=20000)
    ap.add_argument("--datasets", nargs="+", default=["data/small"]); ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    if a.child:
        return child(a)
    for rep in range(1, a.reps + 1):
        for ds in a.datasets:
            for mode in ("read", "mmap"):
                for pat in ("seq", "rand"):
                    for cold in (True, False):  # fria primeiro; a quente reaproveita o cache de páginas
                        r = run_module("experiments.c1_c2_read_vs_mmap", to_args(
                            child=True, mode=mode, pattern=pat, cold=cold, data=ds, rand_reads=a.rand_reads))
                        row = {"experiment": "C1" if mode == "read" else "C2", "rep": rep, "timestamp": now(),
                               "dataset": ds, "mode": mode, "pattern": pat, "cold": cold, **r}
                        append_csv(RESULTS / "c1_c2.csv", row)
                        print(f"rep{rep} {ds} {mode}/{pat}/{'fria' if cold else 'quente'} "
                              f"total={r['t_total']:.3f}s rss={r['rss_mb']:.0f}MB majflt={r['d_majflt']}")


if __name__ == "__main__":
    main()
