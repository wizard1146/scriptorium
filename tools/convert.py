#!/usr/bin/env python3
"""Convert MediaWiki-rendered HTML (data/rendered/) into clean content fragments (content/).
Stdlib only. Re-runnable during the migration: it overwrites content/*.html EXCEPT files marked `origin: scriptorium` in their
metadata comment (hand-written pages) and _nav.html. Once content/ is committed, treat it as the source of truth and stop running this.

What it does to each page:
  * inline styles -> semantic classes (cell-good, cell-bad, cell-head, ...); every other style/attr is dropped
  * <table> -> <div class="table-scroll"><table>
  * mw-collapsible divs -> <details>
  * links: /index.php?title=X -> x.html (redirects resolved); red links / unknown targets -> plain text
  * strips MediaWiki comments, section-edit leftovers, span.mw-headline wrappers
"""
import html, json, pathlib, re, sys, urllib.parse
from collections import Counter
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOID = {"br", "hr", "img", "meta", "link", "input", "wbr"}
KEEP_TAGS = {"p", "br", "hr", "b", "strong", "i", "em", "u", "s", "sub", "sup", "small", "big", "span", "div", "a",
             "ul", "ol", "li", "dl", "dt", "dd", "table", "thead", "tbody", "tr", "th", "td", "caption",
             "h1", "h2", "h3", "h4", "h5", "h6", "pre", "code", "blockquote", "center", "img", "details", "summary"}
PREFIX = {0: "", 4: "", 12: "help-"}
# MediaWiki's own editing manual is obsolete on a static site; contribute.html is hand-written (see CONTRIBUTING.md).
SKIP_TITLES = {"Game Rules", "The Utopian Encyclopedia:Bots", "The Utopian Encyclopedia:Copyrights", "The Utopian Encyclopedia:Administrators",
               "The Utopian Encyclopedia:Bureaucrats"}
SLUG_OVERRIDES = {"Welcome to the Utopia Wiki": "index", "Help:Contribute": "contribute"}
def skipped(title, ns): return ns == 12 or title in SKIP_TITLES


def slugify(title, ns):
    s = re.sub(r"[^a-z0-9]+", "-", title.split(":", 1)[-1].lower() if ns in (4, 12) else title.lower()).strip("-")
    return PREFIX[ns] + (s or "page")


# ---------- tiny DOM ----------
class Node:
    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.kids, self.parent = tag, dict(attrs or {}), [], None
    def add(self, k):
        if isinstance(k, Node): k.parent = self
        self.kids.append(k)
    def text(self):
        return "".join(k if isinstance(k, str) else k.text() for k in self.kids)


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root"); self.cur = self.root
    def handle_starttag(self, tag, attrs):
        n = Node(tag, [(k, v or "") for k, v in attrs]); self.cur.add(n)
        if tag not in VOID: self.cur = n
    def handle_startendtag(self, tag, attrs):
        self.cur.add(Node(tag, [(k, v or "") for k, v in attrs]))
    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag: n = n.parent
        if n is not self.root: self.cur = n.parent
    def handle_data(self, d): self.cur.add(d)
    # comments are dropped by simply not handling them


def parse(fragment):
    b = Builder(); b.feed(fragment); return b.root


# ---------- style -> class ----------
def hex_to_rgb(v):
    m = re.search(r"#([0-9a-f]{3}|[0-9a-f]{6})\b", v.lower())
    if not m: return None
    h = m.group(1); h = "".join(c * 2 for c in h) if len(h) == 3 else h
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def bg_class(style):
    m = re.search(r"background(?:-color)?\s*:\s*([^;]+)", style, re.I)
    rgb = hex_to_rgb(m.group(1)) if m else None
    if not rgb:
        return None
    r, g, b = rgb
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if lum > 0.97: return None                       # white
    if lum < 0.3: return "cell-dark"
    if max(r, g, b) - min(r, g, b) < 24: return "cell-band"   # greys
    if b > r and b >= g - 10: return "cell-head"     # blues -> headings
    if g - max(r, b) >= 10: return "cell-good" if lum > 0.7 else "cell-head"   # clearly green
    if r - max(g, b) >= 25: return "cell-bad" if lum > 0.7 else "cell-dark"    # clearly red
    return None                                                                # tans, beiges etc: no semantic meaning


class Ctx:
    def __init__(self, slugs, redirects):
        self.slugs, self.redirects, self.missing, self.stats = slugs, redirects, Counter(), Counter()


def norm_title(t):
    t = urllib.parse.unquote(t).replace("_", " ").strip()
    return t[:1].upper() + t[1:]


