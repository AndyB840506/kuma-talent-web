"""Renders the share image (og:image, 1200x630) for each language into assets/og/og-<lang>.jpg.

    python site/og.py

Kept apart from build.py because it needs a browser (Playwright with Edge) and the network for
the fonts; the images are committed, so a normal build does not need either. Run it again when
the hero tagline changes.
"""
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ZODIAK_CSS = "https://api.fontshare.com/v2/css?f[]=zodiak@300,301,400,401&display=swap"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400&family=Geist+Mono:wght@400&display=swap" rel="stylesheet">
<link href="%(zodiak)s" rel="stylesheet">
<style>
* { margin: 0; box-sizing: border-box; }
body { width: 1200px; height: 630px; overflow: hidden; background: #0b0a09; color: #f1ebe3; font-family: "Geist", sans-serif;
  position: relative; display: flex; flex-direction: column; justify-content: center; padding: 0 92px; }
.glow { position: absolute; width: 1100px; height: 1100px; left: -380px; top: -420px;
  background: radial-gradient(closest-side, rgba(122,94,87,.42), rgba(122,94,87,0)); }
.top, .foot { position: absolute; left: 92px; right: 92px; font-family: "Geist Mono", monospace; font-size: 22px;
  color: rgba(241,235,227,.5); letter-spacing: .02em; display: flex; justify-content: space-between; }
.top { top: 64px; } .foot { bottom: 64px; }
h1 { position: relative; font-weight: 400; font-size: 188px; line-height: .9; letter-spacing: -.055em; }
h1 i { font-family: "Zodiak", Georgia, serif; font-weight: 300; letter-spacing: -.035em; }
p { position: relative; margin-top: 36px; font-family: "Geist Mono", monospace; font-size: 30px; color: rgba(241,235,227,.7); }
p b { color: #8fd19e; font-weight: 400; }
</style></head><body>
<div class="glow"></div>
<div class="top"><span></span><span>%(short)s</span></div>
<h1>Hire<i>Signal</i></h1>
<p>%(a)s<br><b>%(b)s</b></p>
<div class="foot"><span>%(part)s</span><span>kumatalent.com</span></div>
</body></html>"""


def main():
    out = ROOT / "assets" / "og"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=EDGE, headless=True)
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        for f in sorted((ROOT / "site" / "copy").glob("*.json")):
            c = json.loads(f.read_text(encoding="utf-8"))
            e = lambda k: html.escape(c[k])
            pg.set_content(PAGE % {"zodiak": ZODIAK_CSS, "short": e("_short"), "a": e("hero_tagline"),
                                   "b": e("hero_tagline_b"), "part": e("foot_part")}, wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            dest = out / f"og-{f.stem}.jpg"
            pg.screenshot(path=str(dest), type="jpeg", quality=88)
            print(f"{dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)")
        b.close()


if __name__ == "__main__":
    sys.exit(main())
