"""Generate small synthetic JPEG scans, audit their pixels, and publish a daily report."""

import argparse
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import statistics


def make_scan(path, number, day):
    from PIL import Image, ImageDraw, ImageEnhance

    image = Image.new("RGB", (640, 450), "#faf9f4")
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 36, 592, 414), outline="#aaa9a4", width=2)
    draw.text((80, 70), f"NORTHSTAR ARCHIVE / SHEET {number:02d}", fill="#343839")
    for row in range(5):
        y = 125 + row * 27
        draw.text((85, y), f"Field {row+1}: Synthetic document sample {number:02d}", fill="#4c5151")
    draw.line((95, 330, 545, 330), fill="#202628", width=4)
    draw.text((85, 370), "Generated locally for the plotsrv demo", fill="#51595a")
    if (day.toordinal() * 3 + number * 7) % 17 == 0:
        image = image.rotate(4, resample=Image.Resampling.BICUBIC,
                             expand=False, fillcolor="#faf9f4")
    if (day.toordinal() + number * 3) % 11 == 0:
        image = ImageEnhance.Brightness(image).enhance(0.58)
    if (day.toordinal() * 2 + number * 5) % 13 == 0:
        image = ImageEnhance.Contrast(image).enhance(0.18)
    image.save(path, "JPEG", quality=82, optimize=True)


def audit(path):
    from PIL import Image, ImageStat

    with Image.open(path) as original:
        gray = original.convert("L")
        brightness, contrast = (round(x, 1) for x in (ImageStat.Stat(gray).mean[0],
                                                       ImageStat.Stat(gray).stddev[0]))
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
                (x - mean_x) ** 2 for x, _ in points)
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
    return {"brightness": brightness, "contrast": contrast,
            "skew_degrees": skew, "quality": "review" if flags else "pass",
            "flags": ", ".join(flags)}


def make_report(day, output):
    run_dir = output / day.isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for number in range(1, 11):
        path = run_dir / f"sheet-{number:02d}.jpg"
        make_scan(path, number, day)
        rows.append({"scan_id": f"SHEET-{number:02d}", "run_date": day.isoformat(),
                     **audit(path)})
    review_count = sum(row["quality"] == "review" for row in rows)
    metrics = {"run_date": day.isoformat(), "scans": len(rows),
               "review_count": review_count, "pass_count": len(rows) - review_count,
               "mean_brightness": round(statistics.mean(row["brightness"] for row in rows), 1)}
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


def comparison(metrics, previous):
    if previous is None:
        return "# Change since previous audit\n\nFirst completed run. A comparison will appear tomorrow."
    change = metrics["review_count"] - previous["review_count"]
    return ("# Change since previous audit\n\n"
            f"Compared with {previous['run_date']}: **{metrics['review_count']}** scans need "
            f"review ({change:+d} compared with the previous run). "
            f"Mean brightness changed by {metrics['mean_brightness'] - previous['mean_brightness']:+.1f}.\n\n"
            "These are synthetic scans. plotsrv's observed view describes the current "
            "run; this cross-run comparison is calculated by the job itself.")


def publish(rows, metrics, change_note, example):
    import pandas as pd
    import plotsrv as ps

    options = dict(launch_server=False, section="Document scan audit")
    ps.publish_view(pd.DataFrame(rows), view_id="scans:results", label="Scan results",
                    async_=False, **options)
    ps.publish_view(example, view_id="scans:example", label="Example scan",
                    async_=False, **options)
    ps.publish_view(metrics, view_id="scans:observed", label="Observed run summary",
                    observe=True, **options)
    ps.publish_view(change_note, view_id="scans:changes", label="Since previous run",
                    kind="artifact", artifact_kind="markdown", async_=False, **options)
    if not ps.flush_views(timeout=15):
        raise RuntimeError("observation delivery did not drain")
    error = ps.get_observation_stats().get("last_error")
    if error:
        raise RuntimeError(f"observation delivery failed: {error}")


def complete(day, output):
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "state.json"
    previous = read_previous(state_path, day)
    rows, metrics, run_dir = make_report(day, output)
    example_id = next((row["scan_id"] for row in rows if row["quality"] == "review"), rows[0]["scan_id"])
    example = run_dir / (example_id.lower() + ".jpg")
    publish(rows, metrics, comparison(metrics, previous), example)
    # Advance state only after successful publication; a same-day rerun keeps
    # its original prior-run comparison instead of comparing the day to itself.
    pending = state_path.with_suffix(".tmp")
    pending.write_text(json.dumps({"current": metrics, "previous": previous}))
    os.replace(pending, state_path)
    runs = sorted((p for p in output.iterdir() if p.is_dir() and p.name != day.isoformat()),
                  key=lambda p: p.name)
    for old in runs[:-2]:
        shutil.rmtree(old)
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--output", type=Path, default=Path(".plotsrv/scans-output"))
    args = parser.parse_args()
    os.environ.setdefault("PLOTSRV_CONFIG", str(Path(__file__).with_name("plotsrv.yml")))
    print(json.dumps(complete(args.date, args.output)))
