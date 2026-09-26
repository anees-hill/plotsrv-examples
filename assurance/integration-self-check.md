# Mandatory integration/adversarial worker self-check

PHASE-INTEGRATION-SELF-CHECK, 2026-09-10. All checks below are worker-reported;
they do not constitute independent acceptance. No source repairs were needed
during this phase. No commit, tag, push, deployment or release was performed.

## Fresh execution evidence

- `uv run python -m plotsrv_examples doctor`: exit 0, matching source checkout.
- `uv run python -m plotsrv_examples check quick`: exit 0, received evidence and
  owned-child cleanup confirmed.
- `uv run python -m plotsrv_examples check release`: exit 0, all 15 required
  scenarios passed, 15:58:55–16:00:52 UTC. Manual status remained pending and
  release sign-off withheld.
- `uv run pytest -q`: **143 passed in 323.53 seconds**, no skips or failures,
  against the completed implementation including both alarm-race regressions.
- `uv run python -m compileall -q src examples demos`: exit 0.
- Release with `--fault missing-evidence`: expected exit 1, missing logical view
  identified in basic-publication, remaining 14 requirements `not_run`.
- Lock/version checks and whitespace checks passed. All 95 baseline tracked
  paths matched the final legacy map's path/group dispositions.

Reference: `/home/samane/Projects/plotsrv`, selected by sibling fallback with
`PLOTSRV_CORE_DIR` unset; clean HEAD
`c4c86d230955af9dff6a1c9c766eeb340859ae43`, branch
`0-8-0-green-sprint-1`, declared version `0.7.0`.
Runtime: examples `.venv/bin/python3`, importing
`/home/samane/Projects/plotsrv/src/plotsrv/__init__.py`, installed core `0.7.0`
with editable direct URL `file:///home/samane/Projects/plotsrv`.
Release initial/per-scenario/final provenance agreed. Final Git HEAD/status and
staged/working-tree diff checks matched the clean baseline. This observes core
Git/source state, not ignored files or an independent audit of earlier activity.

## Contract observations

| Requirement | Worker status | Evidence |
| --- | --- | --- |
| INV-01 | passed | Required failure/dependency/timeout/interruption/cleanup tests and deliberate release failure; all run in the final test suite. |
| INV-02 | passed | Quick/release manual status and reconstructed checklist remain separate. |
| INV-03 | passed | All 95 baseline tracked paths have migration dispositions. |
| INV-04 | passed | Targeted source privacy scan found no matching private addresses/keys/tokens; tracked runtime/secret path inventory empty. |
| INV-05 | passed | Project, lock, installed distribution and README agree on 2.0.0 and explicit candidate workflow. |
| INV-06 | passed | Exact inspected reference and imported candidate above; live release provenance reconciled. |
| INV-07 | passed | Core revision/clean status unchanged; both diffs empty. |
| CASE-01 | passed | All 15 deterministic scenarios passed with remaining manual sign-off reported. |
| CASE-02 | passed | Deliberately absent received view produced exit 1 and named failing evidence. |
| CASE-03 | passed | Missing-dependency and unavailable-reference regression cases pass without silent success. |
| CASE-04 | passed | Automated pass retains pending manual status and withheld sign-off. |
| CASE-05 | passed | Removed paths included in the 95-path migration-map comparison. |
| CASE-06 | passed | No checked private/generated material found in public-source and tracked-path inspection. |
| CASE-07 | passed | Metadata/lock/setup checks and public-readiness regression tests pass. |
| CASE-08 | passed | Doctor mismatch, pre-launch rejection and suite provenance-change regression cases pass. |
| CASE-09 | passed | Final core Git/source comparison matches the clean initial state. |

Privacy evidence is a bounded pattern/path inspection, not a guarantee against
every possible secret encoding. Manual browser/TUI/live-source checks remain
pending. Prider owns independent review and lifecycle advancement.
