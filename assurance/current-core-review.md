# Current plotsrv reconciliation

Reviewed 2026-09-26 against the clean sibling plotsrv checkout at
`c9378b03aa82e67f30e45b3ee711bbcdb65c3a34` on
`0-8-0-green-sprint-1`. Its declared and installed version is 0.8.0.
The dated 0.7.0 inspection and run reports elsewhere in `assurance/` remain
historical records; they do not establish current behavior.

The public `stream_view` API still supports the existing JSONL and mixed
Uvicorn examples. The new `stream-python-logs` example exercises a separate
`format="text"` follower, retained raw lines, three recognised Python log
events and four server-provided suggestions. The observation API still supports
the existing ETL example. Its browser markup changed in 0.8.0, so the receiver
check now reads the current public projection and technical provenance panel.

The gallery now uses `configs/current/demo-ui.yml` to demonstrate the current
page title, header, Featured and compact view settings. Browser controls added
or revised in 0.8.0—view pins and modes, theme, plot sizing, stream
interpretation, observation help, History, freshness and refresh—are included
in the manual checklist. HTTP checks verify received data and rendered HTML;
they do not substitute for browser interaction.

The config wizard has no example or manual checklist dependency. The retained
`config-discovery` scenario covers the separate, noninteractive `config create`
and `config populate` commands and passive source discovery.

Verification with this checkout: doctor reported matching source and 0.8.0
distribution metadata; the 19 focused observation, stream, configuration and
gallery tests passed; all 16 release scenarios passed with stable core
provenance. The automated report retains `manual_status: pending` and
`release_signoff: withheld` until someone performs the browser and external
checks. The full repository suite passed 147 tests in 323.36 seconds.
`uv lock --check` and source compilation also passed.

This repository currently contains one local weather sample and release
examples. It does not yet provide the three internet-facing demos or a
deployment for `demo.plotsrv`.