def resolve(title, ctx):
    for _ in range(5):
        if title in ctx.redirects:
            target = ctx.redirects[title]
            base, _, frag = target.partition("#")
            title = norm_title(base)
            if frag: return ctx.slugs.get(title), frag
        else: break
    return ctx.slugs.get(title), None


def fix_href(href, ctx):
    u = urllib.parse.urlparse(href.replace("&amp;", "&"))
    if u.netloc and "wiki.utopia-game.com" not in u.netloc: return href  # external
    if u.scheme in ("mailto",): return href
    q = urllib.parse.parse_qs(u.query)
    if "redlink" in q or q.get("action", ["view"])[0] != "view": return None
    if u.path.endswith("index.php") and "title" in q:
        title = norm_title(q["title"][0])
    elif u.path.startswith("/index.php/"):
        title = norm_title(u.path[len("/index.php/"):])
    elif not u.path and u.fragment:
        return "#" + u.fragment
    else:
        return href
    slug, rfrag = resolve(title, ctx)
    if not slug:
        ctx.missing[title] += 1
        return None
    frag = u.fragment or rfrag
    return slug + ".html" + ("#" + frag.replace(" ", "_") if frag else "")


# ---------- transform ----------
def clean(node, ctx):
    """Return a list of nodes/strings replacing `node`."""
    if isinstance(node, str): return [node]
    tag, a = node.tag, node.attrs
    cls = a.get("class", "").split()
    style = a.get("style", "")

    if tag in ("script", "style", "noscript"): return []
    if tag == "span" and "mw-headline" in cls:  # the id moves onto the heading (handled in the heading branch)
        return [k for kid in node.kids for k in clean(kid, ctx)]
    if tag == "a":
        href = fix_href(a.get("href", ""), ctx) if a.get("href") else None
        kids = [k for kid in node.kids for k in clean(kid, ctx)]
        if href is None:
            if a.get("href", "").startswith("/index.php") or "new" in cls: ctx.stats["links-unwrapped"] += 1
            return kids
        n = Node("a", [("href", href)]); [n.add(k) for k in kids]; return [n]

    out = Node(tag if tag in KEEP_TAGS else "div")
    if tag not in KEEP_TAGS:
        if tag in ("font", "abbr", "cite", "tt", "nobr", "time", "label"): out.tag = "span"
        elif tag in ("section", "article", "aside", "header", "footer", "main", "figure", "center"): out.tag = "div"
    out_cls = []

    if tag == "div" and "mw-collapsible" in cls:
        kids = [k for kid in node.kids for k in clean(kid, ctx)]
        summary = "Details"
        for k in kids:                                  # first bold text becomes the summary
            if isinstance(k, Node):
                b = next((x for x in walk(k) if isinstance(x, Node) and x.tag in ("b", "strong")), None)
                if b and b.text().strip(): summary = b.text().strip(); break
        d = Node("details"); s = Node("summary"); s.add(summary); d.add(s); [d.add(k) for k in kids]
        ctx.stats["collapsibles"] += 1
        return [d]

    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        hl = next((k for k in node.kids if isinstance(k, Node) and "mw-headline" in k.attrs.get("class", "").split()), None)
        if hl and hl.attrs.get("id"): out.attrs["id"] = hl.attrs["id"]
    if tag == "table":
        ctx.stats["tables"] += 1
    if tag in ("td", "th"):
        c = bg_class(style) or bg_class("background:" + a["bgcolor"] if a.get("bgcolor") else "")
        if c: out_cls.append(c)
        if re.search(r"text-align\s*:\s*center", style) or a.get("align") == "center": out_cls.append("cell-center")
        for k in ("colspan", "rowspan"):
            if a.get(k): out.attrs[k] = a[k]
    if tag == "tr":
        c = bg_class(style)
        if c: out_cls.append(c)          # row shading is applied to the cells below
        out.attrs["_rowclass"] = c or ""
    if tag == "img":
        out.attrs["alt"] = a.get("alt", ""); out.attrs["src"] = a.get("src", ""); out.attrs["loading"] = "lazy"
    if tag == "center": out_cls.append("cell-center")
    if a.get("id") and tag != "img" and "id" not in out.attrs and not a["id"].startswith(("mw-", "toc")): out.attrs["id"] = a["id"]
    if out_cls: out.attrs["class"] = " ".join(dict.fromkeys(out_cls))

    for kid in node.kids:
        for k in clean(kid, ctx): out.add(k)
    if tag == "tr":                      # push row shading down into cells that have none
        rc = out.attrs.pop("_rowclass", "")
        out.attrs.pop("class", None)
        if rc:
            for c in out.kids:
                if isinstance(c, Node) and c.tag in ("td", "th") and not any(x.startswith("cell-") and x != "cell-center" for x in c.attrs.get("class", "").split()):
                    c.attrs["class"] = (c.attrs.get("class", "") + " " + rc).strip()
    return [out]


