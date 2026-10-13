"""Start the app locally against the DEV GeoServer (add --prod to also offer PROD to your own user).
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
if "--prod" in sys.argv:
    # opt-in: offer PROD in the Environment dropdown to YOUR signed-in user only. Every prod change still needs the confirmation box.
    os.environ["WMTS_ENVS"] = "dev,prod"
    os.environ["WMTS_PROD_USERS"] = os.environ["WMTS_DEV_USER"]
os.chdir(here)
sys.path.insert(0, here)
import app  # noqa: E402

app.create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), debug=False, threaded=True)
