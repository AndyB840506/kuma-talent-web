"""Builds the HireSignal site from shared partials, one template per page and one copy file per language.

    python site/build.py                  -> site/out/, laid out exactly as it is served: index.html and
                                             try/index.html for English, fr/ es/ pt/ for the others, plus
                                             404.html, fr.html (the old French URL, now a redirect),
                                             sitemap.xml and robots.txt (root-relative /assets/ paths)
    python site/build.py --root           -> the same files into the repo root, which is what the live
                                             site serves: committing them and pushing master publishes
    python site/build.py --inline OUTDIR  -> a self-contained English preview for a private Artifact:
                                             OUTDIR/hiresignal-concept.html (main page) + OUTDIR/try.html,
                                             fonts and images embedded, forms send nothing.

Why a build and not hand-copied pages: the old site kept index.html and fr.html as two full copies,
and every change had to be made twice. Here a language is a JSON file and the pages are shared.

The build refuses to write anything when:
  - a language file is missing a key that English has, or a {placeholder} it needs,
  - a marker is left unresolved,
  - the copy contains an em dash, a middle dot or a hyphenated word (house style; see ALLOW).
"""
import base64
import html
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
COPY = SITE / "copy"
PAGES = SITE / "pages"
OUT = SITE / "out"

# Interview languages the PRODUCT supports today. The page must not promise more than this.
# ES and PT since HireSignal 1.6.0 (candidate side) and 1.10.0 (report and admin).
INTERVIEW_LANGS = ["english", "french", "spanish", "portuguese"]
# Where the /try form posts (HireSignal sprint 4). HS_APP_URL points a local build at a local app.
APP_URL = os.environ.get("HS_APP_URL", "https://app.kumatalent.com").rstrip("/")
SITE_LANGS = ["en", "fr", "es", "pt"]
LANG_PATH = {"en": "/", "fr": "/fr/", "es": "/es/", "pt": "/pt/"}
PAGE_PATH = {"index": "", "try": "try/"}
INLINE_FILE = {"index": "hiresignal-concept.html", "try": "try.html"}
INLINE_HREF = {"index": "./", "try": "try.html"}
ALLOW = {"co-founder", "e-mail"}
ZODIAK_CSS = "https://api.fontshare.com/v2/css?f[]=zodiak@300,301,400,401&display=swap"
CHANGE_ROWS = 6
SITE_URL = "https://kumatalent.com"
PAGE_META = {"index": ("meta_title", "meta_description"), "try": ("cfg_meta_title", "cfg_meta_description")}
OG_LOCALE = {"en": "en_CA", "fr": "fr_CA", "es": "es_LA", "pt": "pt_BR"}
# Built once, not per language: the page is bilingual by listing every language (see render_404).
SINGLE_PAGES = {"404"}


def load_copies():
    copies = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted(COPY.glob("*.json"))}
    # French puts a no-break space before : ; ! ? (same rule as the HireSignal catalogs).
    if "fr" in copies:
        copies["fr"] = {k: re.sub(r" ([:;!?])", " \\1", v) if isinstance(v, str) else v
                        for k, v in copies["fr"].items()}
    return copies


def lint(lang, copy):
    errors = []
    for k, v in copy.items():
        if k.startswith("_") or not isinstance(v, str):
            continue
        if "—" in v:
            errors.append(f"{lang}.{k}: em dash")
        if "·" in v:
            errors.append(f"{lang}.{k}: middle dot")
        for w in re.findall(r"\b[\wÀ-ſ]+-[\wÀ-ſ]+\b", v):
            if w.lower() not in ALLOW:
                errors.append(f"{lang}.{k}: hyphenated '{w}'")
    return errors


def fill(text, copy):
    def ph(m):
        if m.group(1) not in copy:
            raise KeyError(f"placeholder {{{m.group(1)}}} has no value")
        return copy[m.group(1)]
    return re.sub(r"\{([a-z_]+)\}", ph, text)


