"""Complemento de C3: threads x processos em tarefa CPU-bound (GIL) e em tarefa de espera (E/S simulada)."""
import argparse, time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from genresearch.common import RESULTS, append_csv, now


def cpu_task(n):
    s = 0
    for i in range(n):
        s += i * i % 7
    return s


def io_task(sec):
    time.sleep(sec)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=16); ap.add_argument("--iters", type=int, default=2_000_000)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--workers", nargs="+", type=int, default=[1, 2, 4])
    a = ap.parse_args()
    for rep in range(1, a.reps + 1):
        for kind, Ex in (("threads", ThreadPoolExecutor), ("processes", ProcessPoolExecutor)):
            for task, fn, arg in (("cpu", cpu_task, a.iters), ("io", io_task, 0.1)):
                for w in a.workers:
                    with Ex(w) as ex:
                        list(ex.map(fn, [1 if task == "cpu" else 0] * w))  # aquecimento
                        t = time.perf_counter()
                        list(ex.map(fn, [arg] * a.tasks))
                        wall = time.perf_counter() - t
                    append_csv(RESULTS / "c3b_gil.csv", {"rep": rep, "timestamp": now(), "kind": kind, "task": task,
                                                          "workers": w, "wall_s": wall, "tasks_per_s": a.tasks / wall})
                    print(f"rep{rep} {kind} {task} w={w}: {wall:.2f}s")


if __name__ == "__main__":
    main()
