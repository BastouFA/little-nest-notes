#!/usr/bin/env python3
"""Build the deployable site: copy site/ -> dist/ and fill every {{PLACEHOLDER}}.

    python3 scripts/apply_links.py            # build dist/
    python3 scripts/apply_links.py --check    # only report what is still unfilled

Placeholders come from links.json:
  - "site":  {{SITE_URL}}, {{AUTHOR_NAME}}, {{CONTACT_EMAIL}} ...
             Any "site" value can be overridden by an environment variable of
             the same name (e.g. set SITE_URL or PLAUSIBLE_DOMAIN in the
             Netlify/Vercel dashboard). See .env.example.
  - "links": {{AFFILIATE_LINK_<KEY>}} -> your affiliate URL, or the product's
             official URL ("fallback") while you are not approved yet, so the
             live site never shows a broken {{...}} link.

site/ is never modified, so you can re-run this any time. Netlify, Vercel and
the GitHub Pages workflow run it automatically on each deploy.

Analytics: if PLAUSIBLE_DOMAIN is set (links.json "site" block or env var),
the cookieless Plausible script is added to every page's <head>. If it is
empty, no analytics script is added at all.
"""
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site"
OUT = ROOT / "dist"
CONFIG = ROOT / "links.json"
TEXT_EXT = {".html", ".xml", ".txt", ".css", ".js", ".json", ".webmanifest", ".svg", ""}
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
FILL_IN = re.compile(r"\[\[FILL IN[^\]]*\]\]")
PLAUSIBLE_SRC = "https://plausible.io/js/script.js"  # keep in sync with the CSP below
# Security policy sent as a header by site/_headers (Netlify) and vercel.json. GitHub Pages
# cannot send headers, so its workflow sets EMBED_SECURITY_META=1 and the build
# adds the same policy as <meta> tags instead (frame-ancestors is header-only).
CSP = ("default-src 'self'; script-src 'self' https://plausible.io; connect-src 'self' https://plausible.io; "
       "img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; object-src 'none'; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests")


def load_values():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    values, status = {}, {}
    for key, val in cfg.get("site", {}).items():
        val = os.environ.get(key) or val  # a non-empty host env var wins over links.json
        values[key] = val.rstrip("/") if key == "SITE_URL" else val
    for key, entry in cfg.get("links", {}).items():
        name = f"AFFILIATE_LINK_{key}"
        aff = (entry.get("affiliate") or "").strip()
        values[name] = aff or entry.get("fallback", "").strip()
        status[name] = "affiliate" if aff else "fallback"
    return values, status


def check_sitemap():
    """Warn if an indexable page is missing from sitemap.xml (or a listed one does not exist)."""
    sitemap = (SRC / "sitemap.xml").read_text(encoding="utf-8")
    listed = set(re.findall(r"<loc>\{\{SITE_URL\}\}(/[^<]*)</loc>", sitemap))
    pages = set()
    for p in SRC.rglob("index.html"):
        if 'name="robots" content="noindex' in p.read_text(encoding="utf-8"):
            continue
        rel = p.parent.relative_to(SRC).as_posix()
        pages.add("/" if rel == "." else f"/{rel}/")
    for url in sorted(pages - listed):
        print(f"WARNING: {url} is not in site/sitemap.xml")
    for url in sorted(listed - pages):
        print(f"WARNING: sitemap.xml lists {url} but there is no indexable page there")


def check_host_configs():
    """Warn if the Netlify (site/_headers) or Vercel (vercel.json) headers drift from the CSP above."""
    for name in ("site/_headers", "vercel.json"):
        path = ROOT / name
        if path.exists() and CSP not in path.read_text(encoding="utf-8"):
            print(f"WARNING: the Content-Security-Policy in {name} differs from CSP in scripts/apply_links.py")