def fmt(text, copy):
    """Escape, fill {placeholders}, turn *word* into the serif italic."""
    return re.sub(r"\*([^*]+)\*", r'<span class="it">\1</span>', html.escape(fill(text, copy), quote=True))


def plain(text, copy):
    return html.escape(fill(text, copy).replace("*", ""), quote=True)


def data_uri(path, max_w=None, quality=82):
    from PIL import Image
    p = ROOT / "assets" / path
    if p.suffix.lower() in (".jpg", ".jpeg", ".png") and max_w:
        im = Image.open(p)
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        if p.suffix.lower() == ".png":
            im.save(buf, "PNG", optimize=True); mime = "image/png"
        else:
            im.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True); mime = "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()
    mime = {".pdf": "application/pdf", ".png": "image/png"}.get(p.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


_zodiak = None
def zodiak_inline():
    global _zodiak
    if _zodiak:
        return _zodiak
    css = urllib.request.urlopen(ZODIAK_CSS, timeout=30).read().decode()
    faces = []
    for block in re.findall(r"@font-face\s*\{.*?\}", css, re.S):
        if re.search(r"font-style:\s*(\w+)", block).group(1) != "italic":
            continue
        w = re.search(r"font-weight:\s*(\d+)", block).group(1)
        url = "https:" + re.search(r"url\('(//[^']+\.woff2)'\)", block).group(1)
        data = urllib.request.urlopen(url, timeout=30).read()
        faces.append(f"@font-face {{ font-family: 'Zodiak'; font-style: italic; font-weight: {w}; font-display: swap;"
                     f" src: url(data:font/woff2;base64,{base64.b64encode(data).decode()}) format('woff2'); }}")
    if not faces:
        raise RuntimeError("no Zodiak italic faces found")
    _zodiak = "<style>\n" + "\n".join(faces) + "\n</style>"
    return _zodiak


def includes(text):
    for _ in range(3):
        text = re.sub(r"\{\{include:([^}]+)\}\}", lambda m: (SITE / m.group(1)).read_text(encoding="utf-8").rstrip("\n"), text)
    return text


def page_href(lang, page, inline):
    page = {"home": "index"}.get(page, page)
    return INLINE_HREF[page] if inline else LANG_PATH[lang] + PAGE_PATH[page]


def page_url(lang, page):
    return SITE_URL + LANG_PATH[lang] + PAGE_PATH[page]


def seo_head(page, lang, copy, copies, built):
    """Canonical, language alternates, share card and favicon; on the main page, the JSON-LD too."""
    title, desc = (plain(copy[k], copy) for k in PAGE_META[page])
    image = f"{SITE_URL}/assets/og/og-{lang}.jpg"
    tags = [f'<link rel="canonical" href="{page_url(lang, page)}">']
    tags += [f'<link rel="alternate" hreflang="{copies[l]["_locale"]}" href="{page_url(l, page)}">' for l in built]
    tags += [f'<link rel="alternate" hreflang="x-default" href="{page_url("en", page)}">',
             '<meta name="robots" content="index, follow">',
             '<link rel="icon" type="image/png" href="/assets/logo/isotipo-light.png">',
             '<meta property="og:type" content="website">',
             '<meta property="og:site_name" content="HireSignal">',
             f'<meta property="og:title" content="{title}">',
             f'<meta property="og:description" content="{desc}">',
             f'<meta property="og:url" content="{page_url(lang, page)}">',
             f'<meta property="og:locale" content="{OG_LOCALE[lang]}">']
    tags += [f'<meta property="og:locale:alternate" content="{OG_LOCALE[l]}">' for l in built if l != lang]
    tags += [f'<meta property="og:image" content="{image}">',
             '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
             f'<meta property="og:image:alt" content="{plain(copy["hero_tagline"], copy)} {plain(copy["hero_tagline_b"], copy)}">',
             '<meta name="twitter:card" content="summary_large_image">']
    if page == "index":
        org = {"@type": "Organization", "@id": SITE_URL + "/#org", "name": "Kuma Group", "url": SITE_URL + "/",
               "logo": SITE_URL + "/assets/logo/logo-principal.png", "email": copy["contact_email"],
               "founder": [{"@type": "Person", "name": copy["team_h_name"]}, {"@type": "Person", "name": copy["team_a_name"]}]}
        app = {"@type": "SoftwareApplication", "name": "HireSignal", "url": page_url(lang, page),
               "applicationCategory": "BusinessApplication", "operatingSystem": "Web",
               "description": fill(copy["meta_description"], copy), "inLanguage": copy["_locale"],
               "publisher": {"@id": SITE_URL + "/#org"}}
        ld = json.dumps({"@context": "https://schema.org", "@graph": [org, app]}, ensure_ascii=False)
        tags.append('<script type="application/ld+json">' + ld.replace("</", "<\\/") + "</script>")
    return "\n".join(tags)


def render(template, page, lang, copy, copies, inline):
    built = [l for l in SITE_LANGS if l in copies]
    full_doc = (f'<!doctype html>\n<html lang="{copy["_locale"]}">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
    sub = {}
    if inline:
        main = page == "index"
        sub.update(doc_open="" if main else full_doc, doc_body="" if main else "</head>\n<body>",
                   doc_close="" if main else "</body>\n</html>",
                   head_extra='<meta name="claude:viewport-fit-sides" content="cover">' if main else "",
                   zodiak=zodiak_inline(), preview="true")
        if main:
            sub["meta_title"] = "HireSignal Concept"
    else:
        sub.update(doc_open=full_doc, doc_body="</head>\n<body>", doc_close="</body>\n</html>",
                   head_extra=seo_head(page, lang, copy, copies, built),
                   zodiak=f'<link href="{ZODIAK_CSS}" rel="stylesheet">', preview="false")
    sub["nav_base"] = "" if page == "index" else page_href(lang, "index", inline)
    sub["demo_api"] = json.dumps(APP_URL + "/api/demo-request.php")
    links = []
    for l in built:
        cur = ' aria-current="true"' if l == lang else ""
        href = "#" if inline else LANG_PATH[l] + PAGE_PATH[page]
        links.append(f'<a href="{href}" lang="{copies[l]["_locale"]}"{cur}>{copies[l]["_short"]}</a>')
    sub["lang_links"] = "".join(links)
    sub["lang_radios"] = "".join(
        f'<label><input type="radio" name="language" id="lang-{v}" value="{v}"{" checked" if i == 0 else ""}>'
        f'{html.escape(copy["lang_" + v])}</label>' for i, v in enumerate(INTERVIEW_LANGS))
    sub["try_assess_options"] = "".join(
        f'<label for="assess-{v}"><input type="checkbox" name="assess_lang" id="assess-{v}" value="{v}"'
        f'{" checked" if i == 0 else ""}>{html.escape(copy["lang_" + v])}</label>' for i, v in enumerate(INTERVIEW_LANGS))
    sub["change_rows"] = "\n        ".join(
        f'<div class="crow" role="row"><span class="k" role="rowheader">{fmt(copy[f"change_r{i}_k"], copy)}</span>'
        f'<span class="a" role="cell" data-l="{plain(copy["change_col_today"], copy)}">{fmt(copy[f"change_r{i}_a"], copy)}</span>'
        f'<span class="b" role="cell">{fmt(copy[f"change_r{i}_b"], copy)}</span></div>' for i in range(1, CHANGE_ROWS + 1))

    def repl(m):
        key = m.group(1)
        if key in sub:
            return sub[key]
        if key.startswith("path:"):
            return page_href(lang, key[5:], inline)
        if key.startswith("asset:"):
            path = key[6:]
            if inline:
                return data_uri(path, max_w={"founders": 480, "hiresignal": 900, "logo": 96}.get(path.split("/")[0]))
            return "/assets/" + path
        if key.startswith("href:"):
            return "#" if inline else "/assets/" + key[5:]
        if key.startswith("js:"):
            return json.dumps(fill(copy[key[3:]], copy))
        if key.endswith("_plain") and key[:-6] in copy:
            return plain(copy[key[:-6]], copy)
        if key not in copy:
            raise KeyError(f"{lang}/{page}: missing key '{key}'")
        return fmt(copy[key], copy)

    out = re.sub(r"\{\{([^}]+)\}\}", repl, includes(template))
    left = re.findall(r"\{\{[^}]+\}\}", out)
    if left:
        raise RuntimeError(f"{lang}/{page}: unresolved markers {left[:5]}")
    return out


def main():
    copies = load_copies()
    errors = [e for l, c in copies.items() for e in lint(l, c)]
    base = set(copies["en"])
    for l, c in copies.items():
        errors += [f"{l}: missing '{k}'" for k in sorted(base - set(c))]
    if errors:
        print("REFUSED:\n  " + "\n  ".join(errors)); sys.exit(1)
    pages = {p.stem: p.read_text(encoding="utf-8") for p in sorted(PAGES.glob("*.html"))}
    single = {p: pages.pop(p) for p in SINGLE_PAGES}
    if len(sys.argv) > 2 and sys.argv[1] == "--inline":
        outdir = Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
        rendered = {p: render(t, p, "en", copies["en"], copies, inline=True) for p, t in pages.items()}
        for p, page in rendered.items():
            (outdir / INLINE_FILE[p]).write_text(page, encoding="utf-8", newline="\n")
            print(f"inline {p} -> {outdir / INLINE_FILE[p]} ({len(page.encode())} bytes)")
        return
    base = ROOT if sys.argv[1:] == ["--root"] else OUT
    built = [l for l in SITE_LANGS if l in copies]
    files = {(LANG_PATH[l] + PAGE_PATH[p]).lstrip("/") + "index.html": render(t, p, l, copies[l], copies, inline=False)
             for l in built for p, t in pages.items()}
    files["404.html"] = render_404(single["404"], copies, built)
    files["fr.html"] = redirect_page(LANG_PATH["fr"])
    files["sitemap.xml"] = sitemap(pages, copies, built)
    files["robots.txt"] = f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    for rel, text in files.items():
        dest = base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8", newline="\n")
        print(f"{dest.relative_to(ROOT)} ({len(text.encode())} bytes)")


def render_404(template, copies, built):
    """One page for every language: the host serves it for any missing URL, whatever the language."""
    en = copies["en"]
    rows = "\n      ".join(
        f'<p lang="{copies[l]["_locale"]}"><span class="mono">{plain(copies[l]["nf_title"], copies[l])}</span>'
        f' <a href="{LANG_PATH[l]}">{plain(copies[l]["nf_home"], copies[l])} <span aria-hidden="true">&rarr;</span></a></p>'
        for l in built)
    full_doc = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
    out = includes(template)
    for k, v in {"doc_open": full_doc, "doc_body": "</head>\n<body>", "doc_close": "</body>\n</html>",
                 "nf_rows": rows, "meta_title": plain(en["nf_title"], en),
                 "zodiak": f'<link href="{ZODIAK_CSS}" rel="stylesheet">'}.items():
        out = out.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[^}]+\}\}", out)
    if left:
        raise RuntimeError(f"404: unresolved markers {left[:5]}")
    return out


def redirect_page(target):
    """A static host cannot send a 301 here, so the old URL sends the browser on and tells search engines where."""
    url = SITE_URL + target
    return (f'<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n<title>HireSignal</title>\n'
            f'<link rel="canonical" href="{url}">\n<meta name="robots" content="noindex, follow">\n'
            f'<meta http-equiv="refresh" content="0; url={target}">\n'
            f'<script>location.replace({json.dumps(target)});</script>\n</head>\n<body>\n'
            f'<p><a href="{target}">{url}</a></p>\n</body>\n</html>\n')


def sitemap(pages, copies, built):
    urls = []
    for p in pages:
        alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{copies[l]["_locale"]}" href="{page_url(l, p)}"/>' for l in built)
        alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{page_url("en", p)}"/>'
        urls += [f"  <url>\n    <loc>{page_url(l, p)}</loc>{alts}\n  </url>" for l in built]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(urls) + "\n</urlset>\n")


if __name__ == "__main__":
    main()
