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
3. Widen the tile layer extent. 4. **Truncate** the COG's bounding box (zoom 0-24). 5. **Seed** (zoom 0-15, PNG) the COG's footprint **and the
footprints of the members that touch it** (see rule 10). A batch in the app defers seeding and does it **once after the last COG**
(`seed_affected`), shown on the page as "Seed service tiles".
6. Remove stray per-layer tile layers. The function is stateless (reads GeoServer), idempotent (skips existing members), resumable.

## Run the GUI locally (dev GeoServer)
```
python run_local.py        # http://localhost:8000  (needs `az login`; GeoServer password comes from Key Vault pi-geoserver/geoadmin)
python -m pytest -q        # 127 unit tests against a fake GeoServer; no network, no side effects
```
`run_local.py` sets `WMTS_LOCAL=1` (a fake signed-in user; without it the app returns 401 unless Azure sign-in headers are present)
and an empty `AZURE_EXTENSION_DIR` (works around the corrupted costmanagement CLI extension that breaks `az` on this machine).
The page: choose environment, workspace, service (layer group), paste one or many COG blob paths (one per line; paths or full blob URLs), Add.
The list is validated as you type (line numbers, duplicates, clashing layer names, max 100); nothing starts until it is clean. COGs are added one at a time
in pasted order and a failed COG does NOT stop the rest (job ends done / partial / failed; one history row per COG; failed ones can be put back in the box).
**Service type:** WMTS (cached tiles: tile config, bounded truncate, seed z0-15; PNG only) or WMS (live render, no tile cache: same publish + group steps, never keeps a tile layer for the group). A group records its type in group metadata (`wmtsbuilder.service_type`) and keeps it: adding a WMS COG to a WMTS service (or the reverse) is refused. On completion the page shows copyable URLs: WMS capabilities, and for WMTS also the capabilities URL and a tile URL template ({z},{y},{x}).
COGs already in the service are skipped unless 'Refresh' is ticked (re-runs tile config, truncate and seed: repairs a failed add or picks up a replaced file). One add at a time per service (a second returns 409). Dev workspaces whose names exist on prod
are refused (shared tile cache). Environments are enabled by `WMTS_ENVS` (default `dev`). A failed add removes anything it created.

## PROD in the GUI (fail-closed)
The Environment dropdown offers **prod** only when ALL of these hold: `WMTS_ENVS` includes `prod` AND the signed-in user is in `WMTS_PROD_USERS`
(comma-separated emails) or in the Entra group `WMTS_PROD_GROUP_ID` (read from the App Service sign-in claims). If prod is requested but nobody is
authorized, it is silently dropped. Locally: `python run_local.py --prod` offers prod to your own user only.
Rules on prod: every add needs the "I understand this changes PRODUCTION" box (`confirm_prod`); removal needs `workspace:service` typed; at most
`WMTS_PROD_MAX_BATCH` (25) COGs per run; the app only modifies services IT created (marker in group metadata; hand-built services are refused);
seeding uses 2 threads (dev 4) so live traffic is not starved. Prod access in code is a thread-local session (`gs_client.prod_access(write=...)`):
without it every prod call raises. Red banner + dark header make the environment unmistakable. Prod writes have NOT been exercised against the
real prod server yet (unit tests use a separate fake prod; live tests are read-only on prod).

## Prod: updating the customer-facing GeoServer (`instance_sync.py`)
On prod the app writes through the ADMIN node (`imageadmin` -> VM `pi-geoserver01`), but customers are served by the scale set `geoserver-vmss`
(`imageservices`). They are separate GeoServer processes sharing a data directory, so the scale-set instances keep their old in-memory configuration
until reloaded or restarted: clients (QGIS/ArcGIS) "don't see the change". Dev is ONE VM serving both, so dev never needs this (verified).
Once per prod job (after the last COG is seeded; also after a prod removal), under the service lock, in the mode chosen on the page:
- **reload** (default): per instance, in parallel, zero downtime. Azure managed Run Command runs GeoServer's REST reload (+ GWC reload) ON the instance.
  The GeoServer password is a PROTECTED parameter (never in the script); the run command is deleted afterwards and the deletion is confirmed.
- **restart**: rolling, one instance at a time, waiting for each to report exactly `HealthState/healthy`; stops if one never does.
- **none**: skip (the page then warns that customers will not see the change until someone does it).
A sync failure never fails the COGs; it is shown loudly ("customers may NOT see this change yet") and recorded in history.
Config: `WMTS_PROD_SYNC_TARGET=vmss:RG_GEOSERVER_SOUTHCENTRALUS/geoserver-vmss` (unset = sync reports "not configured"), `WMTS_SUBSCRIPTION`.
Needs the app's identity to hold **Virtual Machine Contributor on `geoserver-vmss`** (Azure change, not done). Verified for real on the DEV VM only
(`live_tests -m slow`): ~1.5 min per reload (Azure schedules the command). NEVER run against prod without explicit approval.

## Live test suite (real DEV GeoServer; opt-in)
```
set WMTS_LIVE=1
python -m pytest live_tests -m "live and not slow" -v      # ~4 min: 11 tests
python -m pytest live_tests -m slow -v -s                  # 54-COG WMS batch through the app (scale)
```
Each test builds in a brand-new throwaway workspace (name checked against prod) and tears it down with `remove_service` (truncates the tile cache, deletes the
group and layers, deletes the workspace) and then asserts NO tiles are left in the shared cache. Covers: adjoining-COG seams vs an uncached render, WMS never grows a
tile layer, batch carries on past a missing file, refresh repairs a failed add, two services built at once in one workspace, two app instances adding to the same
service (concurrent writers), kill the process mid-add then refresh, remove-service leaves no orphan tiles, prod cannot be written, and the prod
path through the app is read-only and refuses unconfirmed writes (the suite NEVER writes to prod).

