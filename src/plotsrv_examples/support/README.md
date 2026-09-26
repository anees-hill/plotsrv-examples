# Lifecycle primitives

Use `require_candidate()` before starting any core child. It returns the existing
doctor provenance report or raises `LifecycleError` on missing/mismatched evidence.

Use `with interruption_cleanup(), Processes() as processes:` in the main thread.
Start foreground receiver and publisher children with explicit argument lists,
owned workspace `cwd`, and isolated configuration in `env`. This helper supports
direct foreground children, as required by current `serve` and a synchronous
Python publisher; it does not manage daemonizing commands or descendant trees.
It never discovers kill targets from a port or calls HTTP shutdown.

`available_port()` is a bind preflight, not a reservation. `wait_evidence` checks
the live child owns the loopback listener using OS socket metadata before HTTP
access. If ownership cannot be inspected, it fails closed. Readiness requires
current `/status` fields. Passing both `view_id` and `sentinel` also requires the
exact `/views` entry and sentinel in `/artifact?view=...` HTML. Use a unique ASCII
sentinel; HTML escaping can change other strings. Publisher exit is checked
separately by `processes.wait` and cannot replace receiver evidence.

Every wait drains both pipes for every child, keeping only a bounded combined
output tail (64 KiB by default). HTTP responses including headers are capped at
256 KiB; nonblocking exchanges enforce a total deadline even with trickling
data. Control remains with the caller between waits: do not add independent
blocking `Popen.wait` calls or other unbounded work inside this lifecycle.

Context exit terminates, escalates to kill when needed, and reaps owned children;
repeated SIGINT/SIGTERM is ignored during bounded context cleanup. It closes pipe
descriptors and retains output tails in memory for diagnostics. Workspace cleanup
must happen afterward. Callers must translate `LifecycleError` into a useful
nonzero CLI result and `KeyboardInterrupt` into an interruption result.

PHASE-02 tests exercise disposable subprocesses and a small HTTP fixture. Real
plotsrv publication, CLI error mapping and `check quick` belong to PHASE-03;
these primitives do not claim those integration cases have passed.
