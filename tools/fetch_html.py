#!/usr/bin/env python3
"""Fetch MediaWiki-rendered HTML (templates expanded) for every real page. Resumable; 1 req/sec."""
import json, subprocess, time, urllib.parse, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://wiki.utopia-game.com/api.php"
UA = "ScriptoriumArchiver/0.1 (fan-wiki preservation; contact william@drwilliamyu.com)"
KEEP_NS = {0, 4, 12}  # articles, project pages, help

def slug(title):
    import re
    s = title.split(":", 1)[-1] if ":" in title and title.split(":")[0] in ("Help", "The Utopian Encyclopedia") else title
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "page"

def main():
    pages = json.load(open(ROOT / "data/raw/pages.json"))
    todo = [p for p in pages if p["ns"] in KEEP_NS and not p["redirect"] and p["text"].strip()]
    out = ROOT / "data/rendered"
    for i, p in enumerate(todo, 1):
        f = out / (f'{p["ns"]}_{slug(p["title"])}.json')
        if f.exists(): continue
        url = BASE + "?" + urllib.parse.urlencode({"action": "parse", "page": p["title"], "prop": "text|categories|displaytitle",
              "disableeditsection": 1, "disabletoc": 1, "format": "json"})
        for attempt in range(5):
            time.sleep(1 + attempt * 2)
            r = subprocess.run(["curl", "-skL", "-m", "60", "-A", UA, url], capture_output=True)
            try:
                d = json.loads(r.stdout)["parse"]; break
            except (ValueError, KeyError):
                print("retry", p["title"], attempt + 1, file=sys.stderr)
        else:
            print("FAILED", p["title"], file=sys.stderr); continue
        f.write_text(json.dumps({"title": p["title"], "ns": p["ns"], "html": d["text"]["*"],
            "categories": [c["*"] for c in d.get("categories", [])], "contributors": p.get("contributors", []),
            "last_edit": p["last_edit"]}, ensure_ascii=False))
        print(f"{i}/{len(todo)} {p['title']}", file=sys.stderr)

if __name__ == "__main__":
    main()
