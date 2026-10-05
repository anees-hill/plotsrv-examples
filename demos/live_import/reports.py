"""Publish three bounded, illustrative import-report editions once; no refresh loop."""

from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_events import candidate, validate
from publishing import Publisher

HISTORY_VIEWS = (
    "live:recent",
    "live:exceptions",
    "live:manifest",
    "live:outcomes",
    "live:durations",
    "live:report",
)
SOURCES = ("catalogue.csv", "stock-east.csv", "stock-west.csv", "prices.csv")


def make_batch(revision, count=300):
    if revision not in (1, 2, 3) or not 1 <= count <= 1000:
        raise ValueError("unsupported example revision or record count")
    rng = random.Random(9401)
    start = datetime(2026, 9, 27, 9, tzinfo=UTC) + timedelta(hours=revision - 1)
    rows = []
    for index in range(1, count + 1):
        row = candidate(index, rng)
        source = SOURCES[(index - 1) % len(SOURCES)]
        if revision == 1 and index % 5 == 0:
            row["sku"] = "UNKNOWN"
        if revision == 2 and index % 13 == 0:
            row["quantity"] = -1
        issue = validate(row)
        # A reproducible simulated cost, not a measured server latency.
        duration = round(
            (30 + rng.random() * 55 + (80 if source == "stock-west.csv" else 0))
            * (1.7 if revision == 1 else 1.2 if revision == 2 else 1),
            1,
        )
        rows.append(
            {
                "record_id": row["record_id"],
                "source_file": source,
                "timestamp": (start + timedelta(seconds=3 * index)).isoformat(),
                "sku": row["sku"],
                "quantity": row["quantity"],
                "price_gbp": row["price_gbp"],
                "outcome": "rejected" if issue else "accepted",
                "validation_issue": issue or "",
                "simulated_duration_ms": duration,
                "report_revision": revision,
            }
        )
    return rows


def manifest(rows, revision):
    rejected = sum(row["outcome"] == "rejected" for row in rows)
    return {
        "batch_id": f"illustrative-import-{revision}",
        "revision": revision,
        "description": "Illustrative batch; separate from the continuously running live log.",
        "reporting_window": {
            "start": rows[0]["timestamp"],
            "end": rows[-1]["timestamp"],
        },
        "counts": {
            "records": len(rows),
            "accepted": len(rows) - rejected,
            "rejected": rejected,
        },
        "sources": [
            {
                "file": source,
                "records": sum(r["source_file"] == source for r in rows),
                "owner": "Supplier operations",
                "format": "CSV",
            }
            for source in SOURCES
        ],
        "validation": {
            "known_skus": ["PACK", "SHELL", "LAMP"],
            "quantity": {"min": 1, "max": 20},
            "failure_action": "quarantine record; continue batch",
        },
        "timings": {
            "basis": "synthetic simulation, not server measurements",
            "median_ms": round(
                statistics.median(r["simulated_duration_ms"] for r in rows), 1
            ),
        },
        "issues": dict(
            Counter(r["validation_issue"] for r in rows if r["validation_issue"])
        ),
        "history": {
            "editions": 3,
            "meaning": "problematic batch, partial improvement, current example",
        },
    }


