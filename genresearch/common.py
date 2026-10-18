"""Utilitários compartilhados: métricas de SO, CSV, subprocessos, embedding por hashing."""
import csv, datetime, json, resource, subprocess, sys, threading, time, zlib
from pathlib import Path
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
N_TOPICS, TOPIC_WORDS, COMMON_WORDS = 50, 40, 3000


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


_csv_lock = threading.Lock()


def append_csv(path, row):
    """Acrescenta uma linha a um CSV (cria cabeçalho na primeira vez). Protegido por lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _csv_lock:
        if path.exists():
            with open(path, newline="") as f:
                fields = next(csv.reader(f))
        else:
            fields = list(row.keys())
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
            if f.tell() == 0:
                w.writeheader()
            w.writerow(row)


def meminfo():
    d = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            d[k.strip()] = int(v.split()[0])
    return d


def vmstat():
    d = {}
    with open("/proc/vmstat") as f:
        for line in f:
            k, v = line.split()
            d[k] = int(v)
    return d


def mem_snapshot():
    m = meminfo()
    mb = lambda k: m.get(k, 0) / 1024
    return {"MemTotal_MB": mb("MemTotal"), "MemFree_MB": mb("MemFree"),
            "MemAvailable_MB": mb("MemAvailable"), "Cached_MB": mb("Cached"),
            "SwapUsed_MB": (m.get("SwapTotal", 0) - m.get("SwapFree", 0)) / 1024}


def proc_snapshot():
    p = psutil.Process()
    mi = p.memory_info()
    ru = resource.getrusage(resource.RUSAGE_SELF)
    try:
        io = p.io_counters()
        rd, wr = io.read_bytes / 2**20, io.write_bytes / 2**20
    except Exception:
        rd = wr = 0.0
    return {"rss_mb": mi.rss / 2**20, "vsz_mb": mi.vms / 2**20, "maxrss_mb": ru.ru_maxrss / 1024,
            "minflt": ru.ru_minflt, "majflt": ru.ru_majflt, "io_read_mb": rd, "io_write_mb": wr}


class Sampler(threading.Thread):
    """Amostra RSS, MemAvailable e swap em segundo plano (picos durante a execução)."""
    def __init__(self, interval=0.1):
        super().__init__(daemon=True)
        self.interval, self.evt = interval, threading.Event()
        self.peak_rss = 0.0
        self.min_avail = float("inf")
        self.max_swap = 0.0

    def run(self):
        p = psutil.Process()
        while not self.evt.is_set():
            self.peak_rss = max(self.peak_rss, p.memory_info().rss / 2**20)
            m = mem_snapshot()
            self.min_avail = min(self.min_avail, m["MemAvailable_MB"])
            self.max_swap = max(self.max_swap, m["SwapUsed_MB"])
            self.evt.wait(self.interval)

    def stop(self):
        self.evt.set()
        self.join()


def fadvise_dontneed(path):
    """Remove do cache de páginas as páginas limpas do arquivo (leitura 'fria' sem root)."""
    import os
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


def run_module(module, args):
    """Executa 'python -m module args' em subprocesso e devolve o último JSON impresso."""
    cmd = [sys.executable, "-m", module, *map(str, args)]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"rc={p.returncode} cmd={' '.join(cmd)}\n{p.stderr[-1500:]}")
    lines = [l for l in p.stdout.splitlines() if l.strip().startswith("{")]
    return json.loads(lines[-1])


def to_args(**kw):
    out = []
    for k, v in kw.items():
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                out.append(flag)
        else:
            out += [flag, str(v)]
    return out


def embed(text, dim):
    """Embedding por feature hashing (determinístico, sem modelo): suficiente para recuperação."""
    v = np.zeros(dim, dtype=np.float32)
    for tok in text.split():
        h = zlib.crc32(tok.encode())
        v[h % dim] += 1.0 if (h >> 16) & 1 else -1.0
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def query_text(qid):
    r = np.random.default_rng(int(qid))
    t = int(qid) % N_TOPICS
    ws = r.choice(TOPIC_WORDS, 4, replace=False)
    return " ".join(f"t{t}w{int(w)}" for w in ws)
