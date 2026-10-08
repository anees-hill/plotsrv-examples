# Local and separate publisher file examples

`run watch-formats` additionally checks representative CSV/text/JSON/YAML/Markdown/
HTML inputs, memory/file CSV materialization, exact source export, preview limits,
and bounded head/tail windows. The [manual smoke guide](../../assurance/manual-smoke-test.md)
adds pagination, filtering, browser persistence and live update steps.

From the examples checkout, with the matching core candidate available (see the
repository setup and `python -m plotsrv_examples doctor`):

```sh
uv run --no-sync python -B -m plotsrv_examples run local-watch
uv run --no-sync python -B -m plotsrv_examples run remote-publish
uv run --no-sync python -B -m plotsrv_examples run remote-watch
```

Each command creates a disposable owned run directory, chooses an available
loopback port, verifies content and reaps its processes. Add `--inspect
--inspect-seconds 30` to keep the verified receiver visible briefly. Ctrl+C
cleans up owned children. `--fault missing-evidence` deliberately exits nonzero.
Run directories remain available for inspection and the existing workspace
cleanup command. These are loopback process tests, not two-machine network tests.

The local workflow invokes the public local watch command, checks initial text,
changes the file, and checks the new text:

```sh
plotsrv watch ./sample.txt --port 8000 --label sample --head --materialization memory
```

This uses the generated `watch:sample` identity. In the inspected core, the
dedicated local memory-watch loop preregisters an explicit `--view-id` but sends
content using section/label identity, so this example uses the matching generated
identity. Core is unchanged; remote watches preserve explicit IDs.

For separate processes, start a receiver in its own directory:

```sh
plotsrv serve --config receiver.yml --host 127.0.0.1 --port 8000
```

Use `storage-settings: {enabled: false}` in this disposable receiver profile.
The receiver never scans application files. From the publisher directory, use
the readable public API example (its script path may be absolute):

```sh
python /path/to/plotsrv-examples/examples/watch/publish_file.py sample.txt \
  --destination http://127.0.0.1:8000 --view-id remote:file
```

The example reads the local file as text and explicitly publishes to the receiver
without server launch. Its optional `--remove-after-read` flag deletes that input
before sending and is intended only for disposable assurance inputs. Publication
return does not prove delivery; the scenario checks the receiver artifact.

To follow changes beside the publisher, run:

```sh
plotsrv watch ./sample.txt --destination http://127.0.0.1:8000 \
  --view-id remote:sample --head --every 0.1
```

This command stays in the foreground until interrupted. It uploads bounded
captures; it does not register a receiver-local file path. The remote-watch
scenario verifies two versions, removes its disposable source, waits for
`missing` status, and checks retained artifact and hosted download bytes. The
receiver cwd contains a conflicting same-name file to detect accidental relative
path resolution. Direct publication removes its input before sending. Neither
workflow requires receiver access to publisher files for the checked content;
this is not an OS filesystem access-control sandbox.

Only the local scenario deliberately starts the combined watch/server workflow.
Explicit remote destinations never request a fallback server. Auth, locked
catalogue, outage and config/discovery assurance belong to the next phase.
