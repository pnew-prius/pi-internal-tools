# WMTS automation

Automates what is manual today: after a COG is created, publish it to GeoServer and add it to a cached WMTS service.
Status: **validated on dev** (54-COG sequential test, 0 failures). Not deployed. Nothing here has run against prod.

## The model (what a "WMTS service" is)
- One **workspace** per customer project/season (e.g. `COPE-S26`). One store + coverage + layer per COG, named by tile ID.
  Stores point straight at the blob: `cog://https://pigeoserverprod.blob.core.windows.net/sourceimagery/<path>` (path URL-encoded).
- A WMTS service is a GWC-tiled **layer group** whose members are those per-COG layers. Only the group is advertised;
  member layers are hidden (`coverage.advertised=false`) and have no tile layer of their own.
- Gridset `EPSG:3857`, PNG only, pre-seed zoom 0-15; zoom 16+ renders live on first request, then caches.

## Update workflow (per COG, run any time, one at a time) — `add_cog.py`
1. Publish the COG as a layer (hidden). 2. Add it to the group; set group bounds = union(existing, footprint) in EPSG:3857.
3. Widen the tile layer extent. 4. **Truncate** the COG's bounding box (zoom 0-24). 5. **Seed** the same box (zoom 0-15, PNG).
6. Remove stray per-layer tile layers. The function is stateless (reads GeoServer), idempotent (skips existing members), resumable.

## Run the GUI locally (dev GeoServer)
```
python run_local.py        # http://localhost:8000  (needs `az login`; GeoServer password comes from Key Vault pi-geoserver/geoadmin)
python -m pytest -q        # 68 unit tests against a fake GeoServer; no network, no side effects
```
`run_local.py` sets `WMTS_LOCAL=1` (a fake signed-in user; without it the app returns 401 unless Azure sign-in headers are present)
and an empty `AZURE_EXTENSION_DIR` (works around the corrupted costmanagement CLI extension that breaks `az` on this machine).
The page: choose environment, workspace, service (layer group), paste one or many COG blob paths (one per line; paths or full blob URLs), Add.
The list is validated as you type (line numbers, duplicates, clashing layer names, max 100); nothing starts until it is clean. COGs are added one at a time
in pasted order and a failed COG does NOT stop the rest (job ends done / partial / failed; one history row per COG; failed ones can be put back in the box).
**Service type:** WMTS (cached tiles: tile config, bounded truncate, seed z0-15; PNG only) or WMS (live render, no tile cache: same publish + group steps, never keeps a tile layer for the group). A group records its type in group metadata (`wmtsbuilder.service_type`) and keeps it: adding a WMS COG to a WMTS service (or the reverse) is refused. On completion the page shows copyable URLs: WMS capabilities, and for WMTS also the capabilities URL and a tile URL template ({z},{y},{x}).
COGs already in the service are skipped unless 'Refresh' is ticked (re-runs tile config, truncate and seed: repairs a failed add or picks up a replaced file). One add at a time per service (a second returns 409). Dev workspaces whose names exist on prod
are refused (shared tile cache). Environments are enabled by `WMTS_ENVS` (default `dev`). A failed add removes anything it created.

