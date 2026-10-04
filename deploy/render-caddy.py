"""Select this VM's public hosts from the shared Caddy template."""
import argparse
from pathlib import Path

HOSTS = {
    "website": "plotsrv.com",
    "landing": "demo.plotsrv.com",
    "retail": "retail-demo.plotsrv.com",
    "live_import": "live-demo.plotsrv.com",
    "scan_audit": "scans-demo.plotsrv.com",
}


def render(selected):
    source = Path(__file__).with_name("Caddyfile").read_text()
    # Site boundaries are unindented. Preserve global options and shared snippets.
    start = source.index("\nplotsrv.com {")
    common, sites = source[:start], source[start:]
    blocks = {}
    for name, host in HOSTS.items():
        marker = f"\n{host} {{"
        block_start = sites.index(marker)
        block_end = sites.index("\n}", block_start) + len("\n}")
        blocks[name] = sites[block_start:block_end] + "\n"
    return common + "".join(blocks[name] for name in HOSTS if name in selected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hosts", nargs="+", choices=["all", *HOSTS])
    args = parser.parse_args()
    if "all" in args.hosts and len(args.hosts) != 1:
        parser.error("use all by itself")
    print(render(HOSTS if args.hosts == ["all"] else args.hosts), end="")
