"""Web UI + API for adding COGs to WMTS and WMS services.

PROD is fail-closed: it is offered only if WMTS_ENVS includes "prod" AND the user is listed in WMTS_PROD_USERS (comma-separated
emails) or is a member of the Entra group WMTS_PROD_GROUP_ID (read from the App Service sign-in claims). Every prod change also needs
an explicit confirmation, and on prod the app only modifies services it created itself.

Sign-in: in Azure, App Service Authentication (Microsoft Entra, restricted to a security group) puts the user in the
X-MS-CLIENT-PRINCIPAL-NAME header. Locally set WMTS_LOCAL=1 (and optionally WMTS_DEV_USER) to run without it.
Run locally:  python app.py   (see README)
"""
import base64
import contextlib
import json
import os
import re

from flask import Flask, jsonify, render_template, request

import gs_client
import safety
from add_cog import SERVICE_TYPES, group_marker, group_service_type, group_state
from gs_client import call
from jobs import Busy, JobManager
from store import JsonlStore
from validate import ValidationError, check_name, parse_batch

PUBLIC_HOSTS = {"dev": "devimageservices.priusintelli.com", "prod": "imageservices.priusintelli.com"}


def create_app(manager=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024  # a 100-line batch is ~15 KB; refuse anything much larger
    app.config["TEMPLATES_AUTO_RELOAD"] = os.environ.get("WMTS_LOCAL") == "1"  # edit-and-refresh while developing locally
    envs = [e.strip() for e in os.environ.get("WMTS_ENVS", "dev").split(",") if e.strip()]
    prod_users = {u.strip().lower() for u in os.environ.get("WMTS_PROD_USERS", "").split(",") if u.strip()}
    prod_group = os.environ.get("WMTS_PROD_GROUP_ID", "").strip()
    prod_max_batch = int(os.environ.get("WMTS_PROD_MAX_BATCH", "25"))
    if "prod" in envs and not (prod_users or prod_group):
        envs.remove("prod")   # fail closed: prod requested but nobody is authorized to use it
    data_dir = os.environ.get("WMTS_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    mgr = manager or JobManager(JsonlStore(os.path.join(data_dir, "history.jsonl")))
    app.config["MANAGER"] = mgr

    def current_user():
        name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        if name:
            return name
        if os.environ.get("WMTS_LOCAL") == "1":
            return os.environ.get("WMTS_DEV_USER", "local-dev")
        return None

    def principal_groups():
        """Group object IDs from the App Service sign-in claims (X-MS-CLIENT-PRINCIPAL is base64 JSON)."""
        raw = request.headers.get("X-MS-CLIENT-PRINCIPAL")
        if not raw:
            return set()
        try:
            claims = json.loads(base64.b64decode(raw)).get("claims", [])
        except Exception:
            return set()
        return {c.get("val") for c in claims if c.get("typ") in ("groups", "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups")}

    def user_can_prod():
        if "prod" not in envs:
            return False
        user = (current_user() or "").lower()
        return user in prod_users or bool(prod_group and prod_group in principal_groups())

    def allowed_envs():
        return [e for e in envs if e != "prod" or user_can_prod()]

    def prod_session(env, write=False):
        return gs_client.prod_access(write=write) if env == "prod" else contextlib.nullcontext()

    class Forbidden(Exception):
        pass

    @app.errorhandler(Forbidden)
    def forbidden(e):
        return jsonify(error=str(e)), 403

    @app.before_request
    def require_user():
        if request.path == "/healthz":
            return None
        if current_user() is None:
            return jsonify(error="Sign-in required."), 401
        return None

    def env_or_400():
        allowed = allowed_envs()
        env = request.values.get("env") or (request.get_json(silent=True) or {}).get("env") or allowed[0]
        if env == "prod" and "prod" in envs and not user_can_prod():
            raise Forbidden("You are not authorized to use PROD.")
        if env not in allowed:
            raise ValidationError(f"Environment '{env}' is not enabled here (enabled: {', '.join(allowed) or 'none'}).")
        return env

    class UnsupportedMedia(Exception):
        pass

    @app.errorhandler(UnsupportedMedia)
    def media(e):
        return jsonify(error="Send application/json."), 415

    @app.errorhandler(413)
    def too_big(e):
        return jsonify(error="Request too large."), 413

    @app.errorhandler(ValidationError)
    def bad(e):
        return jsonify(error=str(e)), 400

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.get("/")
    def index():
        return render_template("index.html", user=current_user(), envs=allowed_envs())

    @app.get("/api/me")
    def me():
        return jsonify(user=current_user(), envs=allowed_envs(), prod_max_batch=prod_max_batch)

    @app.get("/api/workspaces")
    def workspaces():
        env = env_or_400()
        with prod_session(env):
            c, r = call(env, "GET", "/rest/workspaces.json")
        ws = r.get("workspaces") if isinstance(r, dict) else None
        return jsonify(workspaces=sorted(w["name"] for w in ws["workspace"]) if isinstance(ws, dict) else [])

    @app.get("/api/groups")
    def groups():
        env = env_or_400()
        ws = check_name("Workspace", request.args.get("workspace"))
        with prod_session(env):
            c, r = call(env, "GET", f"/rest/workspaces/{ws}/layergroups.json")
        lg = r.get("layerGroups") if isinstance(r, dict) else None
        return jsonify(groups=sorted(g["name"] for g in lg["layerGroup"]) if isinstance(lg, dict) else [])

    @app.get("/api/service")
    def service():
        env = env_or_400()
        ws = check_name("Workspace", request.args.get("workspace"))
        group = check_name("Service", request.args.get("group"))
        with prod_session(env):
            st = group_state(env, ws, group)
            stype = group_service_type(env, ws, group, st[0]) if st else None
        host = PUBLIC_HOSTS[env]
        # scoped to the service (workspace/layer group), so a client sees only this layer group and not every service in the workspace
        urls = {"wmts": f"https://{host}/{ws}/{group}/gwc/service/wmts?REQUEST=GetCapabilities",
                "wms": f"https://{host}/{ws}/{group}/ows?service=WMS&request=GetCapabilities&version=1.3.0"}
        tile = (f"https://{host}/gwc/service/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&LAYER={ws}:{group}&STYLE="
                "&TILEMATRIXSET=EPSG:3857&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/png")
        return jsonify(exists=st is not None, members=len(st[1]) if st else 0, service_type=stype, layer=f"{ws}:{group}",
                       capabilities_url=urls.get(stype, urls["wmts"]), wms_url=urls["wms"],
                       wmts_url=urls["wmts"] if stype == "wmts" else None, tile_url_template=tile if stype == "wmts" else None)

    def json_body():
        # Require application/json: a cross-site HTML form can only send form/text content types, so this blocks CSRF.
        if not request.is_json:
            raise UnsupportedMedia()
        return request.get_json(silent=True) or {}

    def batch_text(body):
        if isinstance(body.get("blob_paths"), list):
            return chr(10).join(str(x) for x in body["blob_paths"])
        return body.get("blob_text") or body.get("blob_path") or ""

    @app.post("/api/validate")
    def validate_batch():
        items, errors = parse_batch(batch_text(json_body()))
        return jsonify(items=items, errors=errors)

    @app.post("/api/jobs")
    def create_job():
        body = json_body()
        env = env_or_400()
        ws = check_name("Workspace", body.get("workspace"))
        group = check_name("Service", body.get("group"))
        sync_mode = (body.get("sync_mode") or "reload").lower()
        if sync_mode not in JobManager.SYNC_MODES:
            raise ValidationError(f"sync_mode must be one of: {', '.join(JobManager.SYNC_MODES)}.")
        service = (body.get("service_type") or "wmts").lower()
        if service not in SERVICE_TYPES:
            raise ValidationError(f"Service type must be one of: {', '.join(SERVICE_TYPES)}.")
        items, errors = parse_batch(batch_text(body))
        if errors:
            return jsonify(error=f"{len(errors)} problem(s) in the COG list; nothing was started.", problems=errors), 400
        if env == "prod":
            if body.get("confirm_prod") is not True:
                raise ValidationError("Tick the box to confirm you are changing PRODUCTION. Nothing was started.")
            if len(items) > prod_max_batch:
                raise ValidationError(f"At most {prod_max_batch} COGs per run on PROD ({len(items)} pasted); seeding competes with live traffic.")
            with prod_session(env):
                st = group_state(env, ws, group)
            if st is not None and group_marker(st[0]) is None:
                raise Forbidden("On PROD this app only modifies services it created. This service was built another way, so it is not touched.")
        try:
            safety.assert_not_on_prod(env, ws)
        except PermissionError as e:
            return jsonify(error=str(e)), 403
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        try:
            job = mgr.submit(current_user(), env, ws, group, [{"tile": i["tile"], "path": i["path"]} for i in items],
                             create_workspace=bool(body.get("create_workspace")), refresh=bool(body.get("refresh")), service=service, sync_mode=sync_mode)
        except Busy as e:
            return jsonify(error=str(e)), 409
        return jsonify(job=job), 202

    @app.post("/api/remove")
    def remove():
        body = json_body()
        env = env_or_400()
        ws = check_name("Workspace", body.get("workspace"))
        group = check_name("Service", body.get("group"))
        expected = f"{ws}:{group}" if env == "prod" else group
        if body.get("confirm") != expected:
            raise ValidationError(f"Type exactly {expected} to confirm the removal." if env == "prod" else "Type the exact service name to confirm the removal.")
        try:
            safety.assert_not_on_prod(env, ws)
        except PermissionError as e:
            return jsonify(error=str(e)), 403
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        with prod_session(env):
            st = group_state(env, ws, group)
        if st is None:
            return jsonify(error=f"Service {ws}:{group} does not exist."), 404
        if group_marker(st[0]) is None:
            return jsonify(error="This service was not created by this app, so it cannot be removed here."), 403
        try:
            sync_mode = (body.get("sync_mode") or "reload").lower()
            if sync_mode not in JobManager.SYNC_MODES:
                raise ValidationError(f"sync_mode must be one of: {', '.join(JobManager.SYNC_MODES)}.")
            job = mgr.submit_remove(current_user(), env, ws, group, sync_mode=sync_mode)
        except Busy as e:
            return jsonify(error=str(e)), 409
        return jsonify(job=job), 202

    @app.get("/api/jobs/<job_id>")
    def job(job_id):
        j = mgr.get(re.sub(r"[^a-f0-9]", "", job_id))
        if not j:
            return jsonify(error="Unknown job (it may predate a restart; see history)."), 404
        return jsonify(job=j)

    @app.get("/api/jobs")
    def history():
        live = [{"id": j["id"], "user": j["user"], "workspace": j["workspace"], "group": j["group"], "status": j["status"],
                 "created": j["created"], "counts": j["counts"], "service": j.get("service")} for j in mgr.jobs.values() if j["status"] in ("queued", "running")]
        return jsonify(running=live, jobs=mgr.store.recent(60))

    return app


if __name__ == "__main__":
    os.environ.setdefault("WMTS_LOCAL", "1")
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), debug=False, threaded=True)
