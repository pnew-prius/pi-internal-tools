"""Background batch runner. A job = an ordered list of COGs added ONE AT A TIME with the same steps each time.
One job per service at a time (group updates are not safe to run concurrently). A failed COG does not stop the
rest ("carry on"): the job ends 'done' (all ok), 'partial' (some failed) or 'failed' (all failed)."""
import threading
import time
import uuid

import add_cog as add_cog_mod
import remove_service as remove_mod
from add_cog import STEPS


class Busy(RuntimeError):
    pass


def _blank_steps():
    return [{"name": n, "status": "pending", "seconds": None, "detail": None} for n in STEPS]


class JobManager:
    def __init__(self, store):
        self.store = store
        self.jobs = {}
        self._active = set()
        self._lock = threading.Lock()

    def submit(self, user, env, workspace, group, items, create_workspace=False, refresh=False, service="wmts", run=True):
        """items: [{'tile':..., 'path':...}, ...] in the order to add them."""
        key = (env, workspace, group)
        with self._lock:
            if key in self._active:
                raise Busy(f"Another add is already running for {workspace}:{group}. Wait for it to finish.")
            self._active.add(key)
            job = {"id": uuid.uuid4().hex[:12], "user": user, "env": env, "workspace": workspace, "group": group,
                   "status": "queued", "created": time.time(), "refresh": refresh, "service": service, "current": None,
                   "items": [{"index": i, "tile": it["tile"], "blob_path": it["path"], "status": "pending", "steps": _blank_steps(),
                              "result": None, "error": None, "seconds": None} for i, it in enumerate(items)],
                   "counts": {"total": len(items), "done": 0, "skipped": 0, "failed": 0}}
            self.jobs[job["id"]] = job
        if run:
            threading.Thread(target=self._run, args=(job, create_workspace), daemon=True).start()
        return job

    def submit_remove(self, user, env, workspace, group, run=True):
        """Remove a whole service (tile cache first). One job per service, same lock as adds."""
        key = (env, workspace, group)
        with self._lock:
            if key in self._active:
                raise Busy(f"Another job is already running for {workspace}:{group}. Wait for it to finish.")
            self._active.add(key)
            steps = [{"name": n, "status": "pending", "seconds": None, "detail": None} for n in remove_mod.REMOVE_STEPS]
            job = {"id": uuid.uuid4().hex[:12], "user": user, "env": env, "workspace": workspace, "group": group, "kind": "remove",
                   "status": "queued", "created": time.time(), "refresh": False, "service": None, "current": None,
                   "items": [{"index": 0, "tile": "(remove service)", "blob_path": "", "status": "pending", "steps": steps,
                              "result": None, "error": None, "seconds": None}],
                   "counts": {"total": 1, "done": 0, "skipped": 0, "failed": 0}}
            self.jobs[job["id"]] = job
        if run:
            threading.Thread(target=self._run_remove, args=(job,), daemon=True).start()
        return job

    def _run_remove(self, job):
        job["status"], job["started"] = "running", time.time()
        item = job["items"][0]
        item["status"], item["started"] = "running", time.time()
        final = "failed"
        try:
            out = remove_mod.remove_service(job["env"], job["workspace"], job["group"], progress=self._progress(item), delete_empty_workspace=True)
            item["result"], item["status"], final = out, "done", "done"
            job["counts"]["done"] += 1
        except Exception as e:
            item["status"], item["error"] = "failed", str(e)[:500]
            job["counts"]["failed"] += 1
            for s in item["steps"]:
                if s["status"] == "running":
                    s["status"] = "failed"
        finally:
            item["finished"] = time.time()
            item["seconds"] = round(item["finished"] - item["started"], 1)
            job["finished"] = time.time()
            with self._lock:
                self._active.discard((job["env"], job["workspace"], job["group"]))
            job["current"] = None
            self._record(job, item)
            job["status"] = final

    @staticmethod
    def _progress(item):
        def cb(step, status, seconds=None, detail=None):
            for s in item["steps"]:
                if s["name"] == step:
                    s.update(status=status, seconds=seconds, detail=detail)
        return cb

    def _record(self, job, item):
        """One history row per COG, saved as soon as that COG finishes (a crash mid-batch keeps what was done)."""
        self.store.save({"id": f"{job['id']}-{item['index']}", "batch": job["id"], "user": job["user"], "env": job["env"],
                         "workspace": job["workspace"], "group": job["group"], "service": job["service"], "kind": job.get("kind", "add"), "tile": item["tile"], "blob_path": item["blob_path"],
                         "status": item["status"], "error": item["error"], "created": job["created"],
                         "started": item.get("started"), "finished": item.get("finished"), "seconds": item["seconds"],
                         "batch_size": job["counts"]["total"]})

    def _run(self, job, create_workspace):
        job["status"] = "running"
        job["started"] = time.time()
        try:
            for item in job["items"]:
                job["current"] = item["index"]
                item["status"], item["started"] = "running", time.time()
                try:
                    m = add_cog_mod.add_cog(job["env"], job["workspace"], job["group"], item["tile"], item["blob_path"],
                                            progress=self._progress(item), create_workspace=create_workspace, refresh=job["refresh"],
                                            service=job["service"])
                    if m.get("skipped"):
                        for s in item["steps"]:
                            if s["status"] == "pending":
                                s["status"] = "skipped"
                        item["status"] = "skipped"
                        job["counts"]["skipped"] += 1
                    else:
                        item["status"] = "done"
                        job["counts"]["done"] += 1
                    item["result"] = {k: v for k, v in m.items() if k != "footprint_3857"}
                except Exception as e:  # carry on with the next COG; every add is idempotent so a failed one can be re-run
                    item["status"], item["error"] = "failed", str(e)[:500]
                    job["counts"]["failed"] += 1
                    for s in item["steps"]:
                        if s["status"] == "running":
                            s["status"] = "failed"
                finally:
                    item["finished"] = time.time()
                    item["seconds"] = round(item["finished"] - item["started"], 1)
                    self._record(job, item)
                create_workspace = False  # the first COG created it (or it already existed)
        finally:
            c = job["counts"]
            job["finished"] = time.time()
            with self._lock:
                self._active.discard((job["env"], job["workspace"], job["group"]))
            job["current"] = None
            job["status"] = "failed" if c["failed"] == c["total"] else ("partial" if c["failed"] else "done")

    def get(self, job_id):
        return self.jobs.get(job_id)
