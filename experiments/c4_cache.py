"""C4: cache compartilhado. Consultas repetidas x distintas, tamanho do cache e política (LRU/FIFO)."""
import argparse
from genresearch.common import RESULTS, append_csv, now, run_module, to_args


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/small"); ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--requests", type=int, default=400)
    a = ap.parse_args()
    for rep in range(1, a.reps + 1):
        for scen, pool in (("repetidas_20", 20), ("pool_200", 200), ("distintas", 0)):
            for cap in (0, 10, 100):
                for pol in (("lru",) if cap == 0 else ("lru", "fifo")):
                    kw = dict(data=a.data, workers=2, requests=a.requests, cache_cap=cap, cache_policy=pol,
                              query_pool=pool, seed=rep, tag=f"c4_{scen}_c{cap}_{pol}_r{rep}")
                    r = run_module("genresearch.server", to_args(**kw))
                    append_csv(RESULTS / "c4_cache.csv", {"experiment": "C4", "rep": rep, "timestamp": now(),
                                                          "scenario": scen, **r})
                    print(f"rep{rep} {scen} cap={cap} {pol}: hit={r['cache_hit_rate']:.2f} wall={r['wall_s']:.2f}s "
                          f"evict={r['cache_evictions']} dupcomp={r['computes'] - r['unique_computed']}")


if __name__ == "__main__":
    main()
