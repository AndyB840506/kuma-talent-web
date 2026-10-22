"""The Book a demo form of the built site, one real submission per language, to the live Apps Script.

    python site/demo_form_check.py <base-url> <alias-prefix>     e.g. http://127.0.0.1:8130 berandre2+site5

The form posts no-cors, so the page cannot read the reply: this checks that the request left with the
right payload and that the page showed its success message in its own language. Whether the row
reached the Sheet is checked apart (the Sheet is the only place that records it).
"""
import json
import sys
from playwright.sync_api import sync_playwright

BASE, ALIAS = sys.argv[1].rstrip("/"), sys.argv[2]
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OK = {"en": "Thanks. We'll reply within one business day.", "fr": "Merci. Nous répondons en un jour ouvrable.",
      "es": "Gracias. Respondemos en un día hábil.", "pt": "Obrigado. Respondemos em um dia útil."}
PATH = {"en": "/", "fr": "/fr/", "es": "/es/", "pt": "/pt/"}
results = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EDGE, headless=True)
    for lang, path in PATH.items():
        pg = b.new_page()
        sent = {}
        pg.on("request", lambda r: sent.update(body=r.post_data, status=None) if "script.google.com" in r.url else None)
        pg.on("requestfinished", lambda r: sent.update(done=True) if "script.google.com" in r.url else None)
        pg.goto(BASE + path, wait_until="networkidle")
        pg.fill("#bz-name", f"Site check {lang.upper()} (test, ignore)")
        pg.fill("#bz-company", "Kuma sprint 5 test")
        pg.fill("#bz-email", f"{ALIAS}-demo-{lang}@gmail.com")
        pg.fill("#bz-msg", f"Automated check of the {lang.upper()} page. Please ignore.")
        pg.click("#bz-submit")
        pg.wait_for_function("() => /ok|err/.test(document.querySelector('#bz-status').className)", timeout=60000)
        msg = pg.eval_on_selector("#bz-status", "e => e.textContent.trim()")
        payload = json.loads(sent.get("body") or "{}")
        good = (msg == OK[lang] and payload.get("email") == f"{ALIAS}-demo-{lang}@gmail.com"
                and payload.get("message", "").startswith(f"[HireSignal demo] [{lang.upper()}] ") and sent.get("done"))
        results[lang] = good
        print(f"{'PASS' if good else 'FAIL'}  {lang}  page=[{msg}]  finished={sent.get('done')}  message={payload.get('message')!r}")
        pg.close()
    b.close()
ok = len(results) == 4 and all(results.values())
print("VERDICT:", "PASS" if ok else "FAIL", f"({sum(results.values())}/4)")
sys.exit(0 if ok else 1)
