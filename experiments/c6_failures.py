"""C6: falhas controladas: arquivo ausente, índice indisponível, fila saturada, serviço externo falhando."""
import argparse
from genresearch.common import RESULTS, append_csv, now, run_module, to_args

COLS = ["status", "error", "requests", "enqueued", "completed", "failed", "dropped", "queue_full", "retries",
        "lost", "duplicates", "wall_s", "throughput_rps", "total_p95_ms", "queue_max"]
SAT = dict(queue_cap=2, producers=4, workers=1, gen_ms=40, max_retries=3)
SCEN = [
    ("arquivo_ausente", dict(data="data/nao_existe")),
    ("indice_fora_sem_retry", dict(index_fail_first=5, max_retries=0)),
    ("indice_fora_com_retry", dict(index_fail_first=5, max_retries=3)),
    ("fila_cheia_reject", dict(SAT, put_mode="reject")),
    ("fila_cheia_retry", dict(SAT, put_mode="retry")),
    ("fila_cheia_block", dict(SAT, put_mode="block")),
    ("servico_falha_sem_retry", dict(gen_fail_prob=0.2, max_retries=0)),
    ("servico_falha_com_retry", dict(gen_fail_prob=0.2, max_retries=3)),
    ("recuperacao_pos_arquivo", dict()),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/small"); ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--requests", type=int, default=200)
    a = ap.parse_args()
    for rep in range(1, a.reps + 1):
        for name, extra in SCEN:
            kw = dict(data=a.data, requests=a.requests, cache_cap=0, query_pool=0, seed=rep, tag=f"c6_{name}_r{rep}")
            kw.update(extra)
            r = run_module("genresearch.server", to_args(**kw))
            row = {"experiment": "C6", "rep": rep, "timestamp": now(), "scenario": name, **{c: r.get(c, "") for c in COLS}}
            append_csv(RESULTS / "c6_failures.csv", row)
            print(f"rep{rep} {name}: status={r['status']} done={r.get('completed', '-')} failed={r.get('failed', '-')} "
                  f"dropped={r.get('dropped', '-')} retries={r.get('retries', '-')}")


if __name__ == "__main__":
    main()
