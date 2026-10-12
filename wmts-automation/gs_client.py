"""Minimal GeoServer / GWC REST client (curl-based: the App Gateway rejects Python's urllib).

Credentials come from the GEOSERVER_PASS environment variable (never from source). Prod calls must be
requested explicitly with allow_prod=True.
"""
import json
import os
import subprocess

HOSTS = {"dev": "devimageservices.priusintelli.com", "prod": "imageadmin.priusintelli.com"}
USER = os.environ.get("GEOSERVER_USER", "geoadmin")


def _password():
    pw = os.environ.get("GEOSERVER_PASS")
    if not pw:
        raise RuntimeError("Set the GEOSERVER_PASS environment variable (do not hard-code the password).")
    return pw


def call(env, method, path, body=None, ctype="application/json", accept="application/json", timeout=180, allow_prod=False):
    """Returns (http_status, parsed_json_or_text). Root context path: use /rest/... and /gwc/rest/..., not /geoserver/..."""
    if env == "prod" and not allow_prod:
        raise PermissionError("prod access requires allow_prod=True")
    if env not in HOSTS:
        raise ValueError(f"unknown env {env!r}")
    cmd = ["curl.exe", "-s", "--max-time", str(timeout), "-u", f"{USER}:{_password()}", "-X", method,
           "-H", f"Accept: {accept}", "-w", "\n__HTTP__%{http_code}", f"https://{HOSTS[env]}{path}"]
    data = None
    if body is not None:
        cmd[1:1] = ["-H", f"Content-Type: {ctype}", "--data-binary", "@-"]
        data = body if isinstance(body, str) else json.dumps(body)
    r = subprocess.run(cmd, input=data, capture_output=True, text=True)
    out, _, code = r.stdout.rpartition("\n__HTTP__")
    try:
        parsed = json.loads(out) if out.strip() else None
    except ValueError:
        parsed = out
    return int(code or 0), parsed
