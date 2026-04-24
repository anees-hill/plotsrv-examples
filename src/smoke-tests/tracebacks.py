import time
import numpy as np
from plotsrv.tracebacks import publish_traceback  # traceback type A1 (explicit in try)
from plotsrv.capture import capture_exceptions  # traceback type A2 (wrapper)
from plotsrv.decorators import plotsrv  # traceback type B1 (iautomatic in decorator)


def run_a1():
    for i in range(1, 6):
        try:
            if i % 2 == 0:
                raise RuntimeError(f"A1 intentional failure on iteration {i}")

            arr = np.random.randn(50, 10)
            print("ok", i, arr.shape)

        except Exception as e:
            publish_traceback(
                e,
                label="A1 - explicit publish_traceback",
                section="traceback-tests",
                host="127.0.0.1",
                port=8000,
            )

        time.sleep(1)


def do_work(i: int) -> None:
    if i % 3 == 0:
        raise ValueError(f"A2 boom on {i}")


def run_a2():
    for i in range(1, 8):
        with capture_exceptions(
            label="A2 - capture_exceptions",
            section="traceback-tests",
            host="127.0.0.1",
            port=8000,
            reraise=False,  # keep the loop going
        ):
            do_work(i)

        print("iteration", i, "done")
        time.sleep(1)


@plotsrv(
    label="B1 - decorator on_error",
    section="traceback-tests",
    host="127.0.0.1",
    port=8000,
    on_error="publish_and_raise",
)
def sometimes_fails(i: int) -> np.ndarray:
    if i % 2 == 0:
        raise RuntimeError(f"B1 intentional failure on iteration {i}")
    return np.random.randn(10, 3)


def run_b1():
    for i in range(1, 6):
        try:
            arr = sometimes_fails(i)
            print("ok", i, arr.shape)
        except Exception:
            # expected for even i (because publish_and_raise)
            pass
        time.sleep(1)


if __name__ == "__main__":
    run_a1()
    run_a2()
    run_b1()
