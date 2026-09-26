#!/usr/bin/env python3
"""Build content/current-changes.html from a "FINAL CHANGES" PDF (text extracted with `pdftotext -layout`).
Usage: python3 tools/age_changes.py "AGE 116 FINAL CHANGES.pdf" 116 2026-07-21
The PDF itself is never committed (see .gitignore); only the derived tables are published.
Tables: (1) units and costs, (2) bonuses / penalties / unique ability / spellbook."""
import html, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
pdf, age, updated = sys.argv[1], sys.argv[2], sys.argv[3]
text = subprocess.check_output(["pdftotext", "-layout", pdf, "-"], text=True).replace("\u200b", "").replace("\f", "")
# \u200b: zero-width spaces. \f: page breaks, which would otherwise look like blank lines and cut a list short mid-page
lines = [l.rstrip() for l in text.splitlines()]

RACES = ["Avian", "Dark Elf", "Dryad", "Dwarf", "Elf", "Faery", "Halfling", "Human", "Orc", "Undead"]
start = next(i for i, l in enumerate(lines) if l.strip() == "Races")
end = next(i for i, l in enumerate(lines) if l.strip() == "Personalities" and i > start)
sect = lines[start + 1:end]
idx = {r: next(i for i, l in enumerate(sect) if l.strip() == r) for r in RACES}
order = sorted(RACES, key=idx.get)
blocks = {r: sect[idx[r] + 1:(idx[order[order.index(r) + 1]] if order.index(r) + 1 < len(order) else len(sect))] for r in RACES}

def take(block, label, stops):
    """Lines after a `label` line until a blank line or a line starting with one of `stops`."""
    for i, l in enumerate(block):
        if l.strip().lower().startswith(label.lower()):
            first = l.strip()[len(label):].lstrip(": -").strip()
            got = [first] if first else []
            for m in block[i + 1:]:
                if not m.strip() or any(m.strip().startswith(s) for s in stops): break
                got.append(m.strip())
            return got
    return []

UNIT = re.compile(r"(\d+)\s*/\s*(\d+)[\s,]*(?:(\d+)\s*gc[\s,]*)?([\d.]+)\s*nw")
def unit(block, name):
    for l in block:
        l = re.sub(r"^[\s●○•]+", "", l)                      # some races list units as bullets
        if l.startswith(name):
            m = UNIT.search(l)
            if m: return m.groups()
    raise SystemExit(f"could not read '{name}' in block: {block[:3]}")

# unique-ability names (the PDF runs the name into the text inconsistently, so they are listed here)
UA_NAMES = {"Avian": "Dive Bomb", "Dark Elf": "Mystic Enthusiasts", "Dryad": "Overgrowth", "Dwarf": "Architect's Revenge", "Elf": "Arcane Mastery",
            "Faery": "Leyline Interference", "Halfling": "Silent Assault", "Human": "Civil Administration", "Orc": "Blood Spoils", "Undead": "Death March"}
mystics = (ROOT / "content/mystics.html").read_text()
_plain = lambda x: re.sub(r"['’‘]", "", re.sub(r"\s+", " ", x)).strip().lower()
ids = {_plain(i.replace("_", " ").replace(".27", "'")): i for i in re.findall(r'id="([^"]+)"', mystics)}
def spell_link(name):
    key = _plain(name)
    return f'<a href="mystics.html#{ids[key]}">{html.escape(name.strip())}</a>' if key in ids else html.escape(name.strip())

data = {}
for r in RACES:
    b = blocks[r]
    ua = " ".join(take(b, "Unique Passive", ("Spells", "Penalties", "Units")))
    ua = re.sub(r"^" + re.escape(UA_NAMES[r]) + r"\s*[:\-–]?\s*", "", ua)
    spells = " ".join(take(b, "Spells", ("Penalties", "Units")))
    data[r] = {
        "bonuses": take(b, "Bonuses", ("War Doctrine", "Unique Passive", "Spells")),
        "penalties": take(b, "Penalties", ("Units",)),
        "ua": (UA_NAMES[r], ua), "spells": [s for s in re.split(r",\s*", spells) if s.strip()],
        "sol": unit(b, "Soldier"), "off": unit(b, "Offensive Specialist"), "def": unit(b, "Defensive Specialist"), "elite": unit(b, "Elite Unit"),
    }

FIGURE = re.compile(r"(?<![\w.])([+\-\u2212]?\d+(?:\.\d+)?%?)")
def numbers_mono(text):
    """Escape a line and wrap each figure (with its sign and %) in <span class="num">, which CSS sets in the monospace font."""
    text = re.sub(r"(\d)\s+%", r"\1%", text)              # "+25 %"  -> "+25%"   (typo in the PDF)
    text = re.sub(r",(?=[A-Za-z])", ", ", text)              # "Greed,Incite" -> "Greed, Incite"
    return FIGURE.sub(r'<span class="num">\1</span>', html.escape(text, quote=False))

