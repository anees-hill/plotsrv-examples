# Public landing page

This is a static page. Serve this directory at `demo.plotsrv.com`; Caddy redirects `/retail`, `/live` and `/scans` to their separate receiver subdomains. The previews are screenshots from local, synthetic demo runs. They are documentation images, not live iframes.

For a local check, run `.venv/bin/python -m http.server 8080 --directory site` and open `http://127.0.0.1:8080/`. The short links require the deployment's Caddy redirects, so they do not resolve through Python's static file server.
