# Sequential add test: WW26-All (dev, 2026-10-13)

54 COGs (`sourceimagery/Prius Intelli/automation-test/wmts/`, ww26-01..54 without 10, plus 38a/38b; ~103 GB; 28 in EPSG:32614,
26 in EPSG:32613) added one at a time to layer group `WMTSTEST:WW26-All` with `add_cog`. EPSG:3857, PNG only, pre-seed z0-15.
Result: 54 of 54 succeeded in 1,397 s (23.3 min). Raw data: `metrics_seq.json`, `final_metrics.json`.

| Step | Mean per COG | Total |
|---|---|---|
| Publish + hide | 1.5 s | 80 s |
| Group update | 0.24 s | 13 s |
| Tile layer config | 0.22 s | 12 s |
| Truncate (bbox, z0-24) | 3.9 s | 211 s |
| Seed (bbox, z0-15) | 16.4 s | 885 s |

Per add: mean 25.9 s (11-44 s) including checks. Seed time rose from 9.3 s (first 10 adds) to 21.9 s (last 10).
Stored: 19,126 tiles, 190 MB, all PNG on EPSG:3857 (z15: 12,456 tiles, 135 MB). Seed jobs summed to 37,406 tiles (overlaps re-rendered).
Dev VM `pi-geosvrd01`: CPU avg 9.5%, peak 17.8%.
Adjoining: 43 of 54 adds had neighbors (56 overlaps, 1 touch). 112/112 seam probes matched an uncached live render.
108/108 new-COG center probes were cache HITs (94 had imagery at the sampled point; the rest fell on empty pixels, not investigated).
Zoom 16 (not pre-seeded): first request 3.1 s live render, then 0.16 s HIT. JPEG request: 400 (as intended).
Issue found: 2 of 54 per-layer tile layers (ww26-03, ww26-44) were re-created by GeoServer after deletion; now swept by `reconcile_stray_tile_layers`.
