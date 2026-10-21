"""Start the app locally. DEV and PROD are both offered to your own signed-in user (add --dev-only to hide PROD).
Credential: your `az login` -> Key Vault `pi-geoserver`/`geoadmin` (or set GEOSERVER_PASS to skip Key Vault).
The empty extension dir works around the corrupted costmanagement CLI extension that breaks every `az` call on this machine."""
import os
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
ext = os.path.join(tempfile.gettempdir(), "azext_empty")
os.makedirs(ext, exist_ok=True)
os.environ.setdefault("AZURE_EXTENSION_DIR", ext)
os.environ["WMTS_LOCAL"] = "1"
if not os.environ.get("WMTS_DEV_USER"):
    try:
        os.environ["WMTS_DEV_USER"] = subprocess.run("az account show --query user.name -o tsv", capture_output=True, text=True, shell=True).stdout.strip() or "local-dev"
    except Exception:
        os.environ["WMTS_DEV_USER"] = "local-dev"
if "--dev-only" not in sys.argv and os.environ["WMTS_DEV_USER"] != "local-dev":   # --prod is still accepted and does nothing extra
    # PROD is offered to YOUR signed-in user only (nobody if there is no az sign-in). It is marked with a red PRODUCTION bar; removals need the name typed.
    os.environ["WMTS_ENVS"] = "dev,prod"
    os.environ["WMTS_PROD_USERS"] = os.environ["WMTS_DEV_USER"]
# the production customer-facing scale set that "refresh/restart the customer servers" acts on (needs your Azure rights on it)
os.environ.setdefault("WMTS_PROD_SYNC_TARGET", "vmss:RG_GEOSERVER_SOUTHCENTRALUS/geoserver-vmss")
os.chdir(here)
sys.path.insert(0, here)
import app  # noqa: E402

app.create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), debug=False, threaded=True)
