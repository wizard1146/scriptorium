#!/usr/bin/env python3
"""Export every page (wikitext + contributors) from the Utopia Wiki via the MediaWiki API.
Polite: honest UA, 1 req/sec, batches of 50. Source cert is expired, so we shell out to curl -k (read-only, public data; Python's TLS stack is rejected by the old server)."""
import json, subprocess, time, urllib.parse, pathlib, sys

BASE = "https://wiki.utopia-game.com/api.php"
UA = "ScriptoriumArchiver/0.1 (fan-wiki preservation; contact william@drwilliamyu.com)"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

def api(**p):
    p["format"] = "json"
    url = BASE + "?" + urllib.parse.urlencode(p)
    for attempt in range(5):
        time.sleep(1 + attempt * 2)
        r = subprocess.run(["curl", "-skL", "-m", "60", "-A", UA, url], capture_output=True)
        try:
            return json.loads(r.stdout)
        except ValueError:
            print(f"retry {attempt+1}: {r.stdout[:80]!r}", file=sys.stderr)
    raise RuntimeError("giving up on " + url)

def all_titles():
    ns_info = api(action="query", meta="siteinfo", siprop="namespaces")["query"]["namespaces"]
    titles = []
    for ns in sorted(int(n) for n in ns_info if int(n) >= 0):
        cont = {}
        while True:
            d = api(action="query", list="allpages", apnamespace=ns, aplimit="max", **cont)
            titles += [(ns, p["title"]) for p in d["query"]["allpages"]]
            if "continue" not in d: break
            cont = d["continue"]
        print(f"ns {ns}: running total {len(titles)}", file=sys.stderr)
    return titles

def main():
    titles = all_titles()
    pages = {}
    for i in range(0, len(titles), 50):
        chunk = [t for _, t in titles[i:i+50]]
        d = api(action="query", prop="revisions|info", rvprop="content|timestamp|user", rvslots="main",
                titles="|".join(chunk), inprop="protection")
        for p in d["query"]["pages"].values():
            rev = (p.get("revisions") or [{}])[0]
            pages[p["title"]] = {"ns": p["ns"], "title": p["title"], "pageid": p.get("pageid"),
                "redirect": "redirect" in p, "touched": p.get("touched"),
                "last_editor": rev.get("user"), "last_edit": rev.get("timestamp"),
                "text": (rev.get("slots", {}).get("main", {}) or {}).get("*", rev.get("*", ""))}
        print(f"content {min(i+50, len(titles))}/{len(titles)}", file=sys.stderr)
    # contributors (for CC-BY attribution)
    for i in range(0, len(titles), 50):
        chunk = [t for _, t in titles[i:i+50]]
        cont = {}
        while True:
            d = api(action="query", prop="contributors", pclimit="max", titles="|".join(chunk), **cont)
            for p in d["query"]["pages"].values():
                pages[p["title"]].setdefault("contributors", []).extend(u["name"] for u in p.get("contributors", []))
            if "continue" not in d: break
            cont = d["continue"]
        print(f"contributors {min(i+50, len(titles))}/{len(titles)}", file=sys.stderr)
    (OUT / "pages.json").write_text(json.dumps(sorted(pages.values(), key=lambda p: (p["ns"], p["title"])), indent=1, ensure_ascii=False))
    print(f"done: {len(pages)} pages", file=sys.stderr)

if __name__ == "__main__":
    main()