def walk(n):
    yield n
    if isinstance(n, Node):
        for k in n.kids: yield from walk(k)


def promote_yes_no(n):
    """Cells whose entire text is Yes / No get the cell-yes / cell-no look."""
    for x in walk(n):
        if isinstance(x, Node) and x.tag in ("td", "th"):
            t = x.text().strip().lower()
            if t in ("yes", "no"):
                cs = [c for c in x.attrs.get("class", "").split() if c not in ("cell-good", "cell-bad", "cell-head")]
                x.attrs["class"] = " ".join(dict.fromkeys(cs + ["cell-" + t]))


OPS = {"*": "×", "/": "÷", "+": "+", "-": "−"}


def split_formula(kids):
    """Split inline children at top-level (outside parentheses) ` = ` and ` * / + - ` operators.
    Returns (name_nodes, [(term_nodes, op_after), ...]) or None if this doesn't look like `name = a op b op c`."""
    name, terms, cur, depth = None, [], [], 0
    def flush(op):
        nonlocal cur
        cur = [c for c in cur if not (isinstance(c, str) and not c.strip())]
        if cur and isinstance(cur[0], str): cur[0] = cur[0].lstrip()
        if cur and isinstance(cur[-1], str): cur[-1] = cur[-1].rstrip()
        piece, cur = cur, []
        return piece
    for k in kids:
        if not isinstance(k, str): cur.append(k); continue
        buf = ""
        for i, c in enumerate(k):
            spaced = (i == 0 or k[i - 1] == " ") and (i == len(k) - 1 or k[i + 1] == " ")   # string edges count as spaces (text next to a tag)
            if c == "(": depth += 1
            elif c == ")": depth -= 1
            if depth == 0 and spaced and c == "=" and name is None:
                cur.append(buf); buf = ""; name = flush(None); continue
            if depth == 0 and spaced and c in OPS and name is not None:
                cur.append(buf); buf = ""; terms.append([flush(None), OPS[c]]); continue
            buf += c
        cur.append(buf)
    last = flush(None)
    terms.append([last, ""])
    if name is None or len(terms) < 2 or not name or any(not t for t, _ in terms): return None
    return name, terms


def formulaize(root):
    """Single-line `name = a * b * c` <pre> blocks -> <div class="formula"> with wrapping term chips."""
    n = 0
    for parent in list(walk(root)):
        if not isinstance(parent, Node): continue
        for i, k in enumerate(parent.kids):
            if not (isinstance(k, Node) and k.tag == "pre"): continue
            text = k.text().strip()
            if "\n" in text or len(text) < 40: continue
            kids = list(k.kids)
            # a leading <b>Name =</b> is the common form: unwrap it so "=" can be found as text
            if kids and isinstance(kids[0], Node) and kids[0].tag in ("b", "strong"): kids[0:1] = list(kids[0].kids)
            r = split_formula(kids)
            if not r: continue
            name, terms = r
            f = Node("div", [("class", "formula")]); f.parent = parent
            nm = Node("span", [("class", "formula__name")]); [nm.add(x) for x in name]; f.add(nm)
            f.add(Node("span", [("class", "formula__equals")])); f.kids[-1].add("=")
            prev_op = ""
            for term, op in terms:                        # each step = the operator that PRECEDES a term + the term, so wraps never orphan an operator
                step = Node("span", [("class", "formula__step")])
                if prev_op:
                    o = Node("span", [("class", "formula__op")]); o.add(prev_op); step.add(o)
                t = Node("span", [("class", "formula__term")]); [t.add(x) for x in term]; step.add(t)
                f.add(step); prev_op = op
            parent.kids[i] = f; n += 1
    return n


def is_data_table(t):
    """Layout/navigation tables have few numeric cells; data tables have many."""
    return sum(1 for x in walk(t) if isinstance(x, Node) and x.tag in ("td", "th") and re.search(r"\d", x.text())) >= 4


def wrap_tables(n):
    if not isinstance(n, Node): return
    for i, k in enumerate(n.kids):
        if isinstance(k, Node) and k.tag == "table":
            w = Node("div", [("class", "table-scroll")] + ([] if is_data_table(k) else [("data-updated", "none")])); w.parent = n; k.parent = w; w.kids = [k]; n.kids[i] = w
        else: wrap_tables(k)


# ---------- serialise ----------
BLOCK = {"p", "div", "ul", "ol", "li", "dl", "dt", "dd", "table", "thead", "tbody", "tr", "h1", "h2", "h3",
         "h4", "h5", "h6", "pre", "details", "summary", "hr", "blockquote", "caption"}
STRUCTURAL = {"root", "table", "thead", "tbody", "tr", "ul", "ol", "dl", "details"}

