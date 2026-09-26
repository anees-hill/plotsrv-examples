# Structured JSONL stream

From the configured examples checkout:

```sh
uv run --no-sync python -B -m plotsrv_examples run stream-structured
uv run --no-sync python -B -m plotsrv_examples run stream-structured --inspect --inspect-seconds 60
```

The finite scenario starts an owned receiver and separate follower, waits for the
expected stream session, then starts the synthetic writer. It checks all six
records, excludes the pre-attachment record, and verifies an ended session.
Inspection leaves the receiver open for the specified duration; the writer and
follower have finished and the source log stays fixed. Ctrl+C reaps owned children.
The JSON result includes the owned workspace, which can subsequently be cleaned
with `workspace-clean`. Browser appearance remains manual evidence.

For independent terminals, start a receiver using an explicit configuration, then
follow a disposable `.jsonl` path:

```sh
uv run --no-sync python -B examples/streams/follow_jsonl.py /tmp/example-events.jsonl --destination http://127.0.0.1:8000
```

Wait for `Registered; append records now`, then in another terminal:

```sh
uv run --no-sync python -B examples/streams/write_jsonl.py /tmp/example-events.jsonl --records 6
```

Existing source bytes are skipped at attachment. Missing files start at zero when
created. The writer appends at most 100 small records per invocation; repeated
manual invocations accumulate in that file. The follower defaults to 60 seconds
and accepts at most 300; Ctrl+C attempts a bounded drain and close. Stop the writer
before stopping the follower. Receipt is verified by the finite scenario, not by
the registration message. Neither source offsets nor user `sequence` fields are
receiver cursors. See `assurance/core-stream-contract.md` for the inspected contract.

## Mixed HTTP and text

```sh
uv run --no-sync python -B -m plotsrv_examples run stream-http
uv run --no-sync python -B -m plotsrv_examples run stream-http --inspect --inspect-seconds 60
```

This synthetic batch contains three requests (200, 500, 404), one unattributed
traceback, an unknown message, and incomplete JSON preserved as text. Only the
500 request supplies a duration (12.5 ms); no source timestamps are supplied.
The scenario asserts all six frames and three validated requests, checks that
fallback rows have no HTTP fields/projections, then verifies an ended session.
Its finite writer leaves a fixed log below 1 KiB during inspection.

For independent terminals, run `follow_http.py` with the same destination and
duration arguments as `follow_jsonl.py`, using a disposable `.log` path. Wait for
the registration message, then run `write_http.py` with that path. Each invocation
appends one fixed synthetic batch. The follower passes `format="uvicorn"` to core;
the examples implement no parser.

Manual inspection (pending until performed in a browser):

1. Open the printed stream URL and inspect Raw stream. Find the unknown message,
   incomplete JSON, and ambiguous traceback; do not associate it with the 500.
2. Open Suggested views / Recent requests and Errors. The eligible retained
   request count is three, not six. All presentations refer to the same source.
3. Inspect latency suggestions: only one request has a supplied duration.
   Time plots use publisher observation time (`observed`), not source event time.
4. Save a presentation, then return to Raw stream to see fallback content again.
5. Press Ctrl+C in the scenario terminal; it returns 130 and reaps owned children.

Counts describe the retained and loaded evidence window, not service rates or
availability. Paths are not inferred route templates. Sanitized `raw.text` is an
excerpt, not archival bytes. Tracebacks have no inferred request correlation.
Browser behavior is not established by the automated receiver assertions.

## Python application logs

```sh
uv run --no-sync python -B -m plotsrv_examples run stream-python-logs
uv run --no-sync python -B -m plotsrv_examples run stream-python-logs --inspect --inspect-seconds 60
```

This uses `stream_view(..., format="text")` on a file written by another
process. Three common Python logging lines become validated events, while an
unrecognised line remains in Raw stream. The scenario checks the received
records and the four suggestions: Recent log events, Warnings and errors,
Events by level over time, and Busiest loggers. It checks that the suggestions
use the same source view and that no HTTP request fields are invented. The
source has no event timestamps, so plot time means server receipt time.

During browser inspection, switch among suggested views, adjust a filter or
column, save a presentation, and return to Raw stream. Check the warning and
error rows, the plot axes, and the unrecognised line. The automated check
verifies server evidence; these browser actions remain manual.

For separate terminals with a running receiver, follow a disposable `.log`
path using `examples/streams/follow_text.py`, then append a batch with
`examples/streams/write_python_logs.py`. Start the follower before writing;
existing bytes are skipped at attachment.