## Files
| File | Purpose |
|---|---|
| `app.py`, `templates/index.html` | Flask UI + JSON API (`/api/jobs`, `/api/workspaces`, `/api/groups`, `/api/service`, `/healthz`) |
| `jobs.py`, `store.py` | one-job-per-service background runner; JSON-lines history (replace with Azure Table/Blob before deploy) |
| `validate.py`, `safety.py` | input rules (path/URL normalizing, no SAS/`..`), prod-name guard |
| `tests/` | pytest suite with `fake_gs.py` (in-memory GeoServer/GWC) |
| `gs_client.py` | requests-based REST client (custom User-Agent: the App Gateway 403s Python's default). Password: `GEOSERVER_PASS` env var, else Key Vault via `DefaultAzureCredential` (az login locally, managed identity in Azure); prod needs `allow_prod=True` |
| `gwc.py` | tile layer XML config, bounded truncate/seed, UTM -> EPSG:3857 footprints |
| `add_cog.py` | the per-COG add workflow + stray tile layer reconcile |
| `probe.py` | tile fetch and uncached WMS ground-truth comparison |
| `run_sequential_test.py` | adds a list of COGs one by one, records metrics and seam checks |
| `final_metrics.py` | step timings, tiles per zoom from blob storage, VM CPU |
| `results/2026-10-13-sequential-ww26/` | raw metrics + `REPORT.md` from the 54-COG test |

Needs: Python 3 (`pip install -r requirements.txt`) and `az login`. No `curl.exe` required (Linux-ready).

## Rules learned (each is enforced in the code)
1. **Dev and prod share ONE GWC tile cache** (`pigeoserverprod/tilecache`). Never test with a workspace/group name that exists on prod.
2. GeoServer is served at the root: use `/rest/...` and `/gwc/rest/...` (not `/geoserver/...`). Prod admin/REST is `imageadmin.priusintelli.com`.
3. New stores need the Azure credential block (encrypted key + Azure range reader); it is copied from an existing store.
4. Blob URLs must be URL-encoded. Coverage native name = file stem (`x-RGB`); layer name = tile ID.
5. Group bounds are NOT recomputed on update; tile layer extent is NOT updated when members are added.
6. GWC layer config must be written as XML (JSON round-trip fails). Matrix IDs on `EPSG:3857` are plain `0`-`24`.
7. Truncate range != seed range: truncate every zoom, because on-demand z16+ tiles go stale at seams.
8. GeoServer re-creates per-layer tile layers in the background; sweep them after every add.
9. `az storage blob list` silently caps at 5,000 unless `--num-results` is raised. Tiles are keyed in blob by the group's internal ID.

## Open items
- **Removing a service**: deleting a workspace/group in GeoServer does NOT delete its cached tiles (verified: 28k orphan tiles stayed in `pigeoserverprod/tilecache`). A future 'remove service' action must truncate the tile cache first (all zooms), then delete. Test tiles were removed by prefix (group internal ID) with `az storage blob delete-batch`.
- A WMS-only group could get a tile layer re-created later by GeoServer; a periodic sweep (`reconcile_stray_tile_layers(..., include_group=True)`) would catch it.
- Thorough-test plan in progress (see below). Defects found by live testing so far, all fixed with regression tests: orphaned store when a COG is unreadable;
  history race (job shown done before it was recorded); the stray-layer sweep deleted OTHER services' tile layers in the same workspace; button enabled with invalid input.
- Seed time grows with group size (first 10 adds 9 s -> last 10 adds 22 s); re-measure at larger sizes.
- Tile responses are `no-cache` (set `EXPIRE_CLIENTS` in `add_cog.py`); no CORS headers (matters for browser clients such as ArcGIS Online).
- GUI not yet deployed. To do before deploying: durable history store (App Service disk is not durable), App Service Authentication restricted to an Entra group
  (header `X-MS-CLIENT-PRINCIPAL-NAME`), managed identity with Key Vault secret-read on `pi-geoserver`, gunicorn start command, a dev-named app on `asp-dev1`.
- v1 takes a pasted blob path (browsing `sourceimagery` needs a delegated VNet subnet the storage firewall trusts; none exists yet).
- The post-add stray-layer sweep adds 3-6 s per add; could be cut by sweeping once per batch.
- Not yet tested: replacing/removing a COG, adds spread over days, prod, ArcGIS Pro client.
- The `geoadmin` password still sits in plaintext in `geoserver_seed_cost.py` / `gsd_cost_table.py` (outside this folder): rotate and move to Key Vault.
- Dev test workspaces `AUTOTEST`, `WMTSTEST` and `GUITEST` still exist on dev; delete after review.
