"""Entry point for the packaged Windows app (PyInstaller). Runs the same web app as run_local.py, on this computer only.

Start:      wmts-builder.exe            (opens http://localhost:8000 in your browser; close the window to stop it)
            DEV and PROD are both offered in the Environment dropdown, to YOUR signed-in Azure user only. Every PROD change still
            is marked with a red PRODUCTION bar, only services this program created can be changed on PROD, and a removal needs the name typed.
Dev only:   wmts-builder.exe --dev-only (hides PROD)
Credential: your `az login` -> Key Vault `pi-geoserver`/`geoadmin` (or set GEOSERVER_PASS to skip Key Vault).
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import webbrowser

frozen = getattr(sys, "frozen", False)
here = os.path.dirname(sys.executable if frozen else os.path.abspath(__file__))

# job history lives next to the program (the frozen program itself unpacks to a temporary folder that is not kept)
os.environ.setdefault("WMTS_DATA_DIR", os.path.join(here, "data"))
# the app uses no az extensions; an empty extension dir stops a broken extension on some machines from failing every az call
ext = os.path.join(tempfile.gettempdir(), "azext_empty")
os.makedirs(ext, exist_ok=True)
os.environ.setdefault("AZURE_EXTENSION_DIR", ext)
os.environ["WMTS_LOCAL"] = "1"   # local single-user mode: the signed-in `az` user is the user of record
# the production customer-facing scale set that "refresh/restart the customer servers" acts on (needs your Azure rights on it; override with the same variable)
os.environ.setdefault("WMTS_PROD_SYNC_TARGET", "vmss:RG_GEOSERVER_SOUTHCENTRALUS/geoserver-vmss")


def az_user():
    try:
        r = subprocess.run("az account show --query user.name -o tsv", capture_output=True, text=True, shell=True, timeout=60)
        return r.stdout.strip() or None
    except Exception:
        return None


if not os.environ.get("WMTS_DEV_USER"):
    os.environ["WMTS_DEV_USER"] = az_user() or "local-dev"
if "--dev-only" not in sys.argv and os.environ["WMTS_DEV_USER"] != "local-dev":   # PROD is offered to the signed-in Azure user only
    os.environ["WMTS_ENVS"] = "dev,prod"
    os.environ["WMTS_PROD_USERS"] = os.environ["WMTS_DEV_USER"]


def free_port(start):
    for p in range(start, start + 11):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit(f"Ports {start}-{start + 10} are all in use. Close the other program or set PORT.")


def main():
    import app
    port = free_port(int(os.environ.get("PORT", "8000")))
    url = f"http://localhost:{port}"
    print(f"WMTS service builder\n  signed in as: {os.environ['WMTS_DEV_USER']}\n  environments: {os.environ.get('WMTS_ENVS', 'dev')}"
          f"\n  open: {url}\n  history: {os.environ['WMTS_DATA_DIR']}\n\nLeave this window open while you use the page; close it to stop.\n", flush=True)
    if os.environ["WMTS_DEV_USER"] == "local-dev":
        print("WARNING: no Azure sign-in found. Install the Azure CLI and run `az login`, then restart this program.\n", flush=True)
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.create_app().run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
