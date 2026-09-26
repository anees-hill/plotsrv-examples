# Bounded ETL observation and custom calculations

With the candidate installed as described in the repository README, run the
finite scenario with its owned receiver and separate publishers:

```sh
uv run --no-sync python -B -m plotsrv_examples run observe-etl
uv run --no-sync python -B -m plotsrv_examples run observe-etl --inspect --inspect-seconds 60
```

For separate terminals with a receiver already running on loopback port 8000:

```sh
uv run --no-sync python -B examples/observation/etl.py --port 8000
uv run --no-sync python -B examples/observation/custom.py --port 8000
```

Both scripts use the same fixed 48 synthetic orders. Six cancelled orders are
excluded; validation rejects invalid paid-order amounts. Transformation creates
new columns and the application loads a regional sales ledger in memory. Currency
uses integer cents. There are no files, external data sources, growing loops or
size knobs; this is a small example, not an overhead benchmark.

`etl.py` uses `@ps.view(observe=True)` on a synchronous transformation. It returns
the normal columns to the application, which computes its ledger as usual.
The decorator preserves original application exceptions and does not publish
automatic error reports. Observation delivery runs in the background. An inline
`ObservationOptions` call separately selects the batch metric branch and fields.

The receiver's `etl:orders` view contains bounded evidence for 42 paid orders.
Default capture allows at most 32 base positions per column, subject to shared
read/byte/time budgets; fewer may be inspected. Read actual scope, coverage and
omission reasons. Distributed positions are deterministic, not unbiased random
samples. Ranges, means and missingness cannot certify the unsampled orders.
`etl:metrics` contains application-supplied counts and net cents; these are explicit
calculations, not totals extrapolated by observation. Examples are disabled by
default, but field names, category prefixes and aggregates still leave the process.

`custom.py` publishes `etl:regional-totals` through ordinary synchronous JSON
publication. Its explicit aggregation visits every transformed order and reports
regional order counts, gross, discounts and net cents. This illustrates custom
observation logic in application code, separately from bounded automatic capture.
Its full-batch scope applies to this finite synthetic input only.

Each script makes a finite pass. Rapid repeated calls to the same view can be
skipped by cadence or coalesced while pending; in-flight updates may be skipped.
There is no per-call or final-call delivery guarantee. The observed script prints
its application result separately from drain status and process-wide diagnostics.
A successful flush or process exit does not prove receipt. The receiver must stay
alive through the drain; inspect its actual content independently. Remote failures
are best effort with cooldown and no automatic resend.

The scenario compares both publisher application results with a fixed expected
ledger (42 paid orders and 61,925 net cents). It independently reads `/artifact`
responses from the receiver: observed field coverage and endpoint IDs, selected
metric values, publisher session and source provenance, and the full custom JSON
aggregate. These checks parse the public rendered projection, not private capture
envelopes. They will need updating if that public rendering format changes.

The receiver stays alive until publishers have drained and exited. Inspection
keeps only that receiver open; Ctrl+C reaps it and returns 130. The JSON result
records the disposable workspace and child exits. `--fault missing-evidence`
deliberately emits a correct application result without observations: the scenario
must fail despite successful publisher exits. No per-call delivery count is used.

Run `uv run --no-sync python -B -m pytest -q assurance/tests` for automated assurance, including rapid-call
return identity, errors/cancellation, absent delivery, and interruption cleanup.
Browser presentation remains manual evidence: during inspection, open the bounded
orders and supplied metrics views, use the observation help and the Overview,
Fields, Changes and Evidence tabs, then compare the separate full-batch regional
report. A single run has no earlier compatible capture for the Changes tab. Check that
sampled fields and supplied totals remain clearly distinguished. No browser
behavior is certified by the HTTP checks.
See [the inspected core contract](../../assurance/core-observation-contract.md)
for supported storage, invocation forms, limits and error semantics.

PHASE-03 worker verification on 2026-09-10 against core
`c4c86d230955af9dff6a1c9c766eeb340859ae43`: the finite command passed and
`uv run pytest -q assurance/tests` passed all 69 tests. Core Git state remained
clean. This is worker-reported evidence, not independent acceptance or browser
verification.
