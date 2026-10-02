# Azure Cost Validation Findings

Source: "RGB data processing roadmap" session (active, 2026-09-09 → present). Memory:
`project_rgb_cost_intelligence.md`, `reference_vm_quota_ceilings.md`, `project_rgb_roadmap.md`.
Full itemized recurring-cost tables already exist in the delivered doc
`pi-internal-tools/rgb-pipeline-roadmap/exec_summary/Quarterly_Permian_Collection_Costs_Timelines.docx` —
this file summarizes the validated *methodology and findings* behind those numbers rather than re-deriving
them; the comprehensive report's Azure Costs section should reference that doc for full detail.

## Standing directive

Validate RGB pipeline cost work against live Azure Cost Management data as the authoritative source, not
just bottom-up per-image modeling — for this project and future ones. Long-term goal (not yet started):
aggregate real spend over time, correlated with project metadata (area, resolution, camera), to predict
future project costs. Concretely buildable once per-project cost tagging exists in production.

## Key validated finding: bottom-up compute models undercount real spend — now fully explained

Real Cost Management MTD spend (Sept 1-15 2026) for `rg_imageryprocessing_southcentralus` = **$180.93-181.45**
vs. a build-hours-only model's $20.34 — an initial ~7-9x apparent gap, since resolved by itemizing:

| Category | 15-day real cost | What it is |
|---|---|---|
| Mosaic VM compute (`imageproc-vmss`) | $47.74 | Real compute — ~3.2x the build-hours model alone |
| GDAL VM compute (`gdalproc-vmss`) | $16.80 | Real compute |
| `piimageprocessing` storage | $41.49 | Raw staging storage — never modeled per-image |
| `imageproc02` orphaned disks | $42.36 | **Real waste** — VM deallocated/idle, disks still bill ~$85/mo. Actionable, unrelated to this project. |
| `pi-blobsftp` orphaned disk+IP | $2.94 | Same pattern, smaller |
| Private endpoints | $7.06 | Real networking cost |
| VMSS per-instance temp disks | $17.72 | Real per-build overhead, never modeled per-image |

**The remaining ~3.2x gap in VM compute itself is DevOps elastic-pool administrative overhead, not job
overhead** — confirmed via Activity Log caller identity: Azure DevOps's own service principal performs
scheduled pool maintenance (an exact every-2-hour cycle observed) on both VM pools, independent of real job
volume. This is real, recurring, shared-platform overhead that exists whether or not this project runs any
jobs — correctly NOT apportioned into any single project's per-image rate.

**How to apply**: per-image cost models are correct to exclude this; don't try to "fix" the gap by adding a
per-run overhead constant. If this overhead is ever needed as its own line (e.g. an org-wide DevOps
infrastructure conversation), it's a shared platform cost, not a per-project one.

## Real, confirmed rates (Azure Retail Prices API — public, no auth required)

| SKU | Role | Rate (southcentralus) |
|---|---|---|
| Standard_F16s_v2 | One Button mosaic compute | $0.816/hr |
| Standard_D16ds_v4 | GDAL pool | $1.175/hr |
| Standard_NV36ads_A10_v5 | Correlator3D's benchmark VM (full A10) | $3.84/hr |
| Standard_NV6ads_A10_v5 | Smaller A10 slice | $0.545/hr |
| Azure Bastion, Basic / Standard | (hardware/ingest section) | $0.19/hr / $0.29/hr |

One Button's blended mosaic rate: **$0.866/hr** ($0.816 compute + real $0.05/hr license usage). A prior
$1.316/hr figure double-counted a $0.50/hr license placeholder against the real $1,597/mo+$0.05/hr contract
— corrected 2026-09-15.

## Real VM parallelism ceilings (not VMSS `sku.capacity`, which is not a cap)

The true ceiling is subscription-level vCPU quota per VM family, confirmed live via `az vm list-usage`:
- **Standard FSv2** (mosaic pool): 576 vCPU limit, 40 in use elsewhere → **~33 more F16s_v2 VMs of headroom.**
- **Standard DDSv4** (GDAL pool): 256 vCPU limit, 8 in use → **~15 more D16ds_v4 VMs of headroom.**

These are point-in-time readings, not contractual ceilings — re-check before relying on them for a real
production burst; other subscription workloads sharing the same families can move the number. Total compute
cost is unaffected by VM count (fixed by volume ÷ per-image rate) — only turnaround time changes, so there is
no cost reason to run fewer VMs than this headroom allows.

**Real GDAL per-VM throughput** (from actual historical build data, one clear multi-run outlier excluded):
**598.5-895.9 img/hr/VM.**

**Real mosaic per-VM throughput**: 17.24-17.98 img/hr/VM — same confirmed figure used in the Software
Comparison findings (`software.md`).

## Delivery storage — real accumulation model, not a flat cost

Five historical Permian seasonal deliveries (spring 2023-2026) remain in `pigeoserverprod/sourceimagery`,
none ever purged. Real measured stats: 238-291 tiles/delivery (avg ~259), 6.51-7.05 GB/tile average (avg
~6.52 GB), real confirmed 430-image max tile size. **Finding: delivery storage grows every quarter the
project operates** — it is not a flat monthly line. Real added cost ~$37-107/mo per quarter depending on
resolution/camera; real steady-state cost after collection ends (1 year / 4 quarters of accumulation) ~$147-
427/mo. Rate used: $0.018/GB/month, confirmed live against Azure Retail Prices.

## Storage line-item validation (completeness check, 2026-09-15)

- **Delivery storage & CDN ($1,457/mo)** — real, validated twice against live Cost Management pulls a month
  apart. Trustworthy.
- **Image server (~$896/mo)** — real GeoServer infra, cross-checked live (~$845/mo MTD extrapolated).
  Trustworthy.
- **Cloud staging storage ($260/mo)** — **flagged, likely wrong.** No real GB-usage derivation was ever found
  behind this figure; real current actual for the account is ~$83/mo (though that reflects today's
  non-Permian usage, not this project's real future volume). Carried in the Permian doc as an unreconciled
  placeholder, not silently replaced with an equally-unverified new guess.

## Real API access pattern (for any future live cost pull)

Cost Management Query API works. Known gotcha: the installed `costmanagement` CLI extension is corrupted on
this machine (breaks every `az` command since the CLI loads all extension metadata first) — workaround is
setting `AZURE_EXTENSION_DIR` to an empty writable folder before calling `az`, which skips the broken
extension. Full connection details (subscription/tenant IDs, DevOps org URLs, this workaround) are
consolidated in `reference_system_connections.md` — check there before re-discovering any of this.

```json
POST https://management.azure.com/subscriptions/{sub}/providers/Microsoft.CostManagement/query?api-version=2023-11-01
{
  "type": "ActualCost", "timeframe": "MonthToDate",
  "dataset": { "granularity": "None",
    "aggregation": { "totalCost": { "name": "PreTaxCost", "function": "Sum" } },
    "grouping": [{ "type": "Dimension", "name": "ResourceGroupName" }] }
}
```
Bearer token: `az account get-access-token --resource https://management.azure.com/`. Rate-limited on a
`clienttype` quota that grows its retry-after with concurrent use from other sessions on the same account —
don't retry in a tight loop, wait the real retry-after value.
