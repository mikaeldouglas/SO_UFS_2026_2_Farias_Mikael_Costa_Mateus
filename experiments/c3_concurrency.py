"""C3: produtores/consumidores com fila. Varia workers (1,2,4), capacidade da fila e tipo de carga (sleep vs cpu)."""
import argparse
from genresearch.common import RESULTS, append_csv, now, run_module, to_args


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/small"); ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--requests", type=int, default=300)
    ap.add_argument("--mmap", action="store_true")
    ap.add_argument("--workers", nargs="+", type=int, default=[1, 2, 4])
    a = ap.parse_args()
    for rep in range(1, a.reps + 1):
        for gm in ("sleep", "cpu"):
            for qc in (8, 128):
                for w in a.workers:
                    kw = dict(data=a.data, workers=w, producers=2, queue_cap=qc, gen_mode=gm, requests=a.requests,
                              cache_cap=0, query_pool=0, mmap=a.mmap, seed=rep, tag=f"c3_{gm}_q{qc}_w{w}_r{rep}")
                    r = run_module("genresearch.server", to_args(**kw))
                    append_csv(RESULTS / "c3_concurrency.csv", {"experiment": "C3", "rep": rep, "timestamp": now(), **r})
                    print(f"rep{rep} {gm} q={qc} w={w}: {r['throughput_rps']:.1f} req/s "
                          f"p95={r['total_p95_ms']:.0f}ms util={r['utilization']:.2f} qmax={r['queue_max']}")


if __name__ == "__main__":
    main()
