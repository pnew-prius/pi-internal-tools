"""Background job manager: one add-COG job at a time per service (group updates are not safe to run concurrently)."""
import threading
import time
import uuid

import add_cog as add_cog_mod
from add_cog import STEPS


class Busy(RuntimeError):
    pass


class JobManager:
    def __init__(self, store):
        self.store = store
        self.jobs = {}
        self._active = set()
        self._lock = threading.Lock()

    def submit(self, user, env, workspace, group, tile, blob_path, create_workspace=False, run=True):
        key = (env, workspace, group)
        with self._lock:
            if key in self._active:
                raise Busy(f"Another add is already running for {workspace}:{group}. Wait for it to finish.")
            self._active.add(key)
            job = {"id": uuid.uuid4().hex[:12], "user": user, "env": env, "workspace": workspace, "group": group,
                   "tile": tile, "blob_path": blob_path, "status": "queued", "created": time.time(),
                   "steps": [{"name": n, "status": "pending", "seconds": None, "detail": None} for n in STEPS],
                   "result": None, "error": None}
            self.jobs[job["id"]] = job
        if run:
            threading.Thread(target=self._run, args=(job, create_workspace), daemon=True).start()
        return job

    def _progress(self, job):
        def cb(step, status, seconds=None, detail=None):
            for s in job["steps"]:
                if s["name"] == step:
                    s.update(status=status, seconds=seconds, detail=detail)
        return cb

    def _run(self, job, create_workspace):
        job["status"] = "running"
        job["started"] = time.time()
        final = "failed"
        try:
            m = add_cog_mod.add_cog(job["env"], job["workspace"], job["group"], job["tile"], job["blob_path"],
                                    progress=self._progress(job), create_workspace=create_workspace)
            if m.get("skipped"):
                for s in job["steps"]:
                    if s["status"] == "pending":
                        s["status"] = "skipped"
            job["result"] = {k: v for k, v in m.items() if k not in ("footprint_3857",)}
            final = "done"
        except Exception as e:  # report to the user; the add is idempotent so it can simply be run again
            job["error"] = str(e)[:500]
            for s in job["steps"]:
                if s["status"] == "running":
                    s["status"] = "failed"
        finally:
            job["finished"] = time.time()
            with self._lock:
                self._active.discard((job["env"], job["workspace"], job["group"]))
            self.store.save({**job, "status": final})   # persist BEFORE the status flips, so the UI never sees "done" without history
            job["status"] = final

    def get(self, job_id):
        return self.jobs.get(job_id)
