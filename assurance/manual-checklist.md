# Manual release checklist

Status: **pending**. Automated suite success does not complete any row below.
This checklist is reconstructed from the retained examples, core inspection
contracts, and the legacy interactive gallery purpose; it is not a recovered
historical sign-off or a claim that a tester has performed these checks.

Copy this template into a local release record. Record tester, UTC date, OS,
browser/version, terminal/version, examples revision/dirty state, exact core
revision/dirty state, imported candidate path/version/direct URL, and the matching
automated report. Give each row a status (`pending`, `passed`, `failed`, or
`not applicable` with a reason), evidence and tester/date. Any failed or pending
required row withholds full sign-off. Record external checks separately; do not
substitute local loopback evidence for two-machine behavior.

Run `uv run --no-sync python -B -m plotsrv_examples run NAME --inspect --inspect-seconds 120`
for inspectable scenarios. Open the printed local address while the owned process
is running. Ctrl+C ends inspection and cleans up; that interrupted run is not an
automated pass. Use an earlier completed automated report for automated evidence.
Stream inspection shows retained records after the finite writer has stopped.
To watch records arrive live, start a follower and then a writer in separate
terminals as described in `examples/streams/README.md`.

| Surface / scenario | Human observation required | Status |
| --- | --- | --- |
| `gallery` | Table formatting, plot sizing, object expansion, Featured/compact view entries, Grouped/A–Z navigation, pins and browser theme | pending |
| Focused `examples/lifecycle.py` and gallery | Attached publish/show/watch behavior and terminal interaction; follow example CLI help | pending |
| Focused `examples/exceptions.py` | Traceback display, expansion, readability and intended security presentation | pending |
| `stream-structured`, `stream-http`, `stream-python-logs` | Live feed, filters, interpretation controls, saved presentations, mixed HTTP/text/traceback and Python log suggestions | pending |
| `observe-etl` | Observed content, selected fields, diagnostics, help and the empty Changes state are understandable | pending |
| `local-watch`, `remote-watch`, `remote-publish` | Hosted content updates and retained-byte presentation | pending |
| `admission`, `config-discovery` | Keyed/catalogue UX and discovered views in the browser | pending |
| `storage-history` | History, Compare, freshness, restored snapshots and stale/recovered presentation | pending |
| `checks-webhook` | Attention/check controls, baseline/failure/recovery display | pending |
| `resource-monitor` | Representative charts/tables over a longer session; no benchmark threshold claimed | pending |
| `weather-demo` sample | Weather status, table and plot presentation; local sample is clearly labelled | pending |
| Explicit live weather | Opt-in live source behavior and failure display; requires separately selected public source/configuration | pending |
| Two-machine remote publishing/outage | Real network/security setup and recovery; local automated `outage` is not this check | pending |

Full release sign-off: **withheld**. Tester: unassigned. Date: unset. Browser and
terminal: unset. Candidate: attach the fresh doctor/report identity before testing.
No browser automation, deployment or publication is implied by this checklist.
