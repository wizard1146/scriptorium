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
ids = {re.sub(r"\s+", " ", i.replace("_", " ").replace(".27", "'")).lower(): i for i in re.findall(r'id="([^"]+)"', mystics)}
def spell_link(name):
    key = name.replace("’", "'").strip().lower()
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

def ul(items): return "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>" if items else ""
def plain_unit(u): return f"{u[0]} / {u[1]} ({u[3]}nw)"
rows1, rows2 = [], []
for r in RACES:
    d = data[r]; e = d["elite"]
    rows1.append(f'<tr><td><b>{r}</b></td>' + "".join(f'<td class="cell-center">{c}</td>' for c in
        [plain_unit(d["sol"]), plain_unit(d["off"]), plain_unit(d["def"]), f"{e[0]} / {e[1]} ({e[2]}gc, {e[3]}nw)", e[2], e[3]]) + "</tr>")
    rows2.append(f'<tr><td><b>{r}</b></td><td class="cell-good">{ul(d["bonuses"])}</td><td class="cell-bad">{ul(d["penalties"])}</td>'
                 f'<td><b>{html.escape(d["ua"][0])}</b><br>{html.escape(d["ua"][1])}</td><td>{", ".join(spell_link(s) for s in d["spells"])}</td></tr>')
def table(headers, rows):
    return ('<div class="table-scroll">\n<table class="table--mono">\n<tr>' + "".join(f"<th>{h}</th>" for h in headers) + "</tr>\n"
            + "\n".join(rows) + "\n</table>\n</div>")

page = f'''<!--
title: Current Changes: Age {age}
origin: scriptorium
updated: {updated}
-->
<p>Race stats for the current Age, <b>Age {age}</b>, taken from <b>AGE {age} FINAL CHANGES.pdf</b>, posted in the game's
<a href="https://utopia-game.com/discord">Discord</a>. That file is the source of truth for everything else that changed this Age.</p>

<h2 id="Units_and_Costs">Units and costs</h2>

{table(["Race", "Soldier", "Off. Specialist", "Def. Specialist", "Elite (Off/Def)", "Cost (gc)", "Networth"], rows1)}

<h2 id="Bonuses_Penalties_and_Abilities">Bonuses, penalties and abilities</h2>

{table(["Race", "Bonuses", "Penalties", "Unique Ability", "Spellbook"], rows2)}
'''
(ROOT / "content/current-changes.html").write_text(page)
print("wrote content/current-changes.html:", ", ".join(RACES))
