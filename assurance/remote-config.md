# Remote admission, outage and passive configuration assurance

Use the matching candidate reported by `uv run --no-sync python -B -m plotsrv_examples doctor`.
Each command owns its disposable directory and child processes:

```sh
uv run --no-sync python -B -m plotsrv_examples run admission
uv run --no-sync python -B -m plotsrv_examples run outage
uv run --no-sync python -B -m plotsrv_examples run config-discovery
uv run --no-sync python -B -m pytest -q assurance/tests
```

All required failures return nonzero. `--fault missing-evidence` deliberately
removes required evidence and must fail. `--inspect --inspect-seconds 30` keeps
admission/config receivers available for a finite inspection; outage creates no
receiver and has no inspection hold. Browser checks remain manual-pending.

## Keyed and locked receivers

The profiles `configs/current/keyed.yml` and `configs/current/catalogue.yml`
contain environment-variable names, never credential values. The scenario
creates synthetic matching receiver/publisher credentials. It starts independent
foreground receivers and publishers from separate directories, with explicit
remote destinations and local launch disabled.

The keyed dynamic receiver accepts a valid publication. A fresh publisher with a
wrong synthetic credential must report `publisher_key_required`; a separate
public HTTP diagnostic must return 401; the denied ID must be absent. The locked
receiver accepts `allowed:sample` and rejects `unknown:sample` with 403
`view_not_admitted`. The valid artifact is checked again after rejection.
Success means these distinct outcomes were observed, not that rejected content
was delivered. A Python call returning normally is never receipt evidence.

To use the keyed profile manually from this repository, choose an unused port:

```sh
EXAMPLE_INGEST_KEY=example-only-synthetic plotsrv serve \
  --config configs/current/keyed.yml --port 8000
```

From a disposable publisher directory, with absolute script/report paths as
appropriate:

```sh
EXAMPLE_PUBLISH_KEY=example-only-synthetic python /path/to/plotsrv-examples/examples/watch/admission_publish.py \
  --destination http://127.0.0.1:8000 --bearer-token-env EXAMPLE_PUBLISH_KEY \
  --view-id allowed:sample --text example-content --report ./publication.json
```

Select `catalogue.yml` to restrict writes to its complete configured allowlist.
The report records the application result, not delivery success. Add
`--probe-rejection` for a separate HTTP diagnostic (which also attempts a publish).
The synthetic key authenticates producers; it does not protect dashboard reads.
These scenarios use loopback and do not certify two-machine networking or TLS.

## Receiver unavailable

The outage scenario binds a reserved socket without listening, so its explicit
destination is unavailable and cannot be acquired by a competing local process.
The synchronous public publish call must return normally, preserve the example
application result of 20, and emit `server_unavailable`. The publisher inspects
its TCP listeners and descendants immediately after the call; both must be
empty. A destination connection attempt must still fail. It does not shut down
or inspect the contents of unrelated services, or claim successful delivery.
This checks post-call listener state, not a trace of every transient socket.

## Disposable configuration and static discovery

The scenario invokes `config create`, then edits only that owned generated file
and invokes `config populate limits ... --mode merge`. Its source contains two
literal view IDs, a distinct display label, and a top-level filesystem side
effect. Population selects the configured instance via `PLOTSRV_NAME` and must
retain only the selected literal ID.

Next, `run --config ... --name chosen --no-watch` starts a passive receiver from
a different cwd. A conflicting cwd/environment config points to a missing target,
and the environment names another instance. Only the explicit config/name should
win, and the configured relative source must resolve beside the config. The
catalogue must contain exactly `passive:known`. The side-effect file must remain
absent after both population and passive serving. No callable mode or wizard
internals are exercised.

See [core contract inspection](core-remote-config-contract.md) for precedence
and route details, and [watch examples](../examples/watch/README.md) for local
updates and receiver content independent of publisher source files.
