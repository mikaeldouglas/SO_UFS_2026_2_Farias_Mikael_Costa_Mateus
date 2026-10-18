"""Logger concorrente. safe=False reproduz de propósito o log intercalado (Parte D)."""
import datetime, threading, time
from pathlib import Path


class Logger:
    def __init__(self, path, safe=True, gap=False):
        self.safe, self.gap, self.lock, self.f = safe, gap, threading.Lock(), None
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.f = open(path, "w", buffering=1)

    def log(self, who, event, **kv):
        if not self.f:
            return
        ts = datetime.datetime.now().isoformat(timespec="microseconds")
        tail = "".join(f" {k}={v}" for k, v in kv.items())
        if self.safe:
            with self.lock:
                self.f.write(f"{ts} {who} {event}{tail}\n")
        else:  # três escritas separadas, sem lock -> linhas misturadas
            self.f.write(ts + " ")
            if self.gap:
                time.sleep(0)
            self.f.write(f"{who} {event}{tail}")
            if self.gap:
                time.sleep(0)
            self.f.write("\n")

    def close(self):
        if self.f:
            self.f.close()
