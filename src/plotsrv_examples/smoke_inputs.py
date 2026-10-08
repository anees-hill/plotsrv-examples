"""Deterministic inputs and disposable configurations for the manual smoke guide."""

import csv
from pathlib import Path

import yaml

from .workspace import create


def table_rows(count=1200, version=1):
    return [{"id": i + 1, "group": ("alpha", "beta", "gamma")[i % 3],
             "amount": version * 100 + i % 17,
             **{f"column_{j:02d}": version * 1000 + i + j for j in range(3, 20)}}
            for i in range(count)]


def write_inputs(run):
    run = Path(run)
    for name, count in (("large.csv", 1200), ("small.csv", 99)):
        rows = table_rows(count)
        with (run / name).open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (run / "window.txt").write_text("HEAD-SENTINEL\n" + "middle line\n" * 1000
                                    + "TAIL-SENTINEL\n", encoding="utf-8")
    (run / "sample.json").write_text('{"fixture":"json-smoke","version":1}\n')
    (run / "sample.yml").write_text("fixture: yaml-smoke\nversion: 1\n")
    (run / "sample.md").write_text("# Markdown smoke\n\n**markdown-smoke**\n")
    (run / "sample.html").write_text('<h1>html-smoke</h1><script>window.parent.smokeEscape=1</script>')


def prepare(repository):
    run = create(Path(repository))
    (run / "discovery").mkdir()
    write_inputs(run)
    base = {
        "storage-settings": {"enabled": False, "root_dir": str(run / "store"),
                             "default_keep_last": 3, "default_min_store_interval": None,
                             "latest": {"enabled": True, "restore_on_startup": True,
                                        "restore_scope": "all"}},
        "security-settings": {"tracebacks_enabled": True},
        "render-settings": {"table_view_mode": "rich", "html_sanitize": True},
        "limits": {"truncate_after": {"table_rows": 2000, "table_columns": 20,
                                      "text": 20000}, "watched_files": {"max_mb": 2}},
        "freshness-settings": {"enabled": True, "expected_every": "5s",
                               "warn_after": "10s", "overdue_after": "20s"},
    }
    import copy
    for name in ("memory", "storage", "bounded", "simple", "no-tracebacks", "no-freshness"):
        config = copy.deepcopy(base)
        if name == "storage":
            config["storage-settings"]["enabled"] = True
        elif name == "bounded":
            config["limits"]["truncate_after"].update(table_rows=10, table_columns=5, text=80)
        elif name == "simple":
            config["render-settings"]["table_view_mode"] = "simple"
        elif name == "no-tracebacks":
            config["security-settings"]["tracebacks_enabled"] = False
        elif name == "no-freshness":
            config["freshness-settings"]["enabled"] = False
        (run / f"{name}.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return run
