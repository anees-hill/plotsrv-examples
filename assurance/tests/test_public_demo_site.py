"""The landing page should link to real demos and checked-in previews."""

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a":
            self.hrefs.append(values.get("href"))
        elif tag == "img":
            self.images.append(values.get("src"))


def test_site_has_only_three_live_entry_links_and_real_assets():
    parser = Links()
    parser.feed((ROOT / "site/index.html").read_text())
    assert {p for p in parser.hrefs if p and p.startswith("/")} == {
        "/", "/retail", "/live", "/scans"
    }
    for path in parser.images:
        assert path and path.startswith("/assets/")
        assert (ROOT / "site" / path.lstrip("/")).is_file()
    for name in ("retail", "live_import", "scan_audit", "markdown_docs"):
        assert (ROOT / "demos" / name / "README.md").is_file()