def no_email(text):
    """CONTACT_EMAIL is empty: turn email links into plain text instead of broken mailto: links."""
    text = text.replace('<a href="mailto:{{CONTACT_EMAIL}}">{{CONTACT_EMAIL}}</a>', "[email address coming soon]")
    text = re.sub(r'<a href="mailto:\{\{CONTACT_EMAIL\}\}">([^<]*)</a>', r"\1 (email coming soon)", text)
    return text.replace("{{CONTACT_EMAIL}}", "")


def head_extras(domain):
    """Return (tags placed right after <meta charset>, tags placed before </head>)."""
    top = bottom = ""
    if os.environ.get("EMBED_SECURITY_META") == "1":
        meta_csp = CSP.replace(" frame-ancestors 'none';", "")
        top = (f'\n<meta http-equiv="Content-Security-Policy" content="{meta_csp}">'
               '\n<meta name="referrer" content="strict-origin-when-cross-origin">')
    if domain:
        bottom = f'<script defer data-domain="{html.escape(domain)}" src="{PLAUSIBLE_SRC}"></script>\n'
    return top, bottom


def main():
    check_only = "--check" in sys.argv
    values, status = load_values()

    used, missing = set(), {}
    files = [p for p in SRC.rglob("*") if p.is_file()]
    for p in files:
        if p.suffix not in TEXT_EXT:
            continue
        for m in PLACEHOLDER.finditer(p.read_text(encoding="utf-8")):
            used.add(m.group(1))
            if not values.get(m.group(1)) and m.group(1) != "CONTACT_EMAIL":
                missing.setdefault(m.group(1), set()).add(str(p.relative_to(ROOT)))

    aff = sorted(k for k in used if status.get(k) == "affiliate")
    fb = sorted(k for k in used if status.get(k) == "fallback")
    print(f"Affiliate links filled : {len(aff)}")
    print(f"Using official fallback: {len(fb)}" + (f"  -> {', '.join(k.replace('AFFILIATE_LINK_', '') for k in fb)}" if fb else ""))
    placeholder_site = values.get("SITE_URL", "")
    if "example" in placeholder_site:
        print(f"NOTE: SITE_URL is still {placeholder_site!r} - set it in links.json after your first deploy.")
    if values.get("AUTHOR_NAME", "") in ("", "Your Name") or not values.get("CONTACT_EMAIL") or "example.com" in values["CONTACT_EMAIL"]:
        print("NOTE: AUTHOR_NAME / CONTACT_EMAIL in links.json are still the sample values.")
    fill_ins = sorted({k for k, v in values.items() if isinstance(v, str) and FILL_IN.search(v)})
    if fill_ins:
        print(f"NOTE: still marked [[FILL IN]] in links.json (shown on the privacy/terms pages): {', '.join(fill_ins)}")
    for p in files:
        if p.suffix in TEXT_EXT and FILL_IN.search(p.read_text(encoding="utf-8")):
            print(f"NOTE: [[FILL IN]] text left in {p.relative_to(ROOT)}")
    domain = values.get("PLAUSIBLE_DOMAIN", "").strip()
    print(f"Analytics (Plausible)  : {'ON for ' + domain if domain else 'off (PLAUSIBLE_DOMAIN is empty)'}")
    check_sitemap()
    check_host_configs()
    if missing:
        print("\nERROR - placeholders with no value in links.json:")
        for k, where in sorted(missing.items()):
            print(f"  {{{{{k}}}}}  in {', '.join(sorted(where))}")
        sys.exit(1)
    if check_only:
        return

    top, bottom = head_extras(domain)
    if OUT.exists():
        shutil.rmtree(OUT)
    for p in files:
        dest = OUT / p.relative_to(SRC)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix in TEXT_EXT:
            text = p.read_text(encoding="utf-8")
            if not values.get("CONTACT_EMAIL"):
                text = no_email(text)
            text = PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
            if p.suffix == ".html":
                if top:
                    text = text.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + top, 1)
                if bottom:
                    text = text.replace("</head>", bottom + "</head>", 1)
            dest.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(p, dest)
    print(f"\nBuilt {len(files)} files into {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
