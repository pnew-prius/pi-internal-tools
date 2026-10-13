"""Minimal GeoServer / GWC REST client (requests-based, portable to Linux App Service).

The App Gateway returns 403 to Python's default User-Agent, so every request sends a custom one.
Credential: GEOSERVER_PASS env var if set, otherwise the `geoadmin` secret in the `pi-geoserver` Key Vault, read with
DefaultAzureCredential (your `az login` locally, the app's managed identity in Azure). Never hard-coded.
Prod calls must be requested explicitly with allow_prod=True.
"""
import contextlib
import json
import os
import threading

import requests

HOSTS = {"dev": "devimageservices.priusintelli.com", "prod": "imageadmin.priusintelli.com"}
USER = os.environ.get("GEOSERVER_USER", "geoadmin")
USER_AGENT = "wmts-automation/1.0"
_tls = threading.local()
_secret = {"value": None}


@contextlib.contextmanager
def prod_access(write=False):
    """Explicitly enable PROD for the current thread: read-only by default, writes only with write=True.
    Without this (or allow_prod=True for a read), every prod call raises PermissionError."""
    prev = getattr(_tls, "prod", None)
    _tls.prod = "write" if write else "read"
    try:
        yield
    finally:
        _tls.prod = prev


def _prod_allowed(method, allow_prod):
    mode = getattr(_tls, "prod", None)
    is_write = method.upper() not in ("GET", "HEAD")
    if mode == "write":
        return True
    if (mode == "read" or allow_prod) and not is_write:
        return True
    return False


def _password():
    pw = os.environ.get("GEOSERVER_PASS")
    if pw:
        return pw
    if _secret["value"]:
        return _secret["value"]
    vault = os.environ.get("GEOSERVER_KEYVAULT", "pi-geoserver")
    name = os.environ.get("GEOSERVER_SECRET", "geoadmin")
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        _secret["value"] = SecretClient(f"https://{vault}.vault.azure.net", DefaultAzureCredential()).get_secret(name).value
    except Exception as e:
        raise RuntimeError(f"Could not read the GeoServer credential from Key Vault '{vault}' ({type(e).__name__}). "
                           "Run `az login`, or set GEOSERVER_PASS for local testing.") from e
    return _secret["value"]


def _session():
    if not hasattr(_tls, "s"):
        _tls.s = requests.Session()
        _tls.s.headers["User-Agent"] = USER_AGENT
    return _tls.s


def call(env, method, path, body=None, ctype="application/json", accept="application/json", timeout=180, allow_prod=False):
    """Returns (http_status, parsed_json_or_text); (0, message) on a connection failure.
    Root context path: use /rest/... and /gwc/rest/..., not /geoserver/..."""
    if env == "prod" and not _prod_allowed(method, allow_prod):
        raise PermissionError(f"prod {method} refused: prod needs an explicit prod_access() session (writes need write=True)")
    if env not in HOSTS:
        raise ValueError(f"unknown env {env!r}")
    headers = {"Accept": accept}
    data = None
    if body is not None:
        headers["Content-Type"] = ctype
        data = body if isinstance(body, str) else json.dumps(body)
    try:
        r = _session().request(method, f"https://{HOSTS[env]}{path}", data=data, headers=headers,
                               auth=(USER, _password()), timeout=timeout)
    except requests.RequestException as e:
        return 0, str(e)
    try:
        parsed = r.json() if r.text.strip() else None
    except ValueError:
        parsed = r.text
    return r.status_code, parsed
