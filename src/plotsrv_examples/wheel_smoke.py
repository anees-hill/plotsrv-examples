"""Install an explicit wheel in a fresh environment and check packaged behavior."""

import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

from PIL import Image

from .support.lifecycle import (LifecycleError, Processes, _json, _response,
                                available_port, interruption_cleanup, wait_evidence)
from .workspace import create


def main(wheel):
    result = {"suite": "wheel", "success": False, "manual_status": "pending", "release_signoff": "withheld",
              "scope": "packaged installation and basic receipt; separate from source release suite"}
    owner, temporary, code = None, None, 1
    try:
        wheel = Path(wheel).resolve(strict=True)
        if not wheel.is_file() or wheel.suffix != ".whl":
            raise ValueError("Select an existing .whl file")
        result["wheel"] = {"path": str(wheel), "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
        run = create(Path.cwd())
        result["workspace"] = str(run)
        # Virtual environments contain interpreter symlinks. Keep them outside
        # the diagnostic workspace, whose cleanup deliberately rejects symlinks.
        temporary = tempfile.TemporaryDirectory(prefix="plotsrv-wheel-")
        environment = Path(temporary.name)
        result["environment"] = {"path": str(environment), "retained": False}
        python = environment / "bin/python"
        config = run / "wheel.yml"
        config.write_text("storage-settings:\n  enabled: false\n")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("PLOTSRV_") and k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", MPLBACKEND="Agg",
                   MPLCONFIGDIR=str(run / "mpl"), XDG_CACHE_HOME=str(run / "cache"),
                   PLOTSRV_CONFIG=str(config))
        owner = Processes()
        with interruption_cleanup(), owner:
            child = owner.start(["uv", "venv", "--python", sys.executable, str(environment)],
                                cwd=run, env=env, label="wheel-venv")
            owner.wait(child, timeout=30)
            child = owner.start(["uv", "pip", "install", "--python", str(python), str(wheel)],
                                cwd=run, env=env, label="wheel-install")
            owner.wait(child, timeout=180)
            child = owner.start([str(python), "-B", "-c",
                "import json, plotsrv; from importlib.metadata import distribution, distributions; "
                "d=distribution('plotsrv'); print(json.dumps({'module':plotsrv.__file__, "
                "'version':d.version, 'direct_url':json.loads(d.read_text('direct_url.json')), "
                "'dependencies':sorted((x.metadata['Name'],x.version) for x in distributions())}))"],
                cwd=run, env=env, label="wheel-identity")
            owner.wait(child, timeout=15)
            identity = json.loads(child.output)
            if (not Path(identity["module"]).resolve().is_relative_to(environment.resolve())
                    or identity["direct_url"].get("dir_info", {}).get("editable")
                    or identity["direct_url"].get("url") != wheel.as_uri()):
                raise ValueError("Imported installation does not match selected wheel")
            result["candidate"] = identity
            port = available_port()
            receiver = owner.start([str(python), "-B", "-m", "plotsrv.cli_entry", "serve", "--config",
                str(config), "--host", "127.0.0.1", "--port", str(port), "--quiet"],
                cwd=run, env=env, label="wheel-receiver")
            wait_evidence(owner, receiver, port, timeout=20)
            publisher_code = (
                "import plotsrv as ps; import pandas as pd; import matplotlib.pyplot as plt; "
                f"opts=dict(host='127.0.0.1', port={port}, async_=False); "
                "ps.publish_view('wheel-received-sentinel', view_id='wheel-text', **opts); "
                "ps.publish_view(pd.DataFrame({'a':[1,2,3]}), view_id='wheel-table', **opts); "
                "fig, ax=plt.subplots(); ax.plot([1,2,3]); "
                "ps.publish_view(fig, view_id='wheel-plot', **opts); plt.close(fig)"
            )
            publisher = owner.start([str(python), "-B", "-c", publisher_code],
                                    cwd=run, env=env, label="wheel-publisher")
            owner.wait(publisher, timeout=30)
            wait_evidence(owner, receiver, port, timeout=5, view_id="wheel-text", sentinel="wheel-received-sentinel")
            table = _json(port, "/table/data?view=wheel-table", time.monotonic() + 5, owner)
            if table["rows"] != [{"a": 1}, {"a": 2}, {"a": 3}]:
                raise ValueError("Wheel table content differs")
            with Image.open(io.BytesIO(_response(port, "/plot?view=wheel-plot", time.monotonic() + 5,
                                                 owner, max_bytes=2 * 1024 * 1024))) as image:
                if image.format != "PNG":
                    raise ValueError("Wheel plot is not a PNG")
                image.verify()
            page = _response(port, "/", time.monotonic() + 5, owner, max_bytes=1024 * 1024).decode()
            assets = sorted(set(re.findall(r'(?:src|href)="(/static/[^"?]+)', page)))
            if not any(p.endswith(".js") for p in assets) or not any(p.endswith(".css") for p in assets):
                raise ValueError("Packaged page has no local JS/CSS")
            for asset in assets:
                if not _response(port, asset, time.monotonic() + 5, owner, max_bytes=4 * 1024 * 1024):
                    raise ValueError("Empty packaged asset: " + asset)
            result["evidence"] = {"text": "received sentinel", "table": "exact rows",
                                  "plot": "decoded PNG", "local_assets": assets}
        result["success"], code = True, 0
    except KeyboardInterrupt:
        result["error"], code = "Interrupted; owned children cleaned up", 130
    except (LifecycleError, OSError, ValueError, KeyError, http.client.HTTPException) as exc:
        result["error"] = str(exc)
    finally:
        if temporary is not None:
            try:
                temporary.cleanup()
            except OSError as exc:
                result.update(success=False, error="Temporary environment cleanup failed: " + str(exc))
                code = 1
        result["children"] = [{"label": c.label, "pid": c.process.pid, "exit": c.process.poll(),
                               "tail": c.diagnostic()} for c in owner.children] if owner else []
        result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
