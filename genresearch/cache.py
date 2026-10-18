"""Cache compartilhado LRU/FIFO. safe=False remove o lock (condição de corrida didática)."""
import threading, time
from collections import OrderedDict


class Cache:
    def __init__(self, capacity, policy="lru", safe=True, race_gap=False):
        self.cap, self.policy, self.gap = capacity, policy, race_gap
        self.lock = threading.Lock() if safe else None
        self.d = OrderedDict()
        self.hits = self.misses = self.evictions = self.errors = self.max_len = 0
        self.saved = 0.0

    def _gap(self):  # força troca de thread entre "ler" e "escrever" o contador
        if self.gap:
            time.sleep(0)

    def get(self, key):
        if self.lock:
            with self.lock:
                return self._get(key)
        return self._get(key)

    def put(self, key, val, cost=0.0):
        if self.lock:
            with self.lock:
                return self._put(key, val, cost)
        return self._put(key, val, cost)

    def _get(self, key):
        try:
            if key in self.d:
                val, cost = self.d[key]
                if self.policy == "lru":
                    self.d.move_to_end(key)
                h = self.hits; self._gap(); self.hits = h + 1
                s = self.saved; self._gap(); self.saved = s + cost
                return val
        except KeyError:  # só ocorre sem lock: outra thread removeu a chave
            self.errors += 1
        m = self.misses; self._gap(); self.misses = m + 1
        return None

    def _put(self, key, val, cost):
        if self.cap <= 0:
            return
        self.d[key] = (val, cost)
        if self.policy == "lru":
            try:
                self.d.move_to_end(key)
            except KeyError:
                self.errors += 1
        while len(self.d) > self.cap:
            self._gap()
            try:
                self.d.popitem(last=False)
            except KeyError:
                self.errors += 1
                break
            e = self.evictions; self._gap(); self.evictions = e + 1
        self.max_len = max(self.max_len, len(self.d))

    def stats(self):
        tot = self.hits + self.misses
        return {"cache_hits": self.hits, "cache_misses": self.misses,
                "cache_hit_rate": self.hits / tot if tot else 0.0,
                "cache_evictions": self.evictions, "cache_saved_s": self.saved,
                "cache_max_len": self.max_len, "cache_errors": self.errors}
