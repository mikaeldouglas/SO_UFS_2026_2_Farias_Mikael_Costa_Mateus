"""Parte D: sincronização. (1) corrida no cache  (2) log intercalado  (3) buffer limitado empty/full/mutex
(4) deadlock isolado com timeout e recuperação. Cada teste roda sem proteção (falha) e com proteção (correção)."""
import argparse, contextlib, os, random, re, threading, time
from genresearch.cache import Cache
from genresearch.common import RESULTS, append_csv, now
from genresearch.logger import Logger


def cache_race(safe, gap, threads=8, ops=4000, keys=200, cap=50):
    cache, counts, errs = Cache(cap, "lru", safe=safe, race_gap=gap), [], []

    def work(seed):
        r, n = random.Random(seed), 0
        try:
            for _ in range(ops):
                k = r.randrange(keys)
                if cache.get(k) is None:
                    cache.put(k, k, 0.0)
                n += 1
        except Exception as e:  # sem lock, o dict pode ser corrompido -> exceção
            errs.append(repr(e))
        counts.append(n)
    ths = [threading.Thread(target=work, args=(i,)) for i in range(threads)]
    t = time.perf_counter()
    [x.start() for x in ths]; [x.join() for x in ths]
    wall = time.perf_counter() - t
    total = sum(counts)
    return {"safe": safe, "gap": gap, "threads": threads, "gets_done": total, "hits_plus_misses": cache.hits + cache.misses,
            "lost_counter_updates": total - (cache.hits + cache.misses), "max_len": cache.max_len, "cap": cap,
            "overflow": cache.max_len > cap, "internal_errors": cache.errors, "thread_exceptions": len(errs), "wall_s": wall}


def log_race(safe, threads=8, lines=2000):
    path = RESULTS / "logs" / f"d_log_{'safe' if safe else 'unsafe'}.log"
    lg = Logger(path, safe=safe, gap=True)
    ths = [threading.Thread(target=lambda t=t: [lg.log(f"T{t}", "EVT", req=i) for i in range(lines)]) for t in range(threads)]
    t0 = time.perf_counter(); [x.start() for x in ths]; [x.join() for x in ths]; lg.close()
    ok = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+ T\d+ EVT req=\d+$")
    L = open(path).read().split("\n")[:-1]
    bad = sum(1 for l in L if not ok.match(l))
    return {"safe": safe, "expected_lines": threads * lines, "actual_lines": len(L), "corrupted_lines": bad,
            "wall_s": time.perf_counter() - t0}


class BoundedBuffer:
    """Buffer circular com semáforos empty/full e mutex (problema produtor-consumidor)."""
    def __init__(self, cap, safe=True):
        self.buf, self.cap, self.i, self.o = [None] * cap, cap, 0, 0
        self.empty, self.full = threading.Semaphore(cap), threading.Semaphore(0)
        self.mutex = threading.Lock() if safe else contextlib.nullcontext()

    def put(self, x):
        self.empty.acquire()
        with self.mutex:
            i = self.i; self.buf[i] = x; time.sleep(0); self.i = (i + 1) % self.cap
        self.full.release()

    def get(self, timeout=0.5):
        if not self.full.acquire(timeout=timeout):
            return "TIMEOUT"
        with self.mutex:
            o = self.o; x = self.buf[o]; time.sleep(0); self.o = (o + 1) % self.cap
        self.empty.release()
        return x


def buffer_test(safe, P=2, C=2, items=5000, cap=8):
    bb, got, produced = BoundedBuffer(cap, safe), [], [(p, s) for p in range(P) for s in range(items)]

    def prod(p):
        for s in range(items):
            bb.put((p, s))

    def cons():
        while True:
            x = bb.get()
            if x == "TIMEOUT":
                return
            got.append(x)
    ths = [threading.Thread(target=prod, args=(p,)) for p in range(P)] + [threading.Thread(target=cons) for _ in range(C)]
    t = time.perf_counter(); [x.start() for x in ths]; [x.join() for x in ths]
    valid = [g for g in got if g is not None]
    return {"safe": safe, "produced": len(produced), "consumed": len(got), "lost": len(set(produced) - set(valid)),
            "duplicated": len(valid) - len(set(valid)), "stale_none": len(got) - len(valid), "wall_s": time.perf_counter() - t}


def deadlock_demo(timeout=0.5):
    """Dois locks em ordem oposta -> espera circular. Detectada por timeout; recuperação = ordem global (A antes de B)."""
    A, B, ev = threading.Lock(), threading.Lock(), []

    def worker(name, first, second, fname, sname):
        first.acquire(); time.sleep(0.1)
        if second.acquire(timeout=timeout):
            ev.append(f"{name}: obteve {fname}+{sname}"); second.release(); first.release()
        else:
            ev.append(f"{name}: TIMEOUT esperando {sname} (espera circular detectada); libera {fname}")
            first.release()
    t1 = threading.Thread(target=worker, args=("T1", A, B, "A", "B"))
    t2 = threading.Thread(target=worker, args=("T2", B, A, "B", "A"))
    t1.start(); t2.start(); t1.join(); t2.join()
    detected = any("TIMEOUT" in e for e in ev)
    rec = []

    def ordered(name):
        with A:
            time.sleep(0.05)
            with B:
                rec.append(name)
    t1 = threading.Thread(target=ordered, args=("T1",)); t2 = threading.Thread(target=ordered, args=("T2",))
    t1.start(); t2.start(); t1.join(2); t2.join(2)
    return {"deadlock_detected": detected, "recovered_with_lock_ordering": len(rec) == 2, "events": " | ".join(ev)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    for rep in range(1, a.reps + 1):
        base = {"rep": rep, "timestamp": now()}
        for safe, gap in ((False, True), (True, True), (False, False), (True, False)):
            r = cache_race(safe, gap); append_csv(RESULTS / "d_cache_race.csv", {**base, **r}); print("cache", r)
        for safe in (False, True):
            r = log_race(safe); append_csv(RESULTS / "d_log_race.csv", {**base, **r}); print("log", r)
        for safe in (False, True):
            r = buffer_test(safe); append_csv(RESULTS / "d_buffer.csv", {**base, **r}); print("buffer", r)
        r = deadlock_demo(); append_csv(RESULTS / "d_deadlock.csv", {**base, **r}); print("deadlock", r)


if __name__ == "__main__":
    main()
