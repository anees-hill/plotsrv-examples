"""Generate small synthetic JPEG scans, audit their pixels, and publish a daily report."""

import argparse
import json
import math
import os
import shutil
import statistics
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publishing import Publisher


def make_scan(path, number, day):
    from PIL import Image, ImageDraw, ImageEnhance

    image = Image.new("RGB", (640, 450), "#faf9f4")
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 36, 592, 414), outline="#aaa9a4", width=2)
    draw.text((80, 70), f"NORTHSTAR ARCHIVE / SHEET {number:02d}", fill="#343839")
    draw.text((80, 90), f"Audit date: {day.isoformat()}", fill="#343839")
    for row in range(5):
        y = 125 + row * 27
        draw.text(
            (85, y),
            f"Field {row + 1}: Synthetic document sample {number:02d}",
            fill="#4c5151",
        )
    draw.line((95, 330, 545, 330), fill="#202628", width=4)
    draw.text((85, 370), "Generated locally for the plotsrv demo", fill="#51595a")
    if (day.toordinal() * 3 + number * 7) % 17 == 0:
        image = image.rotate(
            4, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="#faf9f4"
        )
    if number == 1 or (day.toordinal() + number * 3) % 11 == 0:
        image = ImageEnhance.Brightness(image).enhance(0.58)
    if (day.toordinal() * 2 + number * 5) % 13 == 0:
        image = ImageEnhance.Contrast(image).enhance(0.18)
    image.save(path, "JPEG", quality=82, optimize=True)


def audit(path):
    from PIL import Image, ImageStat

    with Image.open(path) as original:
        gray = original.convert("L")
        brightness, contrast = (
            round(x, 1)
            for x in (ImageStat.Stat(gray).mean[0], ImageStat.Stat(gray).stddev[0])
        )
        points = []
        # Measure the registration line, excluding the footer below it.
        for x in range(110, 530, 4):
            matches = [y for y in range(305, 350) if gray.getpixel((x, y)) < 115]
            if matches:
                points.append((x, statistics.median(matches)))
        if len(points) > 30:
            mean_x = statistics.mean(x for x, _ in points)
            mean_y = statistics.mean(y for _, y in points)
            slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / sum(
                (x - mean_x) ** 2 for x, _ in points
            )
            skew = round(abs(math.degrees(math.atan(slope))), 1)
        else:
            skew = None
    flags = []
    if brightness < 190:
        flags.append("dim")
    if contrast < 18:
        flags.append("low contrast")
    if skew is not None and skew > 2.0:
        flags.append("skewed")
    return {
        "brightness": brightness,
        "contrast": contrast,
        "skew_degrees": skew,
        "quality": "review" if flags else "pass",
        "flags": ", ".join(flags),
    }


def make_report(day, output):
    run_dir = output / day.isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for number in range(1, 11):
        path = run_dir / f"sheet-{number:02d}.jpg"
        make_scan(path, number, day)
        rows.append(
            {
                "scan_id": f"SHEET-{number:02d}",
                "run_date": day.isoformat(),
                **audit(path),
            }
        )
    review_count = sum(row["quality"] == "review" for row in rows)
    metrics = {
        "run_date": day.isoformat(),
        "scans": len(rows),
        "review_count": review_count,
        "pass_count": len(rows) - review_count,
        "mean_brightness": round(statistics.mean(row["brightness"] for row in rows), 1),
    }
    return rows, metrics, run_dir


def read_previous(path, day):
    if not path.exists():
        return None
    if path.stat().st_size > 16_384:
        raise ValueError("previous-run state exceeds its size limit")
    state = json.loads(path.read_text())
    current = state["current"]
    current_day = date.fromisoformat(current["run_date"])
    if day < current_day:
        raise ValueError("audit date precedes the latest successful run")
    return state.get("previous") if day == current_day else current


