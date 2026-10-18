"""Armazenamento: vetores em arquivo binário (read ou mmap) + metadados/texto em SQLite."""
import json, sqlite3, threading
from pathlib import Path
import numpy as np


class Store:
    def __init__(self, data_dir, mode="read"):
        d = Path(data_dir)
        mf = d / "manifest.json"
        if not mf.exists():
            raise FileNotFoundError(f"manifesto ausente: {mf}")
        self.dir, self.m = d, json.load(open(mf))
        shape = (self.m["n"], self.m["dim"])
        vp = d / "vectors.bin"
        if mode == "mmap":
            self.vecs = np.memmap(vp, dtype=np.float32, mode="r", shape=shape)
        else:
            self.vecs = np.fromfile(vp, dtype=np.float32).reshape(shape)
        self._tl = threading.local()

    def conn(self):  # uma conexão por thread (sqlite3 não é compartilhável por padrão)
        c = getattr(self._tl, "c", None)
        if c is None:
            c = sqlite3.connect(f"file:{self.dir / 'meta.sqlite'}?mode=ro", uri=True)
            self._tl.c = c
        return c

    def texts(self, ids):
        q = ",".join("?" * len(ids))
        rows = self.conn().execute(f"SELECT id, text FROM chunks WHERE id IN ({q})", ids).fetchall()
        return dict(rows)
