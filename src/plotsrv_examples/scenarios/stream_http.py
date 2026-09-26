"""Receiver assertions for conservative mixed HTTP/text interpretation."""


def verify(data):
    rows = data["records"]
    events = [row["data"] for row in rows]
    if len(events) != 6 or data["accepted_records"] != 6:
        raise ValueError("Expected six mixed frames")
    if [event["event"]["kind"] for event in events] != [
        "http_request", "http_request", "traceback", "text", "text", "http_request"
    ]:
        raise ValueError("Incorrect mixed event kinds/order")
    requests = [events[i]["http"] for i in (0, 1, 5)]
    if requests != [{"method": "GET", "path": "/health", "status": 200},
                    {"method": "POST", "path": "/work", "status": 500, "duration_ms": 12.5},
                    {"method": "GET", "path": "/missing", "status": 404}]:
        raise ValueError("Incorrect supplied HTTP fields")
    for index in (2, 3, 4):
        if set(events[index]) != {"log_schema_version", "event", "raw"} or "http_projection" in rows[index]:
            raise ValueError("Fallback acquired fabricated request telemetry")
    traceback = events[2]["raw"]
    if (not traceback["ambiguous"] or "ValueError: synthetic failure" not in traceback["text"]
            or 'File "app.py"' not in traceback["text"] or "/tmp/synthetic" in traceback["text"]):
        raise ValueError("Traceback content/attribution incorrect")
    if events[3]["raw"]["text"] != "worker-note: unexpected orbit wobble\n" or events[4]["raw"]["text"] != '{"incomplete":\n':
        raise ValueError("Unknown text was lost or reinterpreted")
    for event in events:
        if (event["log_schema_version"] != 1 or event["event"]["adapter"] != "uvicorn"
                or set(event["event"]) != {"kind", "adapter", "publisher_observed_at"}
                or not event["event"]["publisher_observed_at"]
                or event["raw"]["partial"] or event["raw"]["truncated"]
                or "pre_attach" in event["raw"]["text"]):
            raise ValueError("Unexpected framing, timestamps or pre-attachment content")
    profile = data["http_profile"]
    if (profile.get("request_count") != 3 or profile.get("inspected_count") != 6
            or profile.get("time_origin") != "observed" or not profile.get("recipes")
            or "duration" not in profile.get("fields", {})
            or any(recipe["sourceId"] != data["view_id"] for recipe in profile["recipes"])):
        raise ValueError("HTTP suggestions misrepresent retained evidence")
    return {"event_kinds": [event["event"]["kind"] for event in events],
            "requests": requests, "fallback_without_http": True,
            "traceback_unattributed": True, "request_count": 3, "inspected_count": 6}


def main(**kwargs):
    from .stream_structured import main as run
    return run(stream_format="uvicorn", **kwargs)
