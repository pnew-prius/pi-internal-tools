# Risks & Alternatives

Rollup across all three source sessions. Each item below cites which finding file has the detail.

## Open / unresolved decisions (block a final recommendation in their area)

1. **Correlator3D throughput at 150MP — unconfirmed.** Entire software-engine cost conclusion swings ~$4.3M
   over 3 years depending on this one number. See `software.md`. Next action: written SimActive sizing quote.
2. **Correlator3D output quality — assumed to pass, not tested.** Same gate that already failed Metashape and
   Pix4D. See `software.md`.
3. **LiDAR workflow — never described/designed.** Explicitly deferred mid-session ("let's focus on RGB
   first") and never resumed. See `hardware.md`. Blocks any LiDAR-specific content in the comprehensive
   report until the current LiDAR workflow is captured from the user.
4. **Two incompatible physical ingest architectures on record** (generic-drive-dock-workstation vs.
   swappable-NVMe-module + Data Box Gateway), two months apart, never explicitly reconciled. See `hardware.md`.
5. **PosPac cloud path** — still GUI-only, no CLI equivalent found (unlike IIQ→JPEG, which now has
   `pi-1000-imageconverter`). Three candidate paths (Applanix APPS service, licensed cloud Windows VM,
   Trimble RTX-PP), none selected.
6. **`CompareContrast-start-Devops` Logic App** — may already be live Azure-side plumbing for the contrast
   step, discovered but never confirmed live or reconciled against the roadmap's own conversion design.
7. **One Button codebase acquisition (Option C)** — no cost conversation has occurred with SkyIntelli yet.
   Rough benchmark-only range ($120k-470k+), not a real quote.

## Confirmed risks (not hypothetical — already observed)

- **Real VM compute cost runs ~3.2x higher than a build-hours-only model** for reasons now fully explained
  (DevOps elastic-pool administrative overhead) — any future bottom-up model needs this context or it will
  look like an unexplained discrepancy again. See `azure-costs.md`.
- **Azure DevOps build-history retention is 30 days.** A full year of historical pipeline data does not exist
  and cannot be recovered — confirmed live (`purgeRuns: 30`). Any future analysis needing historical volume
  must plan around this (raise retention going forward, or rely on a different real data source — invoicing,
  delivered-tile counts).
- **Orphaned/idle Azure resources actively billing**: `imageproc02` (~$42/mo, deallocated VM, disks still
  billing) and `pi-blobsftp` (~$3/mo, same pattern). Small individually, real, actionable, unrelated to this
  project's own scaling work — worth a cleanup pass regardless of what else is decided here.
- **One cost line in the current Permian doc is unreconciled**: Cloud staging storage ($260/mo) has no real
  derivation behind it and doesn't match current actuals (~$83/mo, though not a true comparison since today's
  usage isn't this project's future volume). Flagged, not fixed.
- **Drive "going dark" root cause is a known, fixable Windows power-management default** (USB selective
  suspend) — not a hardware defect. Low-risk, low-cost fix; worth doing regardless of which ingest
  architecture is chosen long-term.
- **Google Drive OAuth-style token expiry pattern** (from an unrelated app, Ranch Manager) is a useful
  general caution: any OAuth-based integration left in a provider's "Testing" mode can silently expire on a
  short cycle (7 days, in that case) — worth a quick check if any new RGB/LiDAR integration uses OAuth.

## Alternatives considered and ruled out

- **Metashape, Pix4D** — already tested in-house, failed quality bar vs. One Button.
- **WebODM** — ruled out on RAM/compute-scaling grounds at large-format resolution.
- **MicMac** — not ruled out, but gated behind two cheap technical pre-checks (GPU-at-scale, RAM-at-150MP)
  that haven't been re-run since initial (discouraging) findings; also a dead community-support channel.
- **10G tether (aircraft→ground)** — rejected in favor of a swappable-module drive pool, so the design works
  identically at every office with no airframe connector or per-parking-position network drop needed.
- **Bulk transfer over onboard Starlink** — too slow for bulk transport (full sortie would take 28-111 hours);
  retained only as a QC/pre-load channel for ~11-35% of a sortie's data in-flight.
- **Rental option for Correlator3D** (3-month node rental) — explicitly removed from consideration once the
  usage horizon was set to >1yr / Azure production expansion (buy-vs-rent breakeven is ~1.01 years).

## Recommended spend framing for the comprehensive report

Given the conditional/open state of several decisions above, the comprehensive report should present cost
ranges and sensitivity tables rather than single committed figures wherever an item above is still open —
specifically the software-engine decision (present the 3-scenario sensitivity table from `software.md`) and
anything LiDAR-related (flag as pending input, don't estimate).
