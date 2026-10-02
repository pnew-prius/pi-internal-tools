# Software / Processing Engine Comparison

Source sessions: "COLMAP and GDAL workflow comparison" (local_386dd322, 2026-08-10 to 2026-08-18 — title is
stale, the conversation moved from an initial COLMAP-vs-GDAL framing to a full One Button / Correlator3D /
MicMac licensing evaluation and never got renamed). Memory: `project_correlator3d_evaluation.md`,
`feedback_validate_dont_assume.md`.

## Status: OPEN — conditional recommendation only

The cost conclusion in this section hinges on one unconfirmed number (Correlator3D's real throughput at
150MP). Present as conditional/sensitivity-based until a written SimActive sizing quote or a real trial on
production imagery lands. **Current standing recommendation: stay on One Button** — see Recommendation below.

## Baseline — One Button (SkyIntelli), current production engine

- Real 2025 total cost: **$41,333.30/yr** (base license + processing charges; user-corrected final figure,
  supersedes an earlier $38,402.07 derivation that had an unexplained $2,931 gap).
- Base license: $19,161/yr. Usage: $0.05/processing-hour, no concurrency cap.
- Real throughput: **17.24–17.25 img/hr/head** — confirmed independently twice from two different real
  datasets (12-tile regression, r²=0.68; 33-tile/9,203-image regression, r²=0.88). This is the single most
  solidly-confirmed number in the whole evaluation — use it as a constant, not a caveat.
- Demonstrated burst capacity: 22 concurrent heads (not a contractual or technical ceiling — Azure scale-set
  max is 25, itself raisable via quota request). Real annual-parity capacity need is closer to **~51 heads**
  (derived from real 2025 spend ÷ $0.05/hr ÷ confirmed throughput) — both systems are undersized against
  real annual volume when sized only to a burst snapshot.
- Confirmed via real build logs: One Button requests a GPU and **silently falls back to CPU** on every run
  (`CUDA driver version is insufficient` → falls back, succeeds). The 17.24 img/hr baseline is therefore a
  CPU-fallback number. A real GPU trial was run in production (per user, 2026-07-30) — throughput gain did
  not justify the added GPU-VM cost, so production stayed on CPU-fallback (`Standard_F16s_v2`, no GPU).
  Ruling out "no GPU" as the dominant explanation for the speed gap vs. Correlator3D.
- All-in real annual cost (license + Azure infra), once correctly computed at real annual-parity scale:
  **~$403,185/yr** ($41,333 license + ~$361,852 Azure compute) — dramatically higher than the license-only
  headline figure. Azure rate used: $0.816/hr (`Standard_F16s_v2`, southcentralus, confirmed via Azure Retail
  Prices API).

## Correlator3D (SimActive) — leading alternative

- Real vendor quote (2026-08-10): **$50,000/license, per processing node, 20% annual maintenance.**
  No rental option is being considered (usage horizon is >1yr / Azure production expansion — ruled out).