def html_report(rows, info):
    counts = info["counts"]
    rate = 100 * counts["accepted"] / counts["records"]

    def cells(values):
        return (
            "<tr>"
            + "".join("<td>" + escape(str(v)) + "</td>" for v in values)
            + "</tr>"
        )

    source_rows = "".join(
        cells(
            [
                source,
                sum(r["source_file"] == source for r in rows),
                sum(
                    r["source_file"] == source and r["outcome"] == "rejected"
                    for r in rows
                ),
                f"{statistics.median(r['simulated_duration_ms'] for r in rows if r['source_file'] == source):.1f} ms",
            ]
        )
        for source in SOURCES
        if any(r["source_file"] == source for r in rows)
    )
    exceptions = "".join(
        cells(
            [
                r["record_id"],
                r["source_file"],
                r["validation_issue"],
                r["sku"],
                r["quantity"],
            ]
        )
        for r in rows
        if r["validation_issue"]
    )
    issues = "".join(
        f"<li><strong>{escape(name.replace('_', ' ').title())}</strong><span>{count} records</span></li>"
        for name, count in info["issues"].items()
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Import operations</title>
<style>
*{{box-sizing:border-box}}body{{overflow-wrap:anywhere;margin:0;background:#f1f5fa;color:#20324c;font:15px/1.6 system-ui,sans-serif}}
main{{max-width:1080px;margin:auto;padding:32px 24px}}header{{background:#163552;color:white;border-radius:18px;padding:30px}}
.eyebrow{{letter-spacing:.16em;text-transform:uppercase;font-size:11px;font-weight:700;color:#8edacc}}
h1{{font-size:clamp(26px,4vw,42px);line-height:1.15;margin:12px 0}}h2{{font-size:21px;margin:0 0 12px}}h3{{font-size:15px}}
header p{{color:#d4e3ee;max-width:650px}}.tag{{display:inline-block;border:1px solid #6f91ad;border-radius:30px;padding:4px 12px;font-size:12px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin:20px 0}}
.card,section{{background:white;border:1px solid #dce5ef;border-radius:14px;padding:22px}}
.card strong{{display:block;font-size:32px;color:#176b68}}.card.warn strong{{color:#a6641b}}.card small{{color:#607086}}
.grid>div{{min-width:0}}.grid{{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:20px}}section{{margin-bottom:20px;min-width:0}}
.bar{{height:18px;display:flex;border-radius:9px;overflow:hidden;background:#f4c580;margin:16px 0}}.bar span{{background:#279c8a}}
ul{{padding-left:20px}}.issues{{list-style:none;padding:0}}.issues li{{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid #e8edf4}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;padding:11px 10px;border-bottom:1px solid #e6edf4;white-space:nowrap}}th{{color:#48647f;background:#f3f7fb}}
.note{{border-left:4px solid #dda047;background:#fff8e9;padding:14px 16px;border-radius:4px}}details summary{{cursor:pointer;font-weight:650}}footer{{color:#5f7087;font-size:12px}}code{{background:#eef3f7;padding:2px 5px;border-radius:4px}}
@media(max-width:720px){{main{{padding:12px}}.grid{{grid-template-columns:1fr}}header,section{{padding:20px}}}}
</style></head><body><main>
<header><div class="eyebrow">plotsrv / file import operations</div><h1>From incoming files<br>to dependable records.</h1>
<p>A concise view of validation, quarantined records and processing behaviour across four incoming feeds.</p>
<span class="tag">Illustrative batch · edition {info["revision"]} of 3</span></header>
<div class="cards"><div class="card"><small>Records inspected</small><strong>{counts["records"]:,}</strong><small>Four synthetic CSV sources</small></div>
<div class="card"><small>Accepted</small><strong>{rate:.1f}%</strong><small>{counts["accepted"]} records passed validation</small></div>
<div class="card warn"><small>Quarantined</small><strong>{counts["rejected"]}</strong><small>Retained for investigation</small></div>
<div class="card"><small>Median simulated duration</small><strong>{info["timings"]["median_ms"]:.1f}<small> ms</small></strong><small>Illustrative, not server latency</small></div></div>
<div class="grid"><div><section><h2>Batch outcome</h2><p>Validation continues after a rejected record. Accepted rows remain available while the exceptions are investigated.</p>
<div class="bar" role="img" aria-label="{rate:.1f} percent accepted"><span style="width:{rate:.1f}%"></span></div>
<p><strong>{counts["accepted"]} accepted</strong> · {counts["rejected"]} rejected</p>
<div class="scroll"><table><thead><tr><th>Source file</th><th>Records</th><th>Rejected</th><th>Median simulated time</th></tr></thead><tbody>{source_rows}</tbody></table></div></section>
<section><h2>Exception register</h2><p>Each rejection is produced by the example validator. Open the exceptions table in plotsrv to sort or inspect all fields.</p>
<details><summary>Inspect {counts["rejected"]} quarantined records</summary><div class="scroll"><table><thead><tr><th>Record</th><th>Source</th><th>Issue</th><th>SKU</th><th>Quantity</th></tr></thead><tbody>{exceptions}</tbody></table></div></details></section></div>
<div><section><h2>Validation signals</h2><ul class="issues">{issues}</ul><h3>Rules in this example</h3><ul><li>SKU must be PACK, SHELL or LAMP.</li><li>Quantity must be between 1 and 20.</li><li>Rejected records are quarantined individually.</li></ul></section>
<section><h2>Review notes</h2><p>Look across sources as well as totals: an improved headline can hide a feed that still needs attention.</p><div class="note">History contains three illustrative editions: initial issues, partial improvement and the current example.</div></section></div></div>
<section><h2>Manifest &amp; provenance</h2><p>Batch <code>{escape(info["batch_id"])}</code><br>Fictional event window: {escape(info["reporting_window"]["start"])} → {escape(info["reporting_window"]["end"])}</p>
<p>The JSON manifest contains counts, source ownership and validation policy. Snapshot capture times are genuine. These prepared example batches are separate from the continuously running live log.</p></section>
<footer>All records are synthetic. Durations are simulated. No customer data or external data services are involved. This report uses local styles and no JavaScript.</footer>
</main></body></html>'''


def content(revision):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    rows = make_batch(revision)
    info = manifest(rows, revision)
    yield "live:recent", "Recent imports", pd.DataFrame(rows), "table"
    yield (
        "live:exceptions",
        "Validation exceptions",
        pd.DataFrame([r for r in rows if r["validation_issue"]], columns=list(rows[0])),
        "table",
    )
    yield "live:manifest", "Batch manifest", info, "json"
    with plt.rc_context(
        {
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    ):
        fig, ax = plt.subplots(figsize=(8.5, 4.5), layout="constrained")
        groups = [rows[i : i + 30] for i in range(0, len(rows), 30)]
        accepted = [sum(r["outcome"] == "accepted" for r in group) for group in groups]
        labels = [group[0]["timestamp"][11:16] for group in groups]
        ax.bar(labels, accepted, color="#279c8a", label="Accepted")
        ax.bar(
            labels,
            [len(g) - a for g, a in zip(groups, accepted)],
            bottom=accepted,
            color="#dda047",
            label="Quarantined",
        )
        ax.set(
            title="Validation outcomes over time",
            xlabel="Fictional batch time (UTC)",
            ylabel="Records per 90-second window",
        )
        ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0, 1.02), ncol=2)
        ax.set_title("Validation outcomes over time", pad=38)
        ax.tick_params(axis="x", rotation=45)
        yield "live:outcomes", "Import outcomes", fig, "plot"

        fig, ax = plt.subplots(figsize=(8.5, 4.5), layout="constrained")
        boxes = ax.boxplot(
            [
                [r["simulated_duration_ms"] for r in rows if r["source_file"] == source]
                for source in SOURCES
            ],
            tick_labels=SOURCES,
            patch_artist=True,
            medianprops={"color": "#163552", "linewidth": 2},
        )
        for box in boxes["boxes"]:
            box.set_facecolor("#8acabd")
        ax.set(
            title="Validation duration by source file", ylabel="Simulated duration (ms)"
        )
        ax.grid(axis="y", alpha=0.15)
        yield "live:durations", "Processing profile", fig, "plot"
    yield "live:report", "Import operations report", html_report(rows, info), "html"


def publish():
    with Publisher("live_import").locked() as publisher:
        publisher.seeded(HISTORY_VIEWS, content)
        publisher.current(content)


if __name__ == "__main__":
    os.environ.setdefault(
        "PLOTSRV_CONFIG", str(Path(__file__).with_name("plotsrv.yml"))
    )
    os.environ["PLOTSRV_DEBUG"] = "1"
    publish()