def ser(n, depth=0):
    if isinstance(n, str): return html.escape(n, quote=False)
    if n.tag in ("td", "th"):
        n.kids = [k for k in n.kids if not (isinstance(k, str) and not k.strip())] if all(isinstance(k, Node) and k.tag in BLOCK for k in n.kids) else n.kids
    attrs = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in n.attrs.items() if v != "" or k == "alt")
    if n.tag in VOID: return f"<{n.tag}{attrs}>"
    kids = [k for k in n.kids if not (isinstance(k, str) and not k.strip() and n.tag in STRUCTURAL)]
    inner = "".join(ser(k, depth + 1) for k in kids)
    if n.tag in BLOCK: return f"\n<{n.tag}{attrs}>{inner.strip() if n.tag in ('td','th','li','p','summary','caption') else inner}</{n.tag}>"
    if n.tag in ("td", "th"): inner = inner.strip()
    return f"<{n.tag}{attrs}>{inner}</{n.tag}>"


def fix_headings(root, title):
    hs = [x for x in walk(root) if isinstance(x, Node) and x.tag in ("h1", "h2", "h3", "h4", "h5", "h6")]
    first = next((h for h in hs if h.parent is root), None)
    if first and first.text().strip().lower() == title.lower():      # duplicate of the page title
        root.kids.remove(first); hs.remove(first)
    if any(h.tag == "h1" for h in hs):                                # page title is the h1, so body starts at h2
        for h in hs: h.tag = "h" + str(min(int(h.tag[1]) + 1, 6))


def prune(n):
    """Remove empty <p>, collapse runs of <br>."""
    if not isinstance(n, Node): return
    for k in n.kids: prune(k)
    n.kids = [k for k in n.kids if not (isinstance(k, Node) and k.tag == "p" and not k.text().strip() and not any(isinstance(x, Node) and x.tag in ("img", "table") for x in walk(k)))]


def main():
    raw = json.load(open(ROOT / "data/raw/pages.json"))
    slugs, redirects = {}, {}
    for p in raw:
        if p["ns"] not in PREFIX: continue
        if p["redirect"]:
            m = re.match(r"\s*#redirect\s*:?\s*\[\[([^\]|]+)", p["text"], re.I)
            if m: redirects[p["title"]] = m.group(1).strip()
        elif p["text"].strip() and not skipped(p["title"], p["ns"]):
            slugs[p["title"]] = slugify(p["title"], p["ns"])
    slugs.update(SLUG_OVERRIDES)
    ctx = Ctx(slugs, redirects)

    out = ROOT / "content"; out.mkdir(exist_ok=True)
    for old in out.glob("*.html"):   # keep _nav.html and any page marked "origin: scriptorium" (hand-written, not from the old wiki)
        if not old.name.startswith("_") and "origin: scriptorium" not in old.read_text()[:300]: old.unlink()
    files = sorted((ROOT / "data/rendered").glob("*.json"))
    for f in files:
        d = json.load(open(f))
        if skipped(d["title"], d["ns"]): continue
        tree = parse(d["html"])
        root = Node("root"); [root.add(k) for kid in tree.kids for k in clean(kid, ctx)]
        promote_yes_no(root); ctx.stats['formulas'] += formulaize(root); prune(root); wrap_tables(root); fix_headings(root, html.unescape(re.sub(r'<[^>]+>', '', d['title'])))
        body = re.sub(r"\n{3,}", "\n\n", "".join(ser(k) for k in root.kids)).strip()
        cats = [c.replace("_", " ") for c in d["categories"]]
        credits = list(dict.fromkeys(d.get("contributors", [])))
        title = html.unescape(re.sub(r"<[^>]+>", "", d["title"]))
        if d["ns"] == 4: title = title.split(":", 1)[-1]
        slug = slugs.get(d["title"]) or slugify(d["title"], d["ns"])
        updated = (d.get("last_edit") or "")[:10]   # last edit on the ORIGINAL wiki; contributors bump it when they change numbers
        head = f"<!--\ntitle: {title}\ncategory: {', '.join(cats)}\nupdated: {updated}\ncredits: {', '.join(credits)}\n-->\n"
        if (out / f"{slug}.html").exists(): continue   # a hand-written page owns this slug
        (out / f"{slug}.html").write_text(head + body + "\n", encoding="utf-8")

    print(f"converted {len(list(out.glob('*.html')))} pages;", dict(ctx.stats))
    print(f"{len(ctx.missing)} link targets not in the mirror (text kept, link dropped). Top:", ctx.missing.most_common(15))
    (ROOT / "data/missing-link-targets.json").write_text(json.dumps(ctx.missing.most_common(), indent=1))


if __name__ == "__main__":
    main()
