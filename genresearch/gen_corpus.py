"""Gera documentos sintéticos (públicos por construção) com tópicos, para recuperação por similaridade."""
import argparse, json, time
import numpy as np
from .common import N_TOPICS, TOPIC_WORDS, COMMON_WORDS, ROOT


def make_doc(rng, target):
    topics = rng.choice(N_TOPICS, 2, replace=False).tolist()
    parts, size = [], 0
    while size < target:
        t, k = topics[int(rng.integers(0, 2))], int(rng.integers(30, 80))
        is_t = (rng.random(k) < 0.3).tolist()
        tw = rng.integers(0, TOPIC_WORDS, k).tolist()
        cw = rng.integers(0, COMMON_WORDS, k).tolist()
        s = " ".join(f"t{t}w{a}" if m else f"c{b}" for m, a, b in zip(is_t, tw, cw)) + ". "
        parts.append(s)
        size += len(s)
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size-mb", type=float, default=20)
    ap.add_argument("--docs", type=int, default=200)
    ap.add_argument("--out", default="data/raw_small")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    per = int(a.size_mb * 2**20 / a.docs)
    t0, total = time.perf_counter(), 0
    for i in range(a.docs):
        txt = make_doc(rng, per)
        (out / f"doc_{i:05d}.txt").write_text(txt)
        total += len(txt)
    json.dump({"docs": a.docs, "bytes": total, "seed": a.seed, "gen_s": time.perf_counter() - t0},
              open(out / "raw_manifest.json", "w"), indent=1)
    print(f"{a.docs} docs, {total / 2**20:.1f} MB em {out}")


if __name__ == "__main__":
    main()
