"""Legacy interactive entry point; deterministic gallery replaces downloaded data."""
from plotsrv_examples.scenarios.gallery import main

if __name__ == "__main__":
    raise SystemExit(main(inspect=True))
