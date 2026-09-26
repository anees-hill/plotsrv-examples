"""Assert Python application log suggestions from a real received stream."""


def verify(data):
    events = [row["data"] for row in data["records"]]
    if data["accepted_records"] != 4 or len(events) != 4:
        raise ValueError("Expected four application log frames")
    if [event["event"]["kind"] for event in events] != ["text"] * 4:
        raise ValueError("Application log frames were reinterpreted")
    if [event["raw"]["text"] for event in events] != [
        "INFO:worker.tasks:Job started\n",
        "WARNING:worker.tasks:Retrying one task\n",
        "ERROR:worker.db:Connection failed\n",
        "worker-note: this line stays in the raw stream\n",
    ]:
        raise ValueError("Raw application logs changed")
    profile = data["log_profile"]
    if (profile.get("kind") != "python_text" or profile.get("event_count") != 3
            or profile.get("inspected_count") != 4 or profile.get("time_origin") != "received"):
        raise ValueError("Python log interpretation is missing or miscounted")
    names = [recipe["name"] for recipe in profile["recipes"]]
    if names != ["Recent log events", "Warnings and errors",
                 "Events by level over time", "Busiest loggers"]:
        raise ValueError("Python log suggestions are incomplete")
    if any(recipe["sourceId"] != data["view_id"] for recipe in profile["recipes"]):
        raise ValueError("Python log suggestions target another stream")
    if data["http_profile"]["recipes"]:
        raise ValueError("Application logs gained HTTP suggestions")
    return {"log_events": 3, "raw_records": 4, "suggestions": names,
            "unrecognised_text_retained": True}


def main(**kwargs):
    from .stream_structured import main as run
    return run(stream_format="python_text", **kwargs)
