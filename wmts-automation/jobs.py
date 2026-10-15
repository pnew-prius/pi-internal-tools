"""Background batch runner. A job = an ordered list of COGs added ONE AT A TIME with the same steps each time.
One job per service at a time (group updates are not safe to run concurrently). A failed COG does not stop the
rest ("carry on"): the job ends 'done' (all ok), 'partial' (some failed) or 'failed' (all failed)."""
import contextlib
import threading
import time
import uuid

import add_cog as add_cog_mod
import gs_client
import instance_sync
import remove_service as remove_mod
from add_cog import STEPS


class Busy(RuntimeError):
    pass


def _blank_steps():
    return [{"name": n, "status": "pending", "seconds": None, "detail": None} for n in STEPS]


class JobManager:
    SYNC_MODES = ("reload", "restart", "none")

    def __init__(self, store, sync_fn=None):
        self.store = store
        self._sync_fn = sync_fn or self._default_sync
        self.jobs = {}
        self._active = set()
        self._lock = threading.Lock()

    @staticmethod
    def _default_sync(mode, progress=None):
        return instance_sync.sync(mode, gs_client._password(), progress=progress)

    @staticmethod
    def _sync_init(env, mode):
        if env != "prod":
            return {"mode": None, "status": "skipped", "detail": "not needed on dev (one server serves both admin and customers)"}
        return {"mode": mode, "status": "pending", "detail": None}

    def _seed_job(self, job):
        """Once per job, after the last COG: seed the footprints of the COGs added or refreshed and of the members touching them.
        Each add's bounded truncate also removes tiles along its neighbours' seams, so seeding per COG would leave holes in
        the earlier COGs; the batch defers seeding and does it here, after the last truncate.
        A seed failure never fails the COGs (they are published and render live), but the job is reported 'partial'."""
        s = job["seed"]
        needs = [it["result"].get("seed_needed") for it in job["items"] if it["status"] == "done" and it.get("result")]
        needs = [n for n in needs if n]
        if job["service"] != "wmts" or not needs:
            s.update(status="skipped", detail="nothing to seed")
            return
        s.update(status="running", detail=f"seeding {len(needs)} COG footprint(s) and their neighbours (zoom 0-15)")
        t0 = time.time()
        try:
            tiles, boxes = add_cog_mod.seed_affected(job["env"], job["workspace"], job["group"], needs)
            s.update(status="done", seconds=round(time.time() - t0, 1), tiles=tiles,
                     detail=f"{tiles} tiles over {boxes} footprint(s)")
        except Exception as e:
            s.update(status="failed", seconds=round(time.time() - t0, 1),
                     detail=f"{str(e)[:300]} - the COGs are published but their tiles are not pre-cached; run the add again with Refresh")
        if s["status"] == "failed":  # history keeps one row per COG; a seed row is added only when it needs attention
            self._safe_record(job, {"index": job["counts"]["total"], "tile": "(seed service tiles)", "blob_path": "", "status": "failed",
                                    "error": s["detail"], "seconds": s.get("seconds"), "started": job.get("started"), "finished": time.time()})

    def _sync_job(self, job, changed):
        """Once per job, after all seeding: make the customer-facing prod GeoServer instances see the change. Never fails the COGs."""
        s = job["sync"]
        if job["env"] != "prod":
            return
        if s["mode"] == "none":
            s.update(status="skipped", detail="skipped by choice: customers will NOT see this change until the scale set is reloaded or restarted")
        elif not changed:
            s.update(status="skipped", detail="nothing changed, so nothing to update")
        else:
            s["status"] = "running"
            t0 = time.time()
            try:
                r = self._sync_fn(s["mode"], progress=lambda msg: s.update(detail=msg))
                s.update(status="done", detail=r["detail"], instances=r.get("instances"), seconds=round(time.time() - t0, 1))
            except Exception as e:
                s.update(status="failed", seconds=round(time.time() - t0, 1),
                         detail=f"{str(e)[:300]} - customers may NOT see this change until the scale set is reloaded or restarted")
        if s["status"] != "skipped" or s["mode"] == "none":
            self._safe_record(job, {"index": job["counts"]["total"], "tile": "(update customer-facing GeoServer)", "blob_path": "",
                                    "status": s["status"], "error": s["detail"] if s["status"] in ("failed", "skipped") else None,
                                    "seconds": s.get("seconds"), "started": job.get("started"), "finished": time.time()})

    def submit(self, user, env, workspace, group, items, create_workspace=False, refresh=False, service="wmts", run=True, sync_mode="reload"):
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
                   "counts": {"total": len(items), "done": 0, "skipped": 0, "failed": 0}, "sync": self._sync_init(env, sync_mode),
                   "seed": {"status": "pending" if service == "wmts" else "skipped", "detail": None if service == "wmts" else "not needed for WMS"}}
            self.jobs[job["id"]] = job
        if run:
            threading.Thread(target=self._run, args=(job, create_workspace), daemon=True).start()
        return job

    def submit_remove(self, user, env, workspace, group, run=True, sync_mode="reload"):
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
                   "counts": {"total": 1, "done": 0, "skipped": 0, "failed": 0}, "sync": self._sync_init(env, sync_mode)}
            self.jobs[job["id"]] = job
        if run:
            threading.Thread(target=self._run_remove_session, args=(job,), daemon=True).start()
        return job

    def _run_remove_session(self, job):
        with self._session(job):
            self._run_remove(job)

    def _run_remove(self, job):
        job["status"], job["started"] = "running", time.time()
        item = job["items"][0]
        item["status"], item["started"] = "running", time.time()
        final = "failed"
        try:
            out = remove_mod.remove_service(job["env"], job["workspace"], job["group"], progress=self._progress(item), delete_empty_workspace=True)
            item["result"], item["status"], final = out, "done", "done"
            job["counts"]["done"] += 1
            item["finished"] = time.time()
            item["seconds"] = round(item["finished"] - item["started"], 1)
            self._sync_job(job, changed=True)       # customers must stop seeing the removed service too
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
            self._safe_record(job, item)
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

    def _safe_record(self, job, item):
        """Saving history is best effort: it must never stop or fail an add."""
        try:
            self._record(job, item)
        except Exception as e:
            job["history_error"] = f"{type(e).__name__}: {e}"[:200]
            print(f"[jobs] could not save history for {job['id']}: {job['history_error']}", flush=True)

    @staticmethod
    def _session(job):
        """Jobs on prod run inside an explicit prod write session; dev jobs need nothing."""
        return gs_client.prod_access(write=True) if job["env"] == "prod" else contextlib.nullcontext()

    def _run(self, job, create_workspace):
        with self._session(job):
            self._run_inner(job, create_workspace)

    def _run_inner(self, job, create_workspace):
        job["status"] = "running"
        job["started"] = time.time()
        stopped = None
        try:
            for item in job["items"]:
                job["current"] = item["index"]
                item["status"], item["started"] = "running", time.time()
                try:
                    m = add_cog_mod.add_cog(job["env"], job["workspace"], job["group"], item["tile"], item["blob_path"],
                                            progress=self._progress(item), create_workspace=create_workspace, refresh=job["refresh"],
                                            service=job["service"], seed="defer")
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
                item["finished"] = time.time()
                item["seconds"] = round(item["finished"] - item["started"], 1)
                self._safe_record(job, item)
                create_workspace = False  # the first COG created it (or it already existed)
            self._seed_job(job)                                      # ONCE, after the last COG is added
            self._sync_job(job, changed=job["counts"]["done"] > 0)   # ONCE, after the service is seeded
        except BaseException as e:  # anything unexpected: stop, but never report COGs that did not run as done
            stopped = f"{type(e).__name__}: {e}"[:300]
            job["error"] = f"The job stopped unexpectedly: {stopped}"
        finally:
            for item in job["items"]:
                if item["status"] in ("pending", "running"):
                    item["status"] = "failed"
                    item["error"] = f"Not run: the job stopped unexpectedly ({stopped or 'unknown reason'}). Run it again."
                    for s in item["steps"]:
                        if s["status"] == "running":
                            s["status"] = "failed"
                    job["counts"]["failed"] += 1
                    item["finished"] = time.time()
                    self._safe_record(job, item)
            c = job["counts"]
            job["finished"] = time.time()
            with self._lock:
                self._active.discard((job["env"], job["workspace"], job["group"]))
            job["current"] = None
            job["status"] = "failed" if c["failed"] == c["total"] else ("partial" if c["failed"] or job["seed"]["status"] == "failed" else "done")

    def get(self, job_id):
        return self.jobs.get(job_id)
