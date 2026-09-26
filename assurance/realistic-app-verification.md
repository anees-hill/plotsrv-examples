# Realistic application worker evidence

Core inspected read-only: `c4c86d230955af9dff6a1c9c766eeb340859ae43`.
Reference and imported candidate matched; core Git status was clean.
These observations are worker-reported and are not independent acceptance.

- Resource monitor: finite run verified four receiver views, real typed samples,
  two retained observations and zero open figures. Ten-second inspection produced
  19 samples with two retained and both children reaped. Five focused tests include
  200 real samples with bounded retention, failed rendering publication cleanup,
  receiver success/missing evidence and Ctrl+C cleanup.
- Weather sample: default and two-second inspection runs verified the exact three
  transformed rows, decoded PNG, and synthetic status on a fresh local receiver.
- Weather live: controlled local HTTP success used the same pipeline; controlled
  HTTP failure and refused loopback connection returned nonzero, published only
  unavailable status, and reaped children. Source URL/query markers were absent
  from reports. Missing live config cannot start the sample source.
- Thirteen weather tests cover real HTTP and source shutdown, invalid schemas,
  both source modes, live failure, oversized responses, slow-response deadline,
  and HTTP worker cleanup on timeout and publisher termination.
- Added source/config URLs are loopback or `weather.example.invalid`; no real
  endpoint, credential, or private payload was supplied or added. Local `.env`
  is ignored. The example environment file remains trackable.

Manual browser appearance remains pending. Real-source contract/authentication
integration remains unresolved and no private-demo parity or deployment is claimed.
Retention checks are not an RSS benchmark.

PHASE-03 commands: `uv run python -m plotsrv_examples run weather-demo` passed;
inspection with `--inspect --inspect-seconds 2` passed. Explicit live mode against
a refused loopback port returned the expected exit 1 and unavailable-only receiver
evidence. `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
assurance/tests/test_weather_demo.py` passed all 13 tests, including HTTP worker
termination cleanup.

Full assurance: **118 passed, 1 failed** in 302.68 seconds. The pre-existing
`test_lifecycle.py::test_failed_child_diagnostic_is_prompt` expected the child's
`broken startup` stderr but received a listener-ownership inspection error. The
same failure reproduced in isolation. No lifecycle change was applied in that
turn; its full suite was not reported as passing.
The preceding PHASE-02 full run passed 105 tests; the current full run includes
the later monitor interruption test and weather tests.

PHASE-03 continuation repaired the diagnostic race: a psutil inspection error
allows at most 100 ms for the owned child to exit before reporting its stderr.
A still-running child with denied inspection continues to fail ownership checks.
Both outcomes have regression coverage; all 11 lifecycle tests passed.
Default 30-second inspection commands also passed for both applications. The
monitor produced 44 samples, retained two, and had zero open figures. Weather
retained its three expected synthetic observations. Both runs reaped their owned
children and reported the same clean core revision and matching runtime candidate.

The next full run passed 120 tests but exposed an HTTP-worker registration race
in the weather termination test. Fetch now defers SIGINT/SIGTERM until its worker
handle is registered, then kills/reaps it in `finally`. A deterministic regression
injects termination during registration. The 24 weather/lifecycle tests and the
new registration regression passed separately after repair.

Final continuation verification: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
assurance/tests` passed **122 tests in 313.75 seconds**, including both lifecycle
diagnostic outcomes and weather interruption during worker registration. This
supersedes the failed intermediate runs above. Core Git status remained clean at
`c4c86d230955af9dff6a1c9c766eeb340859ae43`; no core changes were made.

## Mandatory integration self-check

After implementation, a fresh `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
assurance/tests` passed **122 tests in 311.78 seconds**. The finite resource
command passed with three real samples, two retained and zero open figures.
Weather with `WEATHER_LIVE_URL` removed passed with the exact synthetic sample
views. Explicit live mode against a refused loopback connection returned the
expected exit 1 and only an unavailable status view. All three runs reaped their
owned children and matched the inspected core candidate. No implementation
changes were needed in this self-check phase.

| Item | Worker status | Evidence |
| --- | --- | --- |
| INV-01 | passed | Bounded monitor history/logs and weather bytes/records/deadline; cleanup tests pass. |
| INV-02 | passed | Default weather succeeds over loopback HTTP with no live configuration. |
| INV-03 | passed | Live failure returns unavailable, never synthetic fallback. |
| INV-04 | passed | Sample and controlled live tests exercise shared fetch/normalise/transform/publish code. |
| INV-05 | passed | Before/after core status clean at the same revision. |
| CASE-01 | passed | 200-sample retention and interruption tests; finite monitor receipt verified. |
| CASE-02 | passed | Exact transformed sample rows, decoded PNG and synthetic status verified. |
| CASE-03 | passed | Controlled HTTP failure and refused connection yield unavailable-only receiver evidence. |
| CASE-04 | passed | Scoped source/config/report inspection finds loopback and placeholder URLs only; redaction tests pass. |
| CASE-05 | passed | No core edits; clean revision and matching runtime provenance. |

These statuses are worker self-reports, not independent acceptance. Browser
appearance, private-demo parity and real-source integration remain unverified.
