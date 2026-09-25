// DEV ONLY. Injected by serve.py into pages it serves; never part of the built site (dist/).
// A floating "Aa" panel to try heading/body fonts and text size live. Choices persist in localStorage.
(() => {
  const SYS = (label, stack) => ({ label, stack });
  const GF = (name, weights) => ({ label: name + '  (Google)', stack: `"${name}", serif`, gf: weights ? `${name.replace(/ /g, '+')}:wght@${weights}` : name.replace(/ /g, '+') });
  const GFS = (name, weights) => ({ ...GF(name, weights), stack: `"${name}", sans-serif` });

  const HEADING = [
    SYS('IM Fell English, Charter  (current)', '"IM Fell English", Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif'),
    SYS('Georgia  (previous default)', 'Georgia, "Times New Roman", serif'),
    SYS('Palatino', '"Palatino Linotype", Palatino, "Book Antiqua", serif'),
    SYS('Iowan Old Style', '"Iowan Old Style", "Palatino Linotype", serif'),
    SYS('Baskerville', 'Baskerville, "Baskerville Old Face", serif'),
    SYS('Hoefler Text', '"Hoefler Text", "Baskerville Old Face", serif'),
    SYS('Didot', 'Didot, "Bodoni MT", serif'),
    SYS('Charter', 'Charter, "Bitstream Charter", "Sitka Text", Cambria, serif'),
    GF('Cinzel', '400;700'), GF('Cormorant Garamond', '400;700'), GF('EB Garamond', '400;700'),
    GF('Playfair Display', '400;700'), GF('Lora', '400;700'), GF('Merriweather', '400;700'),
    GF('UnifrakturCook', '700'), GF('Uncial Antiqua'), GF('Almendra', '400;700'), GF('MedievalSharp'),
  ];
  const BODY = [
    SYS('Lora, Iowan Old Style  (current)', '"Lora", "Iowan Old Style", "Palatino Linotype", ui-serif, Georgia, serif'),
    SYS('System UI  (previous default)', 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'),
    SYS('Charter', 'Charter, "Bitstream Charter", "Sitka Text", Cambria, serif'),
    SYS('Georgia', 'Georgia, "Times New Roman", serif'),
    SYS('Iowan Old Style', '"Iowan Old Style", "Palatino Linotype", serif'),
    SYS('Avenir Next', '"Avenir Next", Avenir, "Segoe UI", sans-serif'),
    SYS('Helvetica Neue', '"Helvetica Neue", Helvetica, Arial, sans-serif'),
    SYS('Verdana', 'Verdana, Geneva, sans-serif'),
    GFS('Inter', '400;600;700'), GFS('Source Sans 3', '400;600;700'), GFS('Atkinson Hyperlegible', '400;700'),
    GF('Source Serif 4', '400;600;700'), GF('Crimson Pro', '400;600;700'),
    GF('EB Garamond', '400;600;700'), GF('Libre Baskerville', '400;700'), GF('Merriweather', '400;700'),
  ];

  const KEY = 'scriptorium-dev-fonts';
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch {} };
  const state = { h: 0, b: 0, scale: 1, open: false, ...load() };
  const root = document.documentElement;

  const loaded = new Set();
  const ensure = f => {
    if (!f.gf || loaded.has(f.gf)) return;
    loaded.add(f.gf);
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = `https://fonts.googleapis.com/css2?family=${f.gf}&display=swap`;
    document.head.appendChild(l);
  };
  const apply = () => {
    const h = HEADING[state.h] || HEADING[0], b = BODY[state.b] || BODY[0];
    ensure(h); ensure(b);
    root.style.setProperty('--font-heading', h.stack);
    root.style.setProperty('--font-body', b.stack);
    root.style.setProperty('--font-scale', state.scale);
    save(state);
    out.value = `:root {\n  --font-heading: ${h.stack};\n  --font-body: ${b.stack};\n  --font-scale: ${state.scale};\n}`;
    const note = [h, b].filter(f => f.gf).map(f => f.label.replace('  (Google)', '')).join(', ');
    hint.textContent = note ? `Google font${note.includes(',') ? 's' : ''}: ${note}. Tell Claude to vendor it into the repo.` : 'System fonts only: nothing to download.';
  };

  const panel = document.createElement('div');
  panel.id = 'dev-font-panel';
  panel.innerHTML = `
    <style>
      #dev-font-panel { position: fixed; right: 14px; bottom: 14px; z-index: 99999; font: 13px/1.4 system-ui, sans-serif; color: #222; }
      #dev-font-panel button.toggle { width: 44px; height: 44px; border-radius: 50%; border: 0; background: #6b2d5c; color: #fff; font: 700 17px Georgia, serif; cursor: pointer; box-shadow: 0 4px 14px #0005; }
      #dev-font-panel .box { display: none; width: 290px; padding: 12px; margin-bottom: 10px; background: #fff; border: 1px solid #ccc; border-radius: 8px; box-shadow: 0 8px 28px #0004; }
      #dev-font-panel.open .box { display: block; }
      #dev-font-panel label { display: block; margin: 8px 0 2px; font-weight: 600; }
      #dev-font-panel select, #dev-font-panel textarea, #dev-font-panel input[type=range] { width: 100%; font: inherit; }
      #dev-font-panel textarea { height: 86px; font: 11px/1.3 ui-monospace, monospace; resize: none; }
      #dev-font-panel .row { display: flex; gap: 6px; margin-top: 8px; }
      #dev-font-panel .row button { flex: 1; padding: 5px; cursor: pointer; }
      #dev-font-panel small { display: block; margin-top: 6px; color: #666; }
      #dev-font-panel .title { font-weight: 700; }
    </style>
    <div class="box">
      <div class="title">Font tester (dev only)</div>
      <label for="dev-h">Headings: brand, page title, h2</label><select id="dev-h"></select>
      <label for="dev-b">Body text</label><select id="dev-b"></select>
      <label for="dev-s">Text size: <span id="dev-sv"></span></label><input id="dev-s" type="range" min="0.85" max="1.3" step="0.05">
      <div class="row"><button type="button" id="dev-reset">Reset</button><button type="button" id="dev-copy">Copy CSS</button></div>
      <textarea id="dev-out" readonly aria-label="CSS for the chosen fonts"></textarea>
      <small id="dev-hint"></small>
    </div>
    <button class="toggle" type="button" aria-label="Font tester">Aa</button>`;
  document.body.appendChild(panel);

  const $ = id => panel.querySelector('#' + id);
  const out = $('dev-out'), hint = $('dev-hint');
  const fill = (sel, list) => list.forEach((f, i) => sel.add(new Option(f.label, i)));
  fill($('dev-h'), HEADING); fill($('dev-b'), BODY);
  const sync = () => { $('dev-h').value = state.h; $('dev-b').value = state.b; $('dev-s').value = state.scale; $('dev-sv').textContent = Math.round(state.scale * 100) + '%'; panel.classList.toggle('open', state.open); };

  $('dev-h').onchange = e => { state.h = +e.target.value; apply(); };
  $('dev-b').onchange = e => { state.b = +e.target.value; apply(); };
  $('dev-s').oninput = e => { state.scale = +e.target.value; $('dev-sv').textContent = Math.round(state.scale * 100) + '%'; apply(); };
  $('dev-reset').onclick = () => { state.h = 0; state.b = 0; state.scale = 1; sync(); apply(); };
  $('dev-copy').onclick = () => { out.select(); navigator.clipboard?.writeText(out.value).catch(() => document.execCommand('copy')); };
  panel.querySelector('.toggle').onclick = () => { state.open = !state.open; sync(); save(state); };

  sync(); apply();
})();