## Files
| File | Purpose |
|---|---|
| `app.py`, `templates/index.html` | Flask UI + JSON API (`/api/jobs`, `/api/workspaces`, `/api/groups`, `/api/service`, `/healthz`) |
| `jobs.py`, `store.py` | one-job-per-service background runner; JSON-lines history (replace with Azure Table/Blob before deploy) |
| `remove_service.py` | remove a service properly: truncate tile cache (all zooms) BEFORE deleting; keeps layers another group still uses |
| `live_tests/` | opt-in live suite (above) |
| `wsgi.py`, `gunicorn.conf.py`, `startup.sh` | production entry point; ONE worker on purpose (jobs/locks are in memory) |
| `../.github/workflows/wmts-automation-tests.yml` | runs the unit suite on Linux when pushed (this machine has no WSL/Docker) |
| `instance_sync.py` | prod: reload/restart the customer-facing scale set after a run (Azure Run Command / ARM REST) |
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
10. **Seed each COG's footprint plus its neighbours, never the group's bounding rectangle.** Dev experiments 2026-10-15 (throwaway services, tiles counted
    in the blob cache): adding a member to the group does NOT empty its cache (653 -> 653 tiles; also with the tile layer disabled, with a nested
    group, and with a bounds-only change). But a COG's bounded truncate also removes tiles along the seams of the COGs next to it, and seeding only
    the new COG's own box does not bring them back: 4 adjoining COGs seeded one at a time were missing 144 tiles inside the earlier footprints
    (footprints 1-3 missing 80/16/48). Adding all four first (every truncate) and then seeding each footprint once left 0 missing. Seeding the
    group's whole bounding rectangle was tried and rejected: 2,252 -> 6,458 tiles, and a sample of the extra tiles was fully transparent (empty
    space between COGs). Verify with `live_tests::test_batch_and_single_add_leave_every_footprint_fully_seeded` (re-seeding any footprint finds nothing).
    GWC lists a seed task only once it is scheduled, so `wait_seed_idle` waits for the task to appear before treating an empty list as finished.
    (An earlier note here claimed GeoServer wipes the whole cache when a member is added; that was not reproduced and has been removed.)

## Open items
- Fixed 2026-10-13 (found by a user's 10-COG batch that stopped after 1 while reporting 'Done'): a history-save failure (deleted `data/` folder) aborted the whole batch, and COGs that never ran were reported as done. Now history is best-effort (folder recreated on save, failures noted but never fatal) and any COG that did not run is marked FAILED ('Not run') so the job can never claim success it did not have. Regression tests reproduce both.
- **Removing a service**: deleting a workspace/group in GeoServer does NOT delete its cached tiles (verified: 28k orphan tiles stayed in `pigeoserverprod/tilecache`). `remove_service.py` truncates first (verified live: 0 tiles left). It is not wired into the UI yet.
- **Concurrent writers** (two App Service instances): GeoServer has no compare-and-swap; `put_member_in_group` re-reads, retries a lost creation race as an update and verifies membership/bounds afterwards, and `sync_tile_extent` re-widens the tile extent. Verified live with two simultaneous adds. For stronger guarantees use ONE instance/worker, or add a blob-lease lock on a small dedicated storage account (which the app also needs for durable history).
- **Linux parity untested** (no WSL/Docker here). The workflow file runs the unit suite and imports `wsgi` on ubuntu as soon as the repo is pushed; the real check is the first deploy.
- **CORS**: tile/capabilities responses carry no `Access-Control-Allow-Origin` (matters for browser-based clients such as ArcGIS Online). That is a GeoServer/App Gateway setting, not this app. Client cache time is set per service (`WMTS_EXPIRE_CLIENTS`, default 600 s).
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

## Deploying to Azure (NOT done; each needs an Azure change)
1. Web app on `asp-dev1` (Linux, Python), startup command `sh startup.sh`. App settings: `WMTS_ENVS=dev` (do NOT set `WMTS_LOCAL`). Keep to ONE instance/worker.
2. App Service Authentication (Microsoft Entra), restricted to a security group. The app trusts `X-MS-CLIENT-PRINCIPAL-NAME`, which is only safe behind that setting.
3. Managed identity with `get` on secret `geoadmin` in Key Vault `pi-geoserver`.
4. Durable history: replace `store.py`'s JSON-lines file (App Service disk is not durable) with a small dedicated storage account (Table/Blob); the same account can host a blob-lease lock if more than one instance is ever needed.
5. Smoke test on the deployed app, then run `live_tests` pointed at it.

## Package it for another Windows machine
`pwsh -File build_exe.ps1` builds `dist\wmts-builder-<commit>.zip` (about 25 MB; a throwaway `.build-venv` is used, nothing is installed system-wide).
Unzip it anywhere writable on the other machine and run `wmts-builder.exe` (add `--prod` to also offer PROD to your own user). The other machine
needs the Azure CLI and `az login` with access to Key Vault `pi-geoserver` (the GeoServer password is read from there, never stored). `INSTALL.txt`
inside the zip says the same in plain terms. Verified 2026-10-15 from a fresh folder: page, Key Vault credential, dev workspaces, one real add + removal.
Not signed, so Windows SmartScreen shows a one-time warning. `exe_main.py` is the entry point; history is kept in `data\` next to the exe.