"""Three explicit exception-publication styles with intentional sample failures.

uv run --no-sync python -B examples/exceptions.py --port 8000
Set security-settings.tracebacks_enabled: true in BOTH publisher and receiver
configs (select the publisher config with PLOTSRV_CONFIG).
"""

import argparse

import plotsrv as ps


def publish(host, port):
    try:
        raise ValueError("Explicit example failure")
    except ValueError as exc:
        ps.publish_traceback(exc, host=host, port=port,
                             view_id="example-exception-explicit", label="Explicit failure")

    with ps.capture_exceptions(host=host, port=port, reraise=False,
                               view_id="example-exception-captured", label="Captured failure"):
        raise RuntimeError("Captured example failure")

    @ps.view(host=host, port=port, on_error="publish_and_raise",
             view_id="example-exception-decorated", label="Decorated failure")
    def fail():
        raise ValueError("Decorated example failure")

    try:
        fail()
    except ValueError:
        # This demo handles its intentional failure; normal callers choose their policy.
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    publish(args.host, args.port)
