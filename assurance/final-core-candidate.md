# Final core/candidate reconciliation

PHASE-01 inspection on 2026-09-10. This is worker-reported provenance evidence,
not independent verification or release sign-off. Later integration must capture
fresh provenance for the candidate actually executed; this snapshot cannot stand
in for that evidence.

## Inspected reference and imported candidate

`PLOTSRV_CORE_DIR` was unset. The sibling fallback resolved to the intended
reference `/home/samane/Projects/plotsrv`:

- HEAD: `c4c86d230955af9dff6a1c9c766eeb340859ae43`.
- Branch: `0-8-0-green-sprint-1`.
- Git status, including untracked files: clean before and after this unit.
- Declared package version: `0.7.0` (the branch name is not a version).

`uv run python -m plotsrv_examples doctor` exited 0 with readiness `ready`,
relationship `matching source checkout`, and no problems. It executed Python
`/home/samane/Projects/plotsrv-examples/.venv/bin/python3` and imported
`/home/samane/Projects/plotsrv/src/plotsrv/__init__.py`. Installed distribution
metadata reports version `0.7.0`, located in the examples environment's
`.venv/lib/python3.11/site-packages`, with direct URL
`file:///home/samane/Projects/plotsrv` and `editable: true`. The candidate's
checkout revision, branch and clean status equal the inspected reference.

No material mismatch was found. The revision also matches the earlier source
inspection recorded in `coverage.md`; this conclusion comes from a fresh Git
and runtime inspection, not from assuming the earlier record is current.
No installation, source edit, commit, tag, push or deployment of core was needed.

## Mismatch gate and bounded verification

The existing doctor rejects missing, invalid or different references/candidates
with exit 1. `require_candidate()` rejects a blocked report before scenario
launch. No mismatch waiver was added; a separately installed wheel remains
blocked by the existing source-identity policy.

`PYTHONDONTWRITEBYTECODE=1 uv run pytest -q assurance/test_doctor.py
assurance/tests/test_quick.py::test_different_imported_candidate_blocks_before_launch`
passed all six tests. These cover matching source without fixture-core writes,
different source, missing reference, empty override, missing runtime, and a
different imported candidate rejected before workspace/receiver creation.

Post-check Git HEAD was unchanged; porcelain status was empty and both working
tree and staged diffs exited 0. This observes Git/source state for this unit;
it does not certify ignored files or establish the entire job's earlier state.

Quick/release behavior, complete repository verification and manual sign-off
remain for their assigned phases. Repeat doctor and the core before/after
comparison during final integration, recording any new revision or dirty state
and reconciling it before attributing release evidence to this baseline.