- GPU-mandatory (confirmed via SimActive's own whitepaper) — this is a structural requirement, not optional.
- Real published benchmark (whitepaper, primary source read directly, not secondhand): 1,000 images @ 42MP
  in ~1.1hr / <$30 on `Standard_NV36ads_A10_v5` (Azure, southcentralus). This is the one number in the whole
  Correlator3D case that is directly vendor-confirmed.
- **The unconfirmed number**: extrapolating that 42MP benchmark to the team's actual 150MP camera requires
  (a) a linear pixel-count scaling assumption (909 img/hr → 254.5 img/hr) which is optimistic/untested, then
  (b) a 40% conservative haircut applied on top → **working planning estimate: 152.7 img/hr/node.** This
  number is three layers removed from anything measured on real 150MP data.
- Sensitivity / breakeven (this is the number that actually matters for any recommendation):

  | Throughput scenario | img/hr | Cost result vs. One Button |
  |---|---|---|
  | Pessimistic (public FAQ benchmark, unspecified low-end hardware) | 40 | **~2x more expensive** |
  | Breakeven | 81.1 | equal |
  | Working estimate (whitepaper extrapolation − 40% haircut) | 152.7 | **~half the cost** (compute only) |
  | Optimistic (whitepaper extrapolation, no haircut) | 254.5 | cheaper still |

  At real annual-parity node counts (6 nodes, not the burst-sized 3), full 3-year TCO swings by
  **~$4.3M** across this throughput range alone. This is not a minor sensitivity — it is the entire decision.
- Azure VM cost for Correlator3D's recommended SKU: `Standard_NV36ads_A10_v5` = **$3.84/hr** (confirmed live
  via Azure Retail Prices API — replaces an earlier flawed $25.12/hr placeholder that had wrongly bundled a
  specific job's storage/egress cost into a general hourly rate).
- Distributed processing requires a **separate license per VM/node** (confirmed, primary source).
- Vendor's own recommended on-prem hardware (i7/i9, RTX 4070, 16-32GB RAM) **does not map to an Azure SKU** —
  Azure has no RTX 4070-class GPU; datacenter-class only (A10/L4/T4/A100/H100). Note from the whitepaper's own
  chart: the vendor's cited local workstation with an "RTX 4000-series" GPU actually beat every cloud VM
  tested, including the A10 — but Azure doesn't sell that card, so it's not actionable for this evaluation.
- Quality: **ASSUMED to pass per explicit user instruction, NOT independently tested.** This is the same gate
  that already failed Metashape and Pix4D in-house — a real, unquantified risk on the business case.

## MicMac (open-source, IGN/ENSG, CeCILL-B license)

Secondary thread, lower priority than Correlator3D. Two preconditions were "cheaply checked" (web/community
research, no paid trial) and both came back worse than the original framing:
- **GPU**: real `UseGpu` CUDA parameter confirmed to exist in `Malt` (dense matching), but an open,
  unanswered 7+-year-old GitHub issue reports GPU memory overload at exactly the 200-1000+ image counts a
  real production test would use — i.e. likely fine at small scale, unreliable once scaled, a worse failure
  mode than "no GPU" because it could silently pass a small test and break in production.
- **RAM**: confirmed real risk, more specific than first assumed — dense matching itself is fine at 300+
  images, but the *orthomosaic/texturing* stage ("Tawny") is the real RAM killer, and very large orthomosaics
  need re-tiling after the fact. No public benchmark exists at 150MP.
- **Support channel red flag**: the official MicMac community forum domain has lapsed ("may be for sale") —
  no SLA AND apparently no functioning community channel either.
- Licensing pitch ($0/head, scales free) is only an advantage vs. Correlator3D — One Button already scales
  free, so this doesn't move the needle vs. the actual production baseline.
- **Status: do not spend on a real MicMac benchmark** until the GPU-at-scale and RAM-at-150MP questions are
  cheaply answered further (a real small-vs-300-image GPU memory test), per the existing gate table.

## Also evaluated and ruled out

- **Metashape / Pix4D** — already tested in-house, did not match One Button's quality. Ruled out.
- **WebODM** — ruled out on RAM/compute-scaling grounds at large-format resolution before this evaluation
  even started.
- **Acquire the One Button codebase outright** ("Option C") — no cost discussion with SkyIntelli has occurred.
  Rough, low-confidence industry-benchmark scope estimate only (NOT vendor-sourced): $120,000–$470,000+,
  3-9+ months, to fix deprecated ESRI connections, restore image editing / GCP correction, and properly
  engineer GPU utilization. Reverse-breakeven ceiling from license-avoidance alone (0% ongoing maintenance):
  ~$124,000 (3yr) / ~$206,667 (5yr) / ~$413,333 (10yr) at the corrected $41,333.30/yr baseline. The honest
  answer: this could be a good deal or a bad one — there is no way to know without a real SkyIntelli quote.

## Recommendation (current, conditional)

**Stay on One Button.** It is the only option with a fully confirmed, real, end-to-end track record
(real cost, real throughput, demonstrated burst capacity, no per-head fee). Correlator3D's case rests on one
confirmed fact (price) and two still-unconfirmed inputs: the ~153 img/hr throughput estimate and untested
quality. Both need to be replaced with real numbers — a written SimActive sizing quote for 150MP on a named
Azure GPU SKU, and a real quality test — before a switch decision, not a planning assumption, should be made.

**Next concrete action**: request a written SimActive throughput/sizing estimate for 150MP on their
recommended Azure GPU SKU (free, given the existing sales relationship) — see the drafted vendor request in
the source session (asks for: exact SKU/region/specs, single-VM vs. distributed, stage-by-stage timing
breakdown matching the whitepaper's own module breakdown, actual Azure compute cost for the run, and the
real output files for an independent quality check against One Button's result on the same imagery).

## Open items carried into Risks / Implementation Plan

- SimActive sizing quote — not yet sent as of this writing.
- Correlator3D quality — not independently tested (same gate that already failed Metashape/Pix4D).
- SkyIntelli (OB codebase acquisition) — no cost conversation has occurred.
- MicMac GPU-at-scale / RAM-at-150MP — not yet re-tested since the 2026-08-10 cheap-check findings.
