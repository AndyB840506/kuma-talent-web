"""The /try form of the built site against the PRODUCTION demo API, one run per site language.

    python site/try_form_check.py <base-url> <alias-prefix>     e.g. http://127.0.0.1:8130 berandre2+site5

Fills the real page and submits. When the page is served from anywhere but kumatalent.com the API's
CORS answer would not let the browser read the reply, so the request is forwarded with the site's
Origin and the reply handed back to the page unchanged except for the CORS header. Sends real
requests: each stores a demo request and emails a link to <alias-prefix>-<lang>@gmail.com.
Expects the success message in the page's own language. Do not open the emailed links.
"""
import sys
from playwright.sync_api import sync_playwright

BASE, ALIAS = sys.argv[1].rstrip("/"), sys.argv[2]
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
RUNS = [  # site path, level, interview language, languages to assess (none = skip the check)
    ("en", "/try/", "entry", "english", []),
    ("fr", "/fr/try/", "technical", "french", ["spanish"]),
    ("es", "/es/try/", "senior", "spanish", []),
    ("pt", "/pt/try/", "entry", "portuguese", ["english", "french"]),
]
results = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EDGE, headless=True)
    for lang, path, level, ilang, assess in RUNS:
        ctx = b.new_context()
        pg = ctx.new_page()
        seen = {}

        def forward(route):
            req = route.request
            headers = {**req.headers, "origin": "https://kumatalent.com", "referer": "https://kumatalent.com" + path}
            r = route.fetch(headers=headers, timeout=60000)
            seen["status"], seen["body"] = r.status, r.text()
            route.fulfill(response=r, headers={**r.headers, "access-control-allow-origin": "*"})
        pg.route("https://app.kumatalent.com/api/demo-request.php", forward)
        pg.goto(BASE + path, wait_until="networkidle")
        pg.check(f"#lvl-{level}", force=True)
        pg.check(f"#lang-{ilang}", force=True)
        if assess:
            pg.check("#assess-yes", force=True)
            for v in ("english", "french", "spanish", "portuguese"):
                pg.set_checked(f"#assess-{v}", v in assess, force=True)
        pg.check("#cv-sample", force=True)
        pg.fill("#try-name", f"Site check {lang.upper()}")
        pg.fill("#try-email", f"{ALIAS}-{lang}@gmail.com")
        pg.check("#try-consent", force=True)
        summary = pg.eval_on_selector("aside.summary dl", "e => e.innerText")
        pg.click("#try-submit")
        pg.wait_for_function("() => /ok|err/.test(document.querySelector('#try-status').className)", timeout=60000)
        cls = pg.eval_on_selector("#try-status", "e => e.className")
        msg = pg.eval_on_selector("#try-status", "e => e.textContent.trim()")
        results[lang] = "ok" in cls.split() and seen.get("status") == 200
        print(f"{'PASS' if results[lang] else 'FAIL'}  {lang}  http={seen.get('status')}  status=[{cls}] {msg}")
        print("      summary:", " | ".join(summary.split("\n")))
        print("      api:", seen.get("body", "")[:200])
        pg.screenshot(path=f"E:/Sandbox/kuma-sprint5/try-{lang}.png", full_page=False)
        ctx.close()
    b.close()
ok = len(results) == len(RUNS) and all(results.values())
print("VERDICT:", "PASS" if ok else "FAIL", f"({sum(results.values())}/{len(RUNS)})")
sys.exit(0 if ok else 1)
