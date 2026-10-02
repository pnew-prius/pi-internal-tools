# Implementation Sequence (draft)

Derived from dependency order across the three source sessions — not yet reviewed/approved by the user.
Mark as draft in the comprehensive report until confirmed.

## Phase 0 — Close open decisions that block everything else

1. Reconcile the two ingest architectures (`hardware.md`, Design A vs. B) — pick one before buying any
   hardware.
2. Gather the current LiDAR workflow description from the user (sensor, local processing, deliverable
   format) — blocks any LiDAR content anywhere else in this report.
3. Send the SimActive sizing-quote request (drafted, see `software.md`) — this is free and doesn't block
   other phases, but should start now given how long vendor turnaround can take.
4. Confirm whether `pi-blobsftp` and `CompareContrast-start-Devops` are live/in-use — cheap to check, avoids
   building redundant infrastructure.

## Phase 1 — Ingest pipeline (cheapest, highest-certainty wins first)

1. Fix the confirmed root cause of drive "going dark" (disable USB selective suspend) — zero cost, fixes a
   real existing problem immediately regardless of any other decision.
2. Stand up the drive-tracking process fix (two-bin system + numbered drive log) — zero/low cost, same
   reasoning.
3. Build/deploy whichever ingest architecture Phase 0.1 selects.
4. Wire `pi-1000-imageconverter` (already built, free-licensed) into production for IIQ→JPEG — the one
   processing step that's already de-risked (real CLI tool exists, cost already derived:
   ~$300-420/mo at current volume, see `project_rgb_roadmap` / `pi-1000-imageconverter` memory).

## Phase 2 — Processing engine decision

1. Hold at One Button (current recommendation) until SimActive's quote + a quality test land.
2. If/when a real SimActive number arrives: re-run the sensitivity table in `software.md` with the real
   figure, and only then make a capital commitment.
3. PosPac cloud path — separately scope the three candidate paths (Applanix APPS, licensed cloud Windows VM,
   Trimble RTX-PP) once the ingest pipeline (Phase 1) is stable, since this doesn't block ingest or conversion.

## Phase 3 — Cost tracking / prediction system (standing directive, not yet started)

Per `project_rgb_cost_intelligence`: once per-project cost tagging exists in production, build toward a real
spend-by-area/resolution/camera prediction system, validated against live Cost Management data rather than
bottom-up modeling alone. This is a distinct deliverable from the comprehensive report itself.

## Cost summary by phase (placeholder — fill in once Phase 0 decisions land)

| Phase | One-time | Recurring | Depends on |
|---|---|---|---|
| 0 — Decisions | $0 (research/quote requests only) | — | none |
| 1 — Ingest | TBD (depends on Design A vs B choice, `hardware.md`) | TBD | Phase 0.1 |
| 2 — Engine | $0 now (stay on OB) / up to ~$300k+ if switching (`software.md`) | current OB: ~$41k/yr license, all-in ~$403k/yr (`software.md`) | Phase 0.3 |
| 3 — Cost system | Not yet scoped | — | Phase 1 live in production |

LiDAR-equivalent phases cannot be filled in until Phase 0.2 is resolved.
