"""Screenshots and layout checks of the built site, every page in every language, desktop and phone.

    python site/shots.py <base-url> <out-dir>      e.g. http://127.0.0.1:8130  E:/Sandbox/kuma-sprint5/shots

For each page: no sideways scroll (document width against the DEVICE width: on a phone the layout
viewport widens to fit an overflow, so innerWidth hides it), no console errors, no broken images,
the fonts loaded, and the page language is the one asked for. Prints a verdict over the full list.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2])
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
LANGS = {"en": ("/", "en"), "fr": ("/fr/", "fr"), "es": ("/es/", "es"), "pt": ("/pt/", "pt-BR")}
PAGES = [(l, p, path + sub, lang) for l, (path, lang) in LANGS.items() for p, sub in (("index", ""), ("try", "try/"))]
PAGES.append(("xx", "404", "/no-such-page/", "en"))
SIZES = {"1280": dict(viewport={"width": 1280, "height": 800}), "390": "iPhone 13"}

OUT.mkdir(parents=True, exist_ok=True)
expected = len(PAGES) * len(SIZES)
passed, fails = 0, []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EDGE, headless=True)
    for size, spec in SIZES.items():
        # Reduced motion: the sections come in on scroll (GSAP), which a full-page shot never
        # triggers; the pages skip the motion for reduced-motion visitors, so every section shows.
        ctx = b.new_context(**(p.devices[spec] if isinstance(spec, str) else spec), reduced_motion="reduce")
        dev_w = 390 if size == "390" else 1280
        for l, page, path, lang in PAGES:
            pg = ctx.new_page()
            errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            # The local server has no 404 page wired in; the host serves 404.html for a missing URL.
            r = pg.goto(BASE + ("/404.html" if page == "404" else path), wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            # Lazy images load only near the viewport: walk the page so every one is requested.
            pg.evaluate("""async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) {
                window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }""")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(1800)          # entrance motion settles
            # An image counts as broken unless it finished AND has pixels (a lazy one never
            # requested is incomplete, and would pass a check on complete images only).
            m = pg.evaluate("""() => ({ docW: document.documentElement.scrollWidth,
                lang: document.documentElement.lang,
                fonts: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family),
                broken: [...document.images].filter(i => !(i.complete && i.naturalWidth > 0)).map(i => i.src) })""")
            name = f"{l}-{page}-{size}.png"
            pg.screenshot(path=str(OUT / name), full_page=True)
            checks = {
                "status_200": r.status == 200,
                "no_sideways_scroll": m["docW"] <= dev_w,
                "no_console_errors": not errs,
                "no_broken_images": not m["broken"],
                "fonts_loaded": any("Geist" in f for f in m["fonts"]) and any("Zodiak" in f for f in m["fonts"]),
                "lang": m["lang"] == lang,
            }
            bad = [k for k, v in checks.items() if not v]
            if bad:
                fails.append(f"{name}: {bad} docW={m['docW']} errs={errs[:2]} broken={m['broken'][:2]}")
            else:
                passed += 1
            print(f"{'PASS' if not bad else 'FAIL'}  {name}  docW={m['docW']}", flush=True)
            pg.close()
        ctx.close()
    b.close()

for f in fails:
    print("  ", f)
print(f"VERDICT: {'PASS' if passed == expected else 'FAIL'} ({passed}/{expected})")
sys.exit(0 if passed == expected else 1)
