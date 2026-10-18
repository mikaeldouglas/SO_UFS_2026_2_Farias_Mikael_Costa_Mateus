"""Ingestão: lê documentos, fragmenta, gera embeddings e grava vetores (.bin) + texto (SQLite)."""
import argparse, json, sqlite3, time
import numpy as np
from .common import ROOT, RESULTS, embed, now
from .logger import Logger


def chunker(text, size):
    i, n = 0, len(text)
    while i < n:
        j = min(i + size, n)
        if j < n:
            k = text.rfind(" ", i, j)
            j = k if k > i else j
        yield text[i:j]
        i = j + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw_small")
    ap.add_argument("--out", default="data/small")
    ap.add_argument("--chunk", type=int, default=500, help="caracteres por fragmento")
    ap.add_argument("--dim", type=int, default=128)
    ap.add_argument("--embed", choices=["hash", "random"], default="hash")
    ap.add_argument("--block", type=int, default=10000)
    a = ap.parse_args()
    raw, out = ROOT / a.raw, ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    log = Logger(RESULTS / "logs" / f"ingest_{out.name}.log")
    for f in ("vectors.bin", "meta.sqlite"):
        (out / f).unlink(missing_ok=True)
    db = sqlite3.connect(out / "meta.sqlite")
    db.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, doc TEXT, text TEXT)")
    rng = np.random.default_rng(0)
    t_read = t_emb = t_wr = 0.0
    t_all = time.perf_counter()
    st = {"n": 0}
    texts, docs = [], []
    vf = open(out / "vectors.bin", "wb")

    def flush():
        nonlocal t_emb, t_wr, texts, docs
        if not texts:
            return
        t = time.perf_counter()
        if a.embed == "hash":
            V = np.stack([embed(x, a.dim) for x in texts])
        else:
            V = rng.standard_normal((len(texts), a.dim)).astype(np.float32)
            V /= np.linalg.norm(V, axis=1, keepdims=True)
        t_emb += time.perf_counter() - t
        t = time.perf_counter()
        V.astype(np.float32).tofile(vf)
        n = st["n"]
        db.executemany("INSERT INTO chunks VALUES (?,?,?)", [(n + i, docs[i], texts[i]) for i in range(len(texts))])
        db.commit()
        t_wr += time.perf_counter() - t
        st["n"] += len(texts)
        texts, docs = [], []

    files = sorted(raw.glob("doc_*.txt"))
    raw_bytes = 0
    for fp in files:
        t = time.perf_counter()
        txt = fp.read_text()
        t_read += time.perf_counter() - t
        raw_bytes += len(txt)
        log.log("ING", "doc", file=fp.name, chars=len(txt))
        for c in chunker(txt, a.chunk):
            texts.append(c); docs.append(fp.name)
            if len(texts) >= a.block:
                flush()
    flush()
    vf.close(); db.close()
    m = {"n": st["n"], "dim": a.dim, "chunk_chars": a.chunk, "embed": a.embed, "docs": len(files),
         "raw_bytes": raw_bytes, "vectors_bytes": (out / "vectors.bin").stat().st_size,
         "sqlite_bytes": (out / "meta.sqlite").stat().st_size, "ingest_s": time.perf_counter() - t_all,
         "t_read_s": t_read, "t_embed_s": t_emb, "t_write_s": t_wr, "created": now()}
    json.dump(m, open(out / "manifest.json", "w"), indent=1)
    log.log("ING", "done", chunks=st["n"]); log.close()
    print(json.dumps(m))


if __name__ == "__main__":
    main()
