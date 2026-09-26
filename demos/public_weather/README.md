# Weather demo

`uv run --no-sync python -B -m plotsrv_examples run weather-demo` runs a deterministic,
synthetic sample source over actual loopback HTTP. No private service, internet,
or configuration is needed. Add `--inspect` for a 30-second receiver inspection,
or `--inspect --inspect-seconds 120`. Ctrl+C cleans up owned processes.
The HTTP source stops after fetching; inspection retains the published snapshot.
The table, plot title and status explicitly label synthetic sample data.

For live input, export `WEATHER_LIVE_URL` and run the same command with
`--weather-mode live`. `.env.example` contains a placeholder only; `.env` is
ignored and is not automatically loaded. Live mode requires an explicit URL;
sample mode ignores it. HTTPS is supported with normal certificate validation.
Proxy environment settings and redirects are disabled. Credentials in URL
userinfo are rejected; no authentication adapter is currently implemented.

An example adapter must return a JSON object with only `observations`, a list
of 1..1000 records. Each record has exactly `time` (timezone-aware ISO timestamp),
`temperature_c` (finite number, -100..70), and `humidity_percent` (finite number,
0..100). Duplicate instants are rejected. The shared pipeline normalises UTC,
sorts timestamps, adds Fahrenheit and source labels, and publishes a table,
temperature PNG and status. The local fixture has three fixed hourly observations
at 10, 12 and 14 Celsius, yielding 50, 53.6 and 57.2 Fahrenheit.

HTTP uses a two-second socket timeout, a five-second total worker deadline,
65536-byte response limit, and no retries. The parent kills and reaps the worker
on timeout/interruption. Fixture requests have a one-second socket timeout;
its server is shut down and its thread joined. Each invocation fetches once,
retains at most 1000 observations and closes its figure. Receiver persistence
is disabled and scenario child logs are bounded. Runs use fresh owned receivers.

Live fetch/config/schema failure publishes `configured live input unavailable`,
returns nonzero, and creates no measurement views in that fresh receiver.
No synthetic fallback occurs. Reports omit source URLs and response payloads.
Standalone `main.py --destination http://127.0.0.1:8000 --mode live` requires an
existing receiver; any pre-existing measurement views there are historical and
must be interpreted with the unavailable status after failure.

This is an example schema, not reconstruction of the private demo. Its real
contract and authentication requirements remain unresolved; an adapter is needed
before integration. No deployment or real-source parity is claimed. Core API
inspection: revision `c4c86d230955af9dff6a1c9c766eeb340859ae43`, documented in
`assurance/core-realistic-app-contract.md`. Browser checks remain manual-pending.
