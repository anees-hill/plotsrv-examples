# About

This package is for the testing and demonstration of [plotsrv](https://github.com/anees-hill/plotsrv) only. In active development.

## Python objects with a live stream

Start the usual server from the repository root in your activated environment:

```bash
bash src/launchers/python-objs/00-python-objs.sh
```

Then run the companion smoke test (with `src` on `PYTHONPATH`):

```bash
PYTHONPATH=src python -m smoke-tests.python_objs_w_stream
```

This runs all of `smoke-tests.python_objs`, then appends 60 structured JSONL log
records over about 30 seconds. Open **streams / python objects log** to inspect
live updates, nested metrics, and INFO/WARNING/ERROR filtering. The stream is
explicitly stopped and drained when the script finishes or you press Ctrl-C;
its temporary source file is removed, and delivered records remain in the server.
Delivery or close failures make the script fail.

For a longer interactive run, use `--records 600 --interval 0.5`; for a quick
check, use `--records 15 --interval 0.01`. The script uses the same `PLOTSRV_HOST`
and `PLOTSRV_PORT` (or `HOST` and `PORT`) settings as the original test, defaulting
to `127.0.0.1:8101`.