def ul(items):
    """Bonuses / penalties: no bullets, a small gap between items so a wrapped line doesn't blur into the next; figures in mono."""
    return '<ul class="list-plain list-spaced">' + "".join(f"<li>{numbers_mono(i)}</li>" for i in items) + "</ul>" if items else ""

def fmt_column(values):
    """Give every value in a column the same number of decimals (the most any of them has), so digits line up: 7 and 7.5 -> 7.0 and 7.5."""
    dp = max((len(v.split(".")[1]) if "." in v else 0) for v in values)
    return [f"{float(v):.{dp}f}" for v in values]

# NW precision is normalised per unit column (Soldier NW: 0.75 everywhere; Off. Specialist NW: 1 decimal everywhere; ...)
nw = {k: dict(zip(RACES, fmt_column([data[r][k][3] for r in RACES]))) for k in ("sol", "off", "def", "elite")}

# ---- personalities: parsed from the PDF's "Personalities" section, one block per "The <Name>" line ----
def parse_personalities():
    start = next(i for i, l in enumerate(lines) if l.strip() == "Personalities")
    block_lines = [l.strip() for l in lines[start + 1:]]
    heads = [i for i, l in enumerate(block_lines) if re.fullmatch(r"The [A-Z][A-Za-z ]+", l)]
    people = {}
    for n, i in enumerate(heads):
        name = block_lines[i][4:]
        chunk = [l for l in block_lines[i + 1:(heads[n + 1] if n + 1 < len(heads) else len(block_lines))] if l]
        items = []                                        # [kind, text-or-lines]
        for l in chunk:
            prev = items[-1] if items else None
            if l.startswith("Access to"): items.append(["spells", l[len("Access to"):].strip()])
            elif l.startswith("Starts with"): items.append(["start", l[len("Starts with"):].strip()])
            elif l.startswith("Unique Passive"): items.append(["ua", [l[len("Unique Passive"):].lstrip(" :–-").strip()]])
            elif prev and prev[0] == "ua": prev[1].append(l)                                   # everything after Unique Passive belongs to it
            elif prev and prev[0] == "spells" and prev[1].endswith(","): prev[1] += " " + l   # wrapped spell list
            elif prev and prev[0] == "start" and re.fullmatch(r"[A-Z][a-z]+", l): prev[1] += " " + l   # "...+200 Building" / "Credits"
            elif prev and prev[0] == "bonus" and l[0].islower(): prev[1] += " " + l           # wrapped bonus line
            else: items.append(["bonus", l])
        p = {"bonuses": [t for k, t in items if k == "bonus"], "start": [t for k, t in items if k == "start"], "spells": [], "ua": ("", "")}
        for k, t in items:
            if k == "spells": p["spells"] += [re.sub(r"^and\s+", "", x.strip()) for x in t.split(",") if x.strip()]
            if k == "ua":
                first = t[0]
                m = re.match(r"(.*?)(?::\s+|\.\s+| - |\s*:$|$)(.*)", first)
                name_, rest = m.group(1).strip(), m.group(2).strip()
                rest_lines = ([rest] if rest else []) + t[1:]
                text = ""
                prev_piece = ""
                for piece in rest_lines:                  # a line starting with a figure is a new list line ("15% of gold") only inside a list, not mid-sentence
                    in_list = re.match(r"\d", piece) and (prev_piece.endswith((":", ".")) or re.match(r"\d", prev_piece))
                    text += ("<br>" if text and in_list else " " if text else "") + numbers_mono(piece)
                    prev_piece = piece
                p["ua"] = (name_, text.strip())
        people[name] = p
    return people

PERSONALITIES = parse_personalities()
PLAYERS = list(PERSONALITIES)

# ---- table 1: per unit Att | Def | NW (NW muted, all numbers right-aligned); Elite adds a muted Cost ----
NUM, MUTED = "cell-num", "cell-num cell-muted"
rows1, rows2 = [], []
for r in RACES:
    d = data[r]; e = d["elite"]
    cells = [f"<td><b>{r}</b></td>"]
    for key in ("sol", "off", "def"):
        u = d[key]
        cells += [f'<td class="{NUM}">{u[0]}</td>', f'<td class="{NUM}">{u[1]}</td>', f'<td class="{MUTED}">{nw[key][r]}</td>']
    cells += [f'<td class="{NUM}">{e[0]}</td>', f'<td class="{NUM}">{e[1]}</td>', f'<td class="{MUTED}">{nw["elite"][r]}</td>', f'<td class="{MUTED}">{e[2]}</td>']
    rows1.append("<tr>" + "".join(cells) + "</tr>")
    spells = '<ul class="list-plain">' + "".join(f"<li>{spell_link(s)}</li>" for s in d["spells"]) + "</ul>"
    # data-label is the caption shown above each section when the table turns into cards on narrow screens
    rows2.append(f'<tr><td><b>{r}</b></td><td class="cell-good" data-label="Bonuses">{ul(d["bonuses"])}</td><td class="cell-bad" data-label="Penalties">{ul(d["penalties"])}</td>'
                 f'<td data-label="Unique Ability"><b class="ability">{html.escape(d["ua"][0])}</b><br>{numbers_mono(d["ua"][1])}</td><td data-label="Spellbook">{spells}</td></tr>')

