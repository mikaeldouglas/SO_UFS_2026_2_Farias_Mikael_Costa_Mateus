"""GenResearch-Servidor: produtores -> fila limitada -> workers (cache, recuperação, geração simulada)."""
import argparse, json, queue, random, threading, time
from collections import Counter
from dataclasses import dataclass, asdict, fields
import numpy as np
from .cache import Cache
from .common import (ROOT, RESULTS, Sampler, embed, mem_snapshot, proc_snapshot, query_text, vmstat)
from .logger import Logger
from .store import Store


class ExternalServiceError(Exception):
    pass


class IndexUnavailable(Exception):
    pass


@dataclass
class Config:
    data: str = "data/small"
    mmap: bool = False            # False = leitura convencional (C1); True = mmap (C2)
    workers: int = 2
    producers: int = 2
    requests: int = 300
    queue_cap: int = 32
    cache_cap: int = 100          # 0 = sem cache
    cache_policy: str = "lru"     # lru | fifo
    query_pool: int = 50          # 0 = todas as consultas distintas
    top_k: int = 5
    max_ctx_bytes: int = 4000
    gen_mode: str = "sleep"       # sleep (E/S-like) | cpu (CPU-bound, sofre com GIL)
    gen_ms: float = 20.0
    cpu_iters: int = 200000
    gen_fail_prob: float = 0.0    # C6: falha de serviço externo
    max_retries: int = 2
    index_fail_first: int = 0     # C6: primeiras N recuperações falham
    put_mode: str = "block"       # block | retry | reject  (fila cheia)
    put_timeout: float = 0.05
    seed: int = 0
    tag: str = "run"
    nolog: bool = False


def make_qids(cfg):
    if cfg.query_pool <= 0:
        return list(range(1000, 1000 + cfg.requests))
    return np.random.default_rng(cfg.seed).integers(0, cfg.query_pool, cfg.requests).tolist()


def retrieve(store, qid, k, max_bytes):
    q = embed(query_text(qid), store.m["dim"])
    scores = np.asarray(store.vecs @ q)
    idx = np.argpartition(scores, -k)[-k:]
    idx = idx[np.argsort(-scores[idx])]
    texts = store.texts([int(i) for i in idx])
    ctx, size = [], 0
    for i in idx:
        t = texts[int(i)]
        if size + len(t) > max_bytes:
            break
        ctx.append(t); size += len(t)
    return size, len(ctx)


def generate(cfg, ctx_tokens, rng):
    if cfg.gen_fail_prob > 0 and rng.random() < cfg.gen_fail_prob:
        raise ExternalServiceError("servico de geracao indisponivel")
    factor = 1 + ctx_tokens / 1000
    if cfg.gen_mode == "sleep":
        time.sleep(cfg.gen_ms * factor / 1000)
    else:
        s = 0
        for i in range(int(cfg.cpu_iters * factor)):
            s += i * i % 7
    return f"resposta simulada ({ctx_tokens} tokens de contexto)"


def summ(arr, prefix):
    if len(arr) == 0:
        return {f"{prefix}_{s}_ms": float("nan") for s in ("mean", "median", "p95")}
    a = np.asarray(arr) * 1000
    return {f"{prefix}_mean_ms": float(a.mean()), f"{prefix}_median_ms": float(np.median(a)),
            f"{prefix}_p95_ms": float(np.percentile(a, 95))}


