# Contributing to Scriptorium

You do not need to install anything. Content is HTML fragments, and the GitHub web editor is enough.

## Fix or improve a page
1. Open the file in [`content/`](content/) (e.g. `content/magic-formulas.html`) and click the ✏️ pencil.
2. Edit the text. Keep the comment block at the top of the file; it holds the page title and categories.
3. Commit to a new branch and open a pull request. The build runs automatically and fails if you broke a link.

## Add a page
Create `content/my-new-page.html`:

```html
<!--
title: My New Page
category: Guides
updated: 2026-09-25
-->
<p>Text goes here.</p>
<h2 id="First_Section">First Section</h2>
<p>Link to another page: <a href="game-rules.html">Game Rules</a>.</p>
```

The file name (without `.html`) is the page's URL. Then add a link to it from a related page or from
`content/_nav.html` so people can find it.

## Rules of the road
- **Content is CC BY-NC 3.0.** Don't paste in anything you can't license that way, and no ads or commercial links.
- **No JavaScript, no inline `style=` in content.** Use the classes in [docs/ANATOMY.md](docs/ANATOMY.md).
- **Numbers change every Age.** When a formula or value changes, say which Age it applies to, and **bump `updated:` in the page's header comment**. That date is shown under every table as "Numbers last updated …" (see [docs/ANATOMY.md](docs/ANATOMY.md)).
- Do not publish information about cheating or exploits. (The original wiki had the same rule.)

## Preview locally (optional)
```
python3 build.py --check      # needs only Python 3.8+
python3 -m http.server -d dist
```
