# API inspection --------------------------------------------------
# i.e. for:
#     .plotsrv\store\matplotlib__CPU

# In the browser:
# http://127.0.0.1:8000/history?view=matplotlib:CPU

# Expect (for 2 entries):

# {
#   "view_id": "matplotlib:CPU",
#   "count": 2,
#   "snapshots": [
#     {
#       "snapshot_id": "20260312T105404.869811Z",
#       "view_id": "matplotlib:CPU%",
#       "section": "matplotlib",
#       "label": "CPU%",
#       "kind": "plot",
#       "created_at": "2026-03-12T10:54:04.869811+00:00",
#       "payload_filename": "20260312T105404.869811Z__payload.png",
#       "payload_format": "png",
#       "size_bytes": 63117,
#       "payload_exists": true,
#       "extra": {

#       }
#     },
#     {
#       "snapshot_id": "20260312T105350.393556Z",
#       "view_id": "matplotlib:CPU%",
#       "section": "matplotlib",
#       "label": "CPU%",
#       "kind": "plot",
#       "created_at": "2026-03-12T10:53:50.393556+00:00",
#       "payload_filename": "20260312T105350.393556Z__payload.png",
#       "payload_format": "png",
#       "size_bytes": 62695,
#       "payload_exists": true,
#       "extra": {

#       }
#     }
#   ]
# }

# Storage mechanism --------------------------------------------------
#! For use within `plotsrv`, not `plotsrv-examples`
from pathlib import Path
import pandas as pd

from plotsrv.storage.backend import (
    write_snapshot,
    list_snapshots,
    load_snapshot,
    prune_snapshots,
)
from plotsrv.storage.policy import estimate_payload_size_bytes, should_store_snapshot

root = Path("./tmp_plotsrv_store")
view_id = "etl:metrics"

df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})

snaps_before = list_snapshots(root_dir=root, view_id=view_id)
size = estimate_payload_size_bytes(kind="table", obj=df)
decision = should_store_snapshot(
    view_id=view_id,
    payload_size_bytes=size,
    existing_snapshots=snaps_before,
)
print(decision)

snap = write_snapshot(
    root_dir=root,
    view_id=view_id,
    kind="table",
    obj=df,
    section="etl",
    label="metrics",
)
print(snap)

snaps_after = list_snapshots(root_dir=root, view_id=view_id)
print([s.snapshot_id for s in snaps_after])

loaded = load_snapshot(root_dir=root, view_id=view_id, snapshot_id=snap.snapshot_id)
print(type(loaded.obj))
print(loaded.obj)
