#!/usr/bin/env python3
"""Scriptorium build: content/*.html + site/ -> dist/.  Standard library only.

    python3 build.py           build into dist/
    python3 build.py --check   build, and exit 1 if any internal link is broken

A content file is an HTML fragment that starts with a metadata comment:

    <!--
    title: Game Rules
    category: Guides, Rules
    credits: Puppy101, Eucariot
    -->
    <p>...</p>

Files whose name starts with "_" are not pages (see _nav.html).
"""
import datetime, html, json, pathlib, re, shutil, sys
from collections import defaultdict
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent
CONTENT, SITE, DIST = ROOT / "content", ROOT / "site", ROOT / "dist"
META = re.compile(r"\A\s*<!--(.*?)-->\s*", re.S)


def parse_page(path):
    raw = path.read_text(encoding="utf-8")
    m = META.match(raw)
    meta = {}
    if m:
        for line in m.group(1).strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip()
        raw = raw[m.end():]
    slug = path.stem
    return {
        "slug": slug, "url": slug + ".html", "body": raw,
        "title": meta.get("title") or slug.replace("-", " ").title(),
        "categories": [c.strip() for c in meta.get("category", "").split(",") if c.strip()],
        "credits": [c.strip() for c in meta.get("credits", "").split(",") if c.strip()],
        "updated": meta.get("updated", ""),
    }


class Text(HTMLParser):
    """Strip tags -> plain text, for the search index and meta description."""
    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.skip -= 1
    def handle_data(self, d):
        if not self.skip: self.out.append(d)

def plain(fragment):
    p = Text(); p.feed(fragment)
    return re.sub(r"\s+", " ", " ".join(p.out)).strip()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs = []; self.ids = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("href"): self.hrefs.append(a["href"])
        if a.get("id"): self.ids.add(a["id"])


TABLE_WRAP = re.compile(r'<div class="table-scroll"([^>]*)>')

def nice_date(iso):
    """2026-02-13 -> 13 Feb 2026 (also accepts 2026-02 and 2026). Returns '' if unparseable."""
    for fmt, out in (("%Y-%m-%d", "%-d %b %Y"), ("%Y-%m", "%b %Y"), ("%Y", "%Y")):
        try: return datetime.datetime.strptime(iso, fmt).strftime(out)
        except ValueError: pass
    return ""


def add_data_notes(page):
    """After every <div class="table-scroll"> add <p class="data-note">Numbers last updated …</p>.
    Date = the wrapper's data-updated="…" if present, else the page's `updated:`. data-updated="none" opts out.
    Returns (body, number_of_tables_without_a_date)."""
    body, out, pos, undated = page["body"], [], 0, 0
    for m in TABLE_WRAP.finditer(body):
        if m.start() < pos: continue                      # nested inside a wrapper we already handled
        depth, i = 1, m.end()
        for tok in re.finditer(r"<div\b|</div>", body[m.end():]):
            depth += 1 if tok.group() == "<div" else -1
            if depth == 0: i = m.end() + tok.end(); break
        attr = re.search(r'data-updated="([^"]*)"', m.group(1))
        date = attr.group(1) if attr else page["updated"]
        out.append(body[pos:i]); pos = i
        if date == "none": continue
        shown = nice_date(date)
        if not shown: undated += 1; continue
        out.append(f'\n<p class="data-note">Numbers last updated {shown}. Changed? <a href="contribute.html">Help keep it current</a>.</p>')
    out.append(body[pos:])
    return "".join(out), undated


def category_slug(name):
    return "category-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fill(template, **values):
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def render(template, nav, page, extra_body=""):
    cats = ""
    if page["categories"]:
        links = " ".join(f'<a class="category-tag" href="{category_slug(c)}.html">{html.escape(c)}</a>' for c in page["categories"])
        cats = f'<p class="page__categories"><span class="page__categories-label">Categories:</span> {links}</p>'
    credits = ""
    if page["credits"]:
        names = ", ".join(html.escape(c) for c in page["credits"])
        credits = (f'<details class="page__credits"><summary>Contributors ({len(page["credits"])})</summary>'
                   f'<p>Written by the Utopia community on the original wiki: {names}.</p></details>')
    body, _ = add_data_notes(page)
    body += extra_body
    return fill(template, title=html.escape(page["title"]), body=body, nav=nav, categories=cats, credits=credits,
                description=html.escape(plain(page["body"])[:160]))


def main():
    check = "--check" in sys.argv
    if DIST.exists(): shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(SITE / "assets", DIST / "assets")
    template = (SITE / "template.html").read_text(encoding="utf-8")
    nav = (CONTENT / "_nav.html").read_text(encoding="utf-8") if (CONTENT / "_nav.html").exists() else ""

    pages = [parse_page(p) for p in sorted(CONTENT.glob("*.html")) if not p.name.startswith("_")]
    by_slug = {p["slug"]: p for p in pages}
    by_cat = defaultdict(list)
    for p in pages:
        for c in p["categories"]: by_cat[c].append(p)

    generated = []
    for c, members in sorted(by_cat.items()):
        items = "".join(f'<li><a href="{m["url"]}">{html.escape(m["title"])}</a></li>' for m in sorted(members, key=lambda m: m["title"].lower()))
        generated.append({"slug": category_slug(c), "url": category_slug(c) + ".html", "title": f"Category: {c}",
                          "body": f'<ul class="page-list">{items}</ul>', "categories": [], "credits": []})
    items = "".join(f'<li><a href="{p["url"]}">{html.escape(p["title"])}</a></li>' for p in sorted(pages, key=lambda p: p["title"].lower()))
    generated.append({"slug": "all-pages", "url": "all-pages.html", "title": "All pages",
                      "body": f'<ul class="page-list page-list--all">{items}</ul>', "categories": [], "credits": []})
    generated.append({"slug": "404", "url": "404.html", "title": "Page not found",
                      "body": '<p>That page does not exist (yet). Try the search box, or see <a href="all-pages.html">all pages</a>.</p>',
                      "categories": [], "credits": []})

    everything = pages + generated
    known = {p["url"] for p in everything} | {"search-index.json"}
    broken = []
    for p in everything:
        (DIST / p["url"]).write_text(render(template, nav, p), encoding="utf-8")
        lp = Links(); lp.feed(p["body"])
        for href in lp.hrefs:
            if re.match(r"^(https?:|mailto:|#)", href): continue
            target = href.split("#")[0]
            if target and target not in known: broken.append((p["slug"], href))
    for p in pages:
        undated = add_data_notes(p)[1]
        if undated: print(f"WARNING: {p['slug']}: {undated} table(s) have no date (add 'updated: YYYY-MM-DD' to the page header)", file=sys.stderr)
    if "index" not in by_slug: print("WARNING: no content/index.html (home page)", file=sys.stderr)

    index = [{"t": p["title"], "u": p["url"], "x": plain(p["body"])} for p in pages]
    (DIST / "search-index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DIST / ".nojekyll").write_text("")

    print(f"built {len(pages)} pages + {len(generated)} generated -> {DIST.relative_to(ROOT)}/")
    if broken:
        print(f"{len(broken)} broken internal links:", file=sys.stderr)
        for slug, href in broken[:40]: print(f"  {slug}: {href}", file=sys.stderr)
        if check: sys.exit(1)


if __name__ == "__main__":
    main()
