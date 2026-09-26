# PHASE-04 worker integration evidence

2026-09-10. These are worker observations, not independent acceptance. Prider's
managed review remains separate. No release, commit, tag, push or deployment was
performed. Manual browser/TUI and external checks remain pending; full release
sign-off is withheld.

## Candidate and reference

The explicitly inspected sibling `/home/samane/Projects/plotsrv` remained clean
at `c4c86d230955af9dff6a1c9c766eeb340859ae43`, branch
`0-8-0-green-sprint-1`, declared version `0.7.0`. `PLOTSRV_CORE_DIR` was unset.
Doctor imported `/home/samane/Projects/plotsrv/src/plotsrv/__init__.py` using the
examples `.venv/bin/python3`. Installed core metadata is version `0.7.0` with
editable direct URL `file:///home/samane/Projects/plotsrv`.

The final post-fix release run, 15:54:17–15:56:03 UTC, passed all 15 required
scenarios. Its initial, per-scenario and final provenance matched. It reported
`automated_status: passed`, `manual_status: pending`, and
`release_signoff: withheld`. Examples project/lock/installed metadata is 2.0.0.

## Review finding addressed

The release SIGALRM deadline could interrupt child creation before ownership was
registered, or interrupt cleanup itself. Lifecycle ownership now defers SIGALRM
alongside SIGINT/SIGTERM during launch and bounded reaping, delivering the pending
signal afterward. This preserves failure while ensuring the child is owned and
reaped. Regression tests inject the deadline immediately after Popen and at the
start of cleanup. All 24 targeted lifecycle/suite tests passed, including the
live timeout check. The full release suite was rerun after this fix.

## Other evidence and scope

- Doctor and quick passed. A deliberate release missing-evidence drill exited 1,
  identified basic-publication failure and left other requirements `not_run`.
- Compilation of `src`, `examples`, and `demos` passed, including a post-fix run.
- Lock validation, project/lock/installed version comparison, whitespace checks,
  and local Markdown link checks passed.
- Final migration dispositions remain in `legacy-map.md`; retained smoke alias,
  failure propagation and metadata are covered by public-readiness tests.
- Targeted public-source private-address/key/token scans found no matches, and
  Git lists no tracked env secrets, bytecode, stores, run state or agent support.
  This is bounded inspection, not a guarantee against every secret encoding.
- Core working-tree and staged diffs remained empty. Git/source observations do
  not certify ignored core files or substitute for an independent audit.

`uv run pytest -q` completed with **141 passed in 318.88 seconds**, without
failures or skips. That run began before the lifecycle fix; the subsequent
24-test lifecycle/suite run includes both newly added race regression cases,
and the full release rerun used the fixed code. No independent review result is
claimed by this worker report.
