# Coverage contract and provenance

This map records automated suite coverage and separate repository/manual checks.
Publisher exit alone is not receiver evidence.
HTTP success does not certify browser behavior.

| Stable scenario / surface | Required automated evidence | Separate human obligation | Repository regression tests |
| --- | --- | --- | --- |
| doctor; release provenance gate | Module, distribution, reference revision/status; reject mismatch and suite-time change | Confirm intended candidate | `test_doctor.py`, `test_suites.py` |
| `basic-publication` (quick and release) | Unique received view/sentinel, publisher exit, cleanup | Attached workflow interaction | `test_quick.py` |
| `gallery` | Receiver sentinels, exact table rows, decoded plot PNGs | Layout, formatting, controls | `test_gallery.py` |
| `stream-structured` | Finite JSONL records and drain | Updates and filters | `test_stream_structured.py` |
| `stream-http` | Mixed HTTP/text/traceback event content | Mixed event presentation | `test_stream_structured.py` |
| `stream-python-logs` | Raw Python log records, three validated events, four suggested presentations | Live log controls and suggested views | `test_stream_structured.py` |
| `observe-etl` | Application result, selected observations, capture provenance, drain | Observation presentation | `test_observation.py` |
| `local-watch` | Local text update received | Rendered updates | `test_watch_remote.py` |
| `remote-publish` | Separate publisher content received | Two-machine behavior | `test_watch_remote.py` |
| `remote-watch` | Remote updates, missing source and retained bytes | Hosted content presentation | `test_watch_remote.py` |
| `admission` | Keyed positive control, wrong-key 401, unknown-ID 403 | Security UX | `test_admission_config.py` |
| `outage` | Application result retained, unavailable diagnostic, no unexpected listener | Real network recovery | `test_admission_config.py` |
| `config-discovery` | Disposable create/populate, passive AST side-effect absence, config/name/path precedence | Inspect discovered views in the browser | `test_admission_config.py` |
| `storage-history` | Owned store, restart versus fresh publication, retention, timed freshness | History/Compare/freshness | `test_storage_history.py` |
| `checks-webhook` | Baseline/failure/recovery, local webhook sink, bounded failure | Attention/check controls | `test_checks_webhook.py` |
| `resource-monitor` | Finite real psutil samples, bounded history, decoded plots, cleanup | Longer chart/table session | `test_resource_monitor.py` |
| `weather-demo` | Deterministic local HTTP sample through shared pipeline | Sample presentation and opt-in live source | `test_weather_demo.py` |
| Release aggregation | All 16 required, exit/evidence/cleanup checked, missing or failed evidence nonzero | Sign-off always separate | `test_suites.py` |
| Focused publication/decorator/async/traceback and attached lifecycle examples | Separate repository tests; not additional release scenario IDs | Readability, interaction, traceback controls | `test_focused_examples.py` |
| Fixtures/configs/workspace/process primitives | Separate repository tests; not behavioral release scenario IDs | None inferred | `test_fixtures.py`, `test_current_configs.py`, `test_workspace.py`, `test_lifecycle.py` |
| Core internals, benchmarks, browser automation | Core-owned; no duplicated benchmark thresholds or browser automation | Not certified by examples | Outside this suite |

All 16 named release scenarios are required; quick is the `basic-publication`
subset. `python -m plotsrv_examples list` exposes the executable registry in
`src/plotsrv_examples/suites.py`. See [release semantics](release.md) and the
[manual checklist](manual-checklist.md). Test paths above are relative to
`assurance/tests/`, except `assurance/test_doctor.py`. The matrix records coverage
implementation, not a claim that final integration or manual checks have passed.
Broad watch formats/head-tail/limits, async fault variants, real networking, and
live weather are not certified by the deterministic suite. Historical inspection
below is supplemented by [the reconciliation baseline](final-core-candidate.md).

## Inspected reference

On 2026-09-10, `PLOTSRV_CORE_DIR` was unset and the sibling resolved to
`/home/samane/Projects/plotsrv`, branch `0-8-0-green-sprint-1`, revision
`c4c86d230955af9dff6a1c9c766eeb340859ae43`, with clean Git status. Its
`pyproject.toml` declares version `0.7.0`; branch naming is not package version.
Inspected public lazy exports in `src/plotsrv/__init__.py`, packaging, API/test
locations, and `tests/smoke/smoke-test.sh`. Later behavior-dependent work must
inspect the then-current implementation/tests again.

At initial inspection examples selected editable `../plotsrv` in pyproject and
lockfile, but had no `.venv`; system Python had no installed plotsrv candidate.
This describes initial provenance, not current runtime readiness. Doctor output
is the live observation; source path agreement is not a behavior test or release
sign-off. Installed distribution metadata and imported source can be independently
affected by Python path overrides; doctor reports both without equating metadata
version with proof of source identity.

## Doctor contract

`uv run --no-sync python -B -m plotsrv_examples doctor` emits JSON and returns 0 only when a
valid core checkout and the imported module resolve to the same source initializer.
Missing/unreadable/non-plotsrv references, failed imports and mismatches return 1.
An explicitly empty or invalid `PLOTSRV_CORE_DIR` never silently falls back.
Without an override, the checkout sibling `../plotsrv` is used.

Doctor does not install packages, start services, write configuration or execute
core tests. It disables imported bytecode writes and uses Git without optional
locks. `uv run` may separately prepare the examples environment; after setup,
`uv run --no-sync python -B -m plotsrv_examples doctor` avoids that preparation.
As with any Python invocation, candidate package initialization is executed; use
trusted candidates. Reference inspection never imports the reference by adding it
to Python's path. Wheel candidates are reported as mismatches, with distribution
direct-url/archive provenance when available; no implicit mismatch waiver exists.

Acceptance cases: CASE-01 matching source, CASE-02 different source, CASE-03
unavailable reference, CASE-04 unchanged core, CASE-05 complete legacy mapping,
CASE-06 preserved examples edits. Worker checks are self-reported observations,
not independent acceptance. See `legacy-map.md` for path-level dispositions.