def comparison(metrics, previous, rows=()):
    lines = [
        f"# Completed scan audit · {metrics['run_date']}",
        "## Quality overview",
        f"**{metrics['pass_count']} passed** · **{metrics['review_count']} need review** · {metrics['scans']} scans inspected.",
        "The audit is complete. Completion means every image was inspected; it does not mean every image passed quality checks.",
        "## Review register",
        "| Scan | Result | Brightness | Contrast | Skew ° | Flags |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        skew = "not measurable" if row["skew_degrees"] is None else row["skew_degrees"]
        lines.append(
            f"| {row['scan_id']} | {row['quality']} | {row['brightness']} | {row['contrast']} | {skew} | {row['flags'] or '—'} |"
        )
    lines += ["## Since the previous run"]
    if previous is None:
        lines.append(
            "First completed run. The current results are complete; a comparison will appear after the next daily audit."
        )
    else:
        lines += [
            f"Compared with {previous['run_date']}:",
            "| Metric | Previous | Current | Change |",
            "| --- | ---: | ---: | ---: |",
        ]
        for key, label in [
            ("review_count", "Scans requiring review"),
            ("mean_brightness", "Mean brightness"),
        ]:
            lines.append(
                f"| {label} | {previous[key]} | {metrics[key]} | {metrics[key] - previous[key]:+.1f} |"
            )
    lines += [
        "## Review priorities",
        "1. Inspect flagged images in the results table.",
        "2. Check dim or low-contrast pages before attempting transcription.",
        "3. Review registration-line measurements for skewed pages.",
        "## Measurement policy",
        "| Signal | Review threshold |",
        "| --- | --- |",
        "| Mean brightness | Below 190 / 255 |",
        "| Pixel contrast | Below 18 |",
        "| Absolute skew | Above 2 degrees |",
        "> SHEET-01 is an intentionally dim calibration sample. It ensures the real pixel audit finds a defect and the ‘Scans require review’ data check remains visible.",
        "### Provenance",
        "All JPEGs are generated synthetic documents. The job calculates these metrics and comparisons; plotsrv displays the supplied results and evaluates the configured check.",
    ]
    return "\n".join(
        line if line.startswith("|") else "\n" + line + "\n" for line in lines
    )


def publish(rows, metrics, change_note, example):
    import pandas as pd
    import plotsrv as ps

    # This standalone job must fail if a synchronous publication fails.
    os.environ["PLOTSRV_DEBUG"] = "1"
    run_date = metrics["run_date"]
    options = {"launch_server": False, "section": "Document scan audit"}
    ps.publish_view(
        pd.DataFrame(rows),
        view_id="scans:results",
        label=f"Scan results · {run_date}",
        async_=False,
        **options,
    )
    ps.publish_view(
        example,
        view_id="scans:example",
        label=f"{example.stem.upper()} · {run_date}",
        async_=False,
        **options,
    )
    ps.publish_view(
        metrics,
        view_id="scans:metrics",
        label=f"Audit metrics · {run_date}",
        kind="artifact",
        artifact_kind="json",
        async_=False,
        **options,
    )
    ps.publish_view(
        metrics,
        view_id="scans:observed",
        label=f"Observed run · {run_date}",
        observe=True,
        **options,
    )
    if not ps.flush_views(timeout=15):
        raise RuntimeError("observation delivery did not drain")
    error = ps.get_observation_stats().get("last_error")
    if error:
        raise RuntimeError(f"observation delivery failed: {error}")
    # The completion view is updated last, after observation delivery finishes.
    ps.publish_view(
        change_note,
        view_id="scans:changes",
        label=f"Completed audit · {run_date}",
        kind="artifact",
        artifact_kind="markdown",
        async_=False,
        **options,
    )


def write_json(path, value):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(value))
    os.replace(pending, path)


def prune_runs(output, day):
    # Only this job's dated batches belong to us. Never follow symlinks or
    # remove unrelated directories supplied beneath --output.
    runs = []
    for path in output.iterdir():
        if path.is_symlink() or not path.is_dir() or path.name == day.isoformat():
            continue
        try:
            if date.fromisoformat(path.name).isoformat() == path.name:
                runs.append(path)
        except ValueError:
            pass
    for old in sorted(runs, key=lambda p: p.name)[:-2]:
        shutil.rmtree(old)


def complete(day, output):
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "state.json"
    status_path = output / "job-status.json"
    status = {
        "run_date": day.isoformat(),
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
    }
    write_json(status_path, status)
    try:
        previous = read_previous(state_path, day)
        # Prune before creating another batch, including after a previous crash.
        prune_runs(output, day)
        rows, metrics, run_dir = make_report(day, output)
        example_id = next(
            (row["scan_id"] for row in rows if row["quality"] == "review"),
            rows[0]["scan_id"],
        )
        example = run_dir / (example_id.lower() + ".jpg")
        publish(rows, metrics, comparison(metrics, previous, rows), example)
        # Same-day retries keep the original prior-run comparison.
        write_json(state_path, {"current": metrics, "previous": previous})
    except Exception as error:
        write_json(
            status_path,
            {**status, "status": "failed", "error_type": type(error).__name__},
        )
        raise
    else:
        write_json(
            status_path,
            {
                **status,
                "status": "succeeded",
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )
        return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", type=date.fromisoformat, default=datetime.now(UTC).date()
    )
    parser.add_argument("--output", type=Path, default=Path(".plotsrv/scans-output"))
    args = parser.parse_args()
    os.environ.setdefault(
        "PLOTSRV_CONFIG", str(Path(__file__).with_name("plotsrv.yml"))
    )
    with Publisher("scan_audit").locked() as publisher:
        print(json.dumps(complete(args.date, args.output)))