def table(head_rows, rows, cls="table--mono", colgroup=""):
    return f'<div class="table-scroll">\n<table class="{cls}">\n{colgroup}' + "\n".join(head_rows) + "\n" + "\n".join(rows) + "\n</table>\n</div>"
def head(cells): return "<tr>" + "".join(cells) + "</tr>"
def subs(*names): return "".join(f'<th class="{NUM}">{n}</th>' for n in names)

# fixed column widths for the units table: Race, twelve equal figure columns, then the (wider) Cost column
UNITS_COLS = '<colgroup><col class="col-w-race"><col class="col-w-num" span="12"><col class="col-w-cost"></colgroup>\n'
head1 = [head(['<th rowspan="2">Race</th>', '<th colspan="3">Soldier</th>', '<th colspan="3">Offense Specialist</th>', '<th colspan="3">Defense Specialist</th>', '<th colspan="4">Elite</th>']),
         head([subs("Att", "Def", "NW") * 3 + subs("Att", "Def", "NW", "Cost (gc)")])]
# second table: fixed layout, so Bonuses / Penalties / Unique Ability get equal widths; Race and Spellbook are set narrow
head2 = [head(['<th class="col-sm">Race</th>', "<th>Bonuses</th>", "<th>Penalties</th>", "<th>Unique Ability</th>", '<th class="col-md">Spellbook</th>'])]

# ---- table 3: personalities (same layout as the race table: fixed even columns, cards on narrow screens) ----
rows3 = []
for name, p in PERSONALITIES.items():
    spells = ('<ul class="list-plain">' + "".join(f"<li>{spell_link(s)}</li>" for s in p["spells"]) + "</ul>") if p["spells"] else '<span class="cell-muted">None</span>'
    start = f'<div class="start-bonus">{ul(p["start"])}</div>' if p["start"] else ""
    rows3.append(f'<tr><td><b>{name}</b></td><td data-label="Bonuses">{ul(p["bonuses"])}{start}</td>'
                 f'<td data-label="Unique Ability"><b class="ability">{html.escape(p["ua"][0])}</b><br>{p["ua"][1]}</td><td data-label="Spellbook">{spells}</td></tr>')
head3 = [head(['<th class="col-sm">Personality</th>', "<th>Bonuses &amp; Starting Bonuses</th>", "<th>Unique Ability</th>", '<th class="col-md">Spellbook</th>'])]

page = f'''<!--
title: Current Changes: Age {age}
origin: scriptorium
updated: {updated}
-->
<p>Race and personality stats for Age {age}. Source: <b>AGE {age} FINAL CHANGES.pdf</b> in the game's <a href="https://utopia-game.com/discord">Discord</a>.</p>

<h2 id="Units_and_Costs">Units and costs</h2>

{table(head1, rows1, "table--mono table--sticky-first table--borderless table--units table--hover", UNITS_COLS)}

<h2 id="Race_Bonuses_Penalties_and_Abilities">Race bonuses, penalties and abilities</h2>

{table(head2, rows2, "table--mono table--fixed table--cards table--hover")}

<h2 id="Personalities">Personalities</h2>

{table(head3, rows3, "table--mono table--fixed table--cards table--hover")}
'''
(ROOT / "content/current-changes.html").write_text(page)
print("wrote content/current-changes.html:", ", ".join(RACES), "|", len(PERSONALITIES), "personalities:", ", ".join(PERSONALITIES))
# coverage check: every personality line in the PDF must appear on the page (letters and digits only, so punctuation and wrapping don't matter)
_norm = lambda t: re.sub(r"[^a-z0-9%]+", "", html.unescape(re.sub(r"<[^>]+>", " ", t)).lower())
_page = _norm(page)
_missing = []
for l in (x.strip() for x in lines[next(i for i, l in enumerate(lines) if l.strip() == "Personalities") + 1:]):
    if not l or re.fullmatch(r"The [A-Z][A-Za-z ]+", l): continue
    if l.startswith("Access to"):                                      # spells are listed one per line on the page: check each
        _missing += [x for x in re.split(r",|\band\b", l[len("Access to"):]) if x.strip() and _norm(x) not in _page]
    elif _norm(re.sub(r"^(Starts with|Unique Passive)", "", l)) not in _page:
        _missing.append(l)
if _missing: print("WARNING: personality lines from the PDF that are NOT on the page:", *_missing, sep="\n  ")
else: print("coverage: every personality line in the PDF is on the page")

# the sidebar label ("Current Changes: Age {{age}}") reads the current Age from content/_values.json
import json
vf = ROOT / "content" / "_values.json"
vals = json.loads(vf.read_text(encoding="utf-8"))
if vals.get("age") != int(age):
    vals["age"] = int(age)
    vf.write_text(json.dumps(vals, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("updated content/_values.json: age =", age)
