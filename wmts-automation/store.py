"""Job history. v1 keeps finished jobs in a local JSON-lines file; the interface is small so an Azure Table/Blob
backend can replace it before deployment (App Service's local disk is not durable across redeploys)."""
import json
import os
import threading


class JsonlStore:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def save(self, job):
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(job, default=str) + "\n")

    def recent(self, limit=25):
        if not os.path.exists(self.path):
            return []
        with self._lock, open(self.path, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return list(reversed(out))
