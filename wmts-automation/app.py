"""Web UI + API for adding COGs to WMTS services.

Sign-in: in Azure, App Service Authentication (Microsoft Entra, restricted to a security group) puts the user in the
X-MS-CLIENT-PRINCIPAL-NAME header. Locally set WMTS_LOCAL=1 (and optionally WMTS_DEV_USER) to run without it.
Run locally:  python app.py   (see README)
"""
import os
import re

from flask import Flask, jsonify, render_template, request

import safety
from add_cog import SERVICE_TYPES, group_service_type, group_state
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

    @app.before_request
    def require_user():
        if request.path == "/healthz":
            return None
        if current_user() is None:
            return jsonify(error="Sign-in required."), 401
        return None

    def env_or_400():
        env = request.values.get("env") or (request.get_json(silent=True) or {}).get("env") or envs[0]
        if env not in envs:
            raise ValidationError(f"Environment '{env}' is not enabled here (enabled: {', '.join(envs)}).")
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
        return render_template("index.html", user=current_user(), envs=envs)

    @app.get("/api/me")
    def me():
        return jsonify(user=current_user(), envs=envs)

    @app.get("/api/workspaces")
    def workspaces():
        env = env_or_400()
        c, r = call(env, "GET", "/rest/workspaces.json")
        ws = r.get("workspaces") if isinstance(r, dict) else None
        return jsonify(workspaces=sorted(w["name"] for w in ws["workspace"]) if isinstance(ws, dict) else [])

    @app.get("/api/groups")
    def groups():
        env = env_or_400()
        ws = check_name("Workspace", request.args.get("workspace"))
        c, r = call(env, "GET", f"/rest/workspaces/{ws}/layergroups.json")
        lg = r.get("layerGroups") if isinstance(r, dict) else None
        return jsonify(groups=sorted(g["name"] for g in lg["layerGroup"]) if isinstance(lg, dict) else [])

    @app.get("/api/service")
    def service():
        env = env_or_400()
        ws = check_name("Workspace", request.args.get("workspace"))
        group = check_name("Service", request.args.get("group"))
        st = group_state(env, ws, group)
        host = PUBLIC_HOSTS[env]
        stype = group_service_type(env, ws, group, st[0]) if st else None
        urls = {"wmts": f"https://{host}/{ws}/gwc/service/wmts?REQUEST=GetCapabilities",
                "wms": f"https://{host}/{ws}/ows?service=WMS&request=GetCapabilities&version=1.3.0"}
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
        service = (body.get("service_type") or "wmts").lower()
        if service not in SERVICE_TYPES:
            raise ValidationError(f"Service type must be one of: {', '.join(SERVICE_TYPES)}.")
        items, errors = parse_batch(batch_text(body))
        if errors:
            return jsonify(error=f"{len(errors)} problem(s) in the COG list; nothing was started.", problems=errors), 400
        try:
            safety.assert_not_on_prod(env, ws)
        except PermissionError as e:
            return jsonify(error=str(e)), 403
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        try:
            job = mgr.submit(current_user(), env, ws, group, [{"tile": i["tile"], "path": i["path"]} for i in items],
                             create_workspace=bool(body.get("create_workspace")), refresh=bool(body.get("refresh")), service=service)
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
