# Final legacy migration map

Baseline: examples `429a0226c1ee1287723f6b513031bb14c50b026e`.
These are final PHASE-03 dispositions. Directory/glob rows cover every baseline
tracked descendant unless a narrower row overrides them. A retired profile does
not imply its full historical behavior is certified by a replacement.

| Baseline path | Final disposition | Preserved purpose / explicit limitation |
| --- | --- | --- |
| `src/smoke-tests/basic-smoke-test.py` | Retain compatibility launcher | External core smoke host/port/config/delay/custom publisher options; serve with selected interpreter, resolve both object-module aliases, propagate publisher failure. No fixture-directory prerequisite. |
| `src/smoke-tests/python_objs.py` | Retain adapter | Independent `examples/objects.py` public publisher. |
| `src/smoke-tests/python_objs_w_stream.py` | Retain finite companion | Object gallery plus bounded JSONL stream, drain/close checks; deterministic stream assurance is in release. |
| `src/smoke-tests/tracebacks.py` | Replace with adapter | `examples/exceptions.py` explicit/captured/decorated publication; browser/security inspection remains manual. |
| `src/smoke-tests/__init__.py` | Retain | Package marker for the retained stream companion import. |
| `src/launchers/python-objs/00-python-objs.sh` | Retain gallery adapter | Bounded gallery; mixed watch fixtures remain available separately. |
| `src/launchers/python-objs/01-python-objs.sh`, `02-python-objs.sh` | Retain exit-2 migration notices | Minimal/rich gallery purpose in current minimal config/gallery; rich/simple UI remains manual. |
| `src/launchers/python-objs/03-python-objs.sh` | Retain exit-2 notice | Current bounded config and generated fixtures retain limits purpose; broad watch formats/head-tail combinations are not release-certified. |
| `src/launchers/python-objs/04-python-objs.sh` | Retain exit-2 notice | Owned `storage-history` covers retention/restart/freshness. |
| `src/launchers/python-objs/05-python-objs.sh` | Retain exit-2 notice | Current keyed/catalogue configs and `admission`; not a production deployment profile. |
| `src/launchers/python-api/03-python-api-watch-limits.sh` | Retain exit-2 notice | `examples/lifecycle.py`, watch examples and bounded config; limits not inferred from lifecycle success. |
| `src/launchers/python_api_smoke.sh` | Retain adapter | Readable publish/show/watch lifecycle modes; old positional interface retired. |
| `src/launchers/tracebacks.sh` | Replace with exit-2 guidance | Explicit receiver/publisher traceback security configuration required. |
| `src/launchers/resource_monitor.sh`, `src/resource-monitor/main.py` | Retain adapters | Finite real psutil monitor with bounded history and public plots/tables. |
| `src/resource-monitor/__init__.py` | Remove | Unused package marker; executable adapter remains. |
| `src/launchers/workflows/config-create-populate-run.sh` | Retain owned-workspace workflow | Disposable discovery/population; rejects overwriting caller configs. |
| `src/launchers/workflows/freshness-transition.sh` | Replace with storage-history adapter | Timed freshness checks and bounded manual inspection; no shared tmp config writes. |
| `src/interactive_tests/manual_interactive_validation_1.py` | Retain gallery adapter | Deterministic tables/objects/plots; reconstructed manual checklist covers UI/lifecycle. Downloaded data and old publisher stages retired. |
| `src/interactive_tests/storage_mechanism.py` | Remove | Private core backend exercise belongs in core; public history/restart covered by storage-history. |
| `plotsrv.yml` | Replace with memory-only compatibility default | External core smoke expects this path. Representative options live in configs/current. |
| `configs/plotsrv.yml`, `configs/plotsrv_config_0_0_5.yml`, `configs/plotsrv_no_storage.yml`, `configs/plotsrv_smoketests.yml`, `configs/python-objs/**` | Remove | Superseded schemas/profiles: current minimal/bounded/keyed/catalogue configs; storage/freshness generated in owned runs. Branding fixture retained; exact old profile combinations not certified. |
| `configs/old_plotsrv.ini` | Retain fixture | Watched INI text only, not current configuration. |
| `mock-files/100_20.csv`, `1000_20.csv`, `6000_20.csv`, `long_text.txt`, `uvicorn.log` | Remove from index, preserve local copies | Deterministic bounded fixture generator and tracked table-small.csv; head/tail fixtures available without claiming broad-format assurance. |
| `mock-files/html-simple-1.html`, `html-complex-1.html`, `json-1.json`, `yaml-1.yaml`, `yaml-1.yml`, `small_image.jpg` | Retain fixtures | Synthetic mixed-format/security inspection inputs; credential strings are environment placeholders. |
| `www/free-png.png` | Retain fixture | Branding/image manual inspection. |
| `tmp/plotsrv-generated.yml`, `tmp/plotsrv-freshness-transition.yml`, `tmp/.plotsrv/store/**` | Remove from index, preserve local copies | Captured/generated runtime state replaced by owned workspaces and storage-history scenario. |
| `README.md` | Replace/update | 2.0.0 purpose, candidate setup, automated/manual distinction and guides. |
| `pyproject.toml`, `uv.lock` | Retain/update | 2.0.0 examples dependencies; core candidate installed explicitly. |
| `.python-version`, `.gitignore` | Retain/update | Python selection and generated/private local exclusions. |

Ignored local `.plotsrv/`, `ptop.sh`, user-owned `.codex/`, and Prider support
are preserved. Deleted tracked source/config files remain recoverable from Git.
Previously untracked runtime copies remain local and ignored.

## External core smoke boundary

The inspected core `tests/smoke/smoke-test.sh` invokes the retained launcher with
`--publisher-module smoke_tests.python_objs --publisher-delay 5` and
`--config plotsrv.yml`. Both underscore and hyphen object aliases resolve to the
retained publisher script. Host/port/config and custom script/module options stay
available; the launcher intentionally stays alive until externally stopped.
Publisher failure returns nonzero and reaps its receiver.

This compatibility service no longer attaches the historical mixed-file watch
bundle. Use current watch examples and fixtures explicitly; run `check release`
for automated assurance. The core smoke finishing function can warn about failures
without returning nonzero, so its exit alone is not release evidence. Core is
unchanged. No historical standalone release checklist was supplied; the new
[manual checklist](manual-checklist.md) is explicitly reconstructed.
