# Checks and generic webhooks

Run `uv run --no-sync python -B -m plotsrv_examples run checks-webhook`. The scenario creates
an owned receiver/store, a bounded loopback sink, and a reserved non-listening
loopback destination. No external webhook service or credential is used.

The supplied metric `errors > 0` starts healthy with no baseline alert, becomes
failing, repeats unchanged without another event, then recovers. A structured
stream sends status 200 and 503; only 503 yields a match. The sink verifies event
identity headers and the scenario compares payload identities, values and states
to `/checks`. The unavailable destination exhausts three attempts per state event
and leaves a recovered check and unchanged application result. This verifies
bounded best-effort failure, not durable or exactly-once delivery.

`publish.py --port PORT --state healthy|failing|recovered --schema 1|2` is the small
public API example. Only use it with your own receiver. `sink.py` is a test fixture
with an 8 KiB request limit, one connection at a time, a one-second connection
timeout and at most 16 retained requests; it is not a production receiver.

For the browser checklist and live controls, see
[manual inspection](../../assurance/checks-webhook.md). Core remains read-only;
generated history stays in the owned run and can later be removed with the
existing guarded workspace-clean command.