def run(cfg):
    pc = time.perf_counter
    logger = Logger(None if cfg.nolog else RESULTS / "logs" / f"{cfg.tag}.log")
    sampler = Sampler(); sampler.start()
    p0, v0 = proc_snapshot(), vmstat()
    t = pc()
    store = Store(ROOT / cfg.data, "mmap" if cfg.mmap else "read")
    load_s = pc() - t
    logger.log("MAIN", "start", workers=cfg.workers, producers=cfg.producers, mmap=cfg.mmap)
    cache = Cache(cfg.cache_cap, cfg.cache_policy, safe=True)
    q = queue.Queue(maxsize=cfg.queue_cap)
    qids = make_qids(cfg)
    cnt, computed, cl = Counter(), Counter(), threading.Lock()
    idx_left = [cfg.index_fail_first]
    recs, qsizes, busy = [], [], [0.0] * cfg.workers

    def inc(k, n=1):
        with cl:
            cnt[k] += n

    def handle(req, who, rng):
        r = {"hit": False, "t_ret": 0.0, "t_gen": 0.0}
        if cache.get(req["qid"]) is not None:
            logger.log(who, "cache_hit", req=req["id"])
            r["hit"] = True
            return r
        logger.log(who, "cache_miss", req=req["id"])
        attempt = 0
        while True:
            try:
                t0 = pc()
                with cl:
                    if idx_left[0] > 0:
                        idx_left[0] -= 1
                        raise IndexUnavailable("indice indisponivel")
                ctx_bytes, nch = retrieve(store, req["qid"], cfg.top_k, cfg.max_ctx_bytes)
                r["t_ret"] = pc() - t0
                logger.log(who, "retrieval", req=req["id"], chunks=nch, bytes=ctx_bytes)
                break
            except IndexUnavailable:
                inc("retries"); attempt += 1
                logger.log(who, "retry_index", req=req["id"], attempt=attempt)
                if attempt > cfg.max_retries:
                    raise
                time.sleep(0.01 * 2 ** attempt)
        attempt = 0
        while True:
            try:
                t0 = pc()
                ans = generate(cfg, ctx_bytes // 4, rng)
                r["t_gen"] = pc() - t0
                logger.log(who, "generation", req=req["id"], ms=round(r["t_gen"] * 1000, 1))
                break
            except ExternalServiceError:
                inc("retries"); attempt += 1
                logger.log(who, "retry_generation", req=req["id"], attempt=attempt)
                if attempt > cfg.max_retries:
                    raise
                time.sleep(0.01 * 2 ** attempt)
        cache.put(req["qid"], ans, cost=r["t_ret"] + r["t_gen"])
        with cl:
            computed[req["qid"]] += 1
        return r

    def worker(wid):
        who, rng = f"W{wid}", random.Random(cfg.seed * 100 + wid)
        while True:
            req = q.get()
            if req is None:
                break
            t_deq = pc()
            try:
                r = handle(req, who, rng); r["ok"] = True
            except (IndexUnavailable, ExternalServiceError) as e:
                r = {"hit": False, "t_ret": 0.0, "t_gen": 0.0, "ok": False}
                inc("failed"); logger.log(who, "failure", req=req["id"], err=type(e).__name__)
            t_end = pc()
            busy[wid] += t_end - t_deq
            r.update(id=req["id"], wait=t_deq - req["t_enq"], total=t_end - req["t_enq"])
            recs.append(r)

    def producer(pid, items):
        for rid, qid in items:
            req = {"id": rid, "qid": qid, "t_enq": pc()}
            tries = 0
            while True:
                try:
                    if cfg.put_mode == "block":
                        q.put(req)
                    elif cfg.put_mode == "reject":
                        q.put_nowait(req)
                    else:
                        q.put(req, timeout=cfg.put_timeout)
                    inc("enqueued"); qsizes.append(q.qsize())
                    break
                except queue.Full:
                    inc("queue_full"); tries += 1
                    logger.log(f"P{pid}", "queue_full", req=rid, attempt=tries)
                    if cfg.put_mode == "reject" or tries > cfg.max_retries:
                        inc("dropped"); logger.log(f"P{pid}", "drop", req=rid)
                        break

    items = list(enumerate(qids))
    t_start = pc()
    ws = [threading.Thread(target=worker, args=(i,)) for i in range(cfg.workers)]
    ps = [threading.Thread(target=producer, args=(i, items[i::cfg.producers])) for i in range(cfg.producers)]
    for th in ws + ps:
        th.start()
    for th in ps:
        th.join()
    for _ in ws:
        q.put(None)
    for th in ws:
        th.join()
    wall = pc() - t_start
    logger.log("MAIN", "shutdown", processed=len(recs)); logger.close()
    sampler.stop()
    p1, v1 = proc_snapshot(), vmstat()
    ok = [r for r in recs if r["ok"]]
    ids = [r["id"] for r in recs]
    miss = [r for r in ok if not r["hit"]]
    cs = cache.stats()
    res = asdict(cfg)
    res.update({
        "n_chunks": store.m["n"], "ingest_s": store.m["ingest_s"], "vectors_mb": store.m["vectors_bytes"] / 2**20,
        "sqlite_mb": store.m["sqlite_bytes"] / 2**20, "load_s": load_s, "wall_s": wall,
        "throughput_rps": len(recs) / wall if wall else 0.0,
        "enqueued": cnt["enqueued"], "completed": len(ok), "failed": cnt["failed"], "dropped": cnt["dropped"],
        "queue_full": cnt["queue_full"], "retries": cnt["retries"],
        "duplicates": len(ids) - len(set(ids)), "lost": cnt["enqueued"] - len(recs),
        "utilization": sum(busy) / (cfg.workers * wall) if wall else 0.0,
        "queue_mean": float(np.mean(qsizes)) if qsizes else 0.0, "queue_max": max(qsizes) if qsizes else 0,
        "computes": sum(computed.values()), "unique_computed": len(computed),
        "peak_rss_mb": sampler.peak_rss, "min_mem_available_mb": sampler.min_avail,
        "max_swap_used_mb": sampler.max_swap, "vsz_mb": p1["vsz_mb"],
        "d_minflt": p1["minflt"] - p0["minflt"], "d_majflt": p1["majflt"] - p0["majflt"],
        "d_read_mb": p1["io_read_mb"] - p0["io_read_mb"],
        "d_pswpin": v1["pswpin"] - v0["pswpin"], "d_pswpout": v1["pswpout"] - v0["pswpout"],
    })
    res.update(summ([r["total"] for r in ok], "total")); res.update(summ([r["wait"] for r in recs], "wait"))
    res.update(summ([r["t_ret"] for r in miss], "retrieval")); res.update(summ([r["t_gen"] for r in miss], "gen"))
    res.update(cs)
    return res


def main():
    ap = argparse.ArgumentParser()
    for f in fields(Config):
        flag = "--" + f.name.replace("_", "-")
        if isinstance(f.default, bool):
            ap.add_argument(flag, action="store_true")
        else:
            ap.add_argument(flag, type=type(f.default), default=f.default)
    cfg = Config(**vars(ap.parse_args()))
    try:
        res = run(cfg); res["status"] = "ok"
    except FileNotFoundError as e:  # C6: arquivo ausente tratado, sem derrubar o processo
        lg = Logger(RESULTS / "logs" / f"{cfg.tag}.log")
        lg.log("MAIN", "error", err="FileNotFoundError", detail=str(e).replace(" ", "_")); lg.close()
        res = {**asdict(cfg), "status": "error_handled", "error": "FileNotFoundError"}
    print(json.dumps(res, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    main()
