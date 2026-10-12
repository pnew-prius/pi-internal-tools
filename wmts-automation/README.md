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

## Files
| File | Purpose |
|---|---|
| `gs_client.py` | curl-based REST client. Credentials from `GEOSERVER_PASS`; prod needs `allow_prod=True` |
| `gwc.py` | tile layer XML config, bounded truncate/seed, UTM -> EPSG:3857 footprints |
| `add_cog.py` | the per-COG add workflow + stray tile layer reconcile |
| `probe.py` | tile fetch and uncached WMS ground-truth comparison |
| `run_sequential_test.py` | adds a list of COGs one by one, records metrics and seam checks |
| `final_metrics.py` | step timings, tiles per zoom from blob storage, VM CPU |
| `results/2026-10-13-sequential-ww26/` | raw metrics + `REPORT.md` from the 54-COG test |

Needs: Python 3 with `pyproj` (and `pillow` for image checks), `curl.exe`, Azure CLI logged in. Set `GEOSERVER_PASS` first.

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
- Seed time grows with group size (first 10 adds 9 s -> last 10 adds 22 s); re-measure at larger sizes.
- Tile responses are `no-cache` (set `EXPIRE_CLIENTS` in `add_cog.py`); no CORS headers (matters for browser clients such as ArcGIS Online).
- Not yet tested: replacing/removing a COG, adds spread over days, prod, ArcGIS Pro client.
- The `geoadmin` password still sits in plaintext in `geoserver_seed_cost.py` / `gsd_cost_table.py` (outside this folder): rotate and move to Key Vault.
- Dev test workspaces `AUTOTEST` and `WMTSTEST` still exist on dev; delete after review.
