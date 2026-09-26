# Resource monitor

Run `uv run --no-sync python -B -m plotsrv_examples run resource-monitor` for three real
psutil samples and receiver-backed table/PNG checks. Add `--inspect` to sample
for 30 seconds, or `--inspect --inspect-seconds 300` for five minutes.
Ctrl+C cleans up owned children. Browser appearance remains manual-pending.

The scenario retains two samples to exercise eviction. The standalone
`main.py --destination http://127.0.0.1:8000` requires an existing receiver and
accepts `--samples`, `--history-size` (default 60, maximum 10000), `--interval`
(seconds), and `--duration` (minimum sampling duration). History is bounded
before rendering. CPU/memory matplotlib plots and pandas/Polars tables reuse
four view IDs. Figures close on failure, receiver storage is disabled by the
scenario, and captured output is limited to 65536 bytes per child.

The former infer/explicit switches had identical behavior and are removed.
The old shell launcher forwards scenario options; the old Python path forwards
standalone options. See `assurance/core-realistic-app-contract.md` for core API
provenance. The representative plot backend is now matplotlib.

PHASE-02 worker checks (2026-09-10): finite receiver run passed; a 10-second
inspection produced 19 samples, retained two, decoded both PNGs and left no
open figures or owned children. Five focused tests cover 200 real samples with
seven retained (publication stubbed for that retention check), plot exception
cleanup, real receiver success/missing evidence, and inspection interruption.
These are worker-reported checks, not independent acceptance or an RSS benchmark.
The full assurance run passed 105 tests in 284.95 seconds; the subsequently added
interruption check passed in the separate five-test monitor run.
