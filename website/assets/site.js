/* Shared site chrome (header and footer on every page) and the Python loader.
 *
 * The simulation, the agent and every experiment are the Python package in /escape_room.
 * PY.load() starts Pyodide (Python compiled to WebAssembly), copies the package into its
 * file system and returns escape_room.web, whose functions return JSON strings. */
(function () {
  'use strict';
  const REPO = 'https://github.com/RohanRaoCs/unit7-escape-protocol';
  const PAGES = [
    ['index.html', 'Home', 'home'],
    ['simulator.html', 'Simulator', 'simulator'],
    ['benchmark.html', 'Benchmark', 'benchmark'],
    ['learning.html', 'Learning lab', 'learning'],
    ['how-it-works.html', 'How it works', 'how'],
    ['testing.html', 'Testing guide', 'testing'],
  ];
  const current = document.body.dataset.page;
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const header = document.createElement('header');
  header.className = 'site-header';
  header.innerHTML =
    '<a class="site-brand" href="index.html"><span class="mark" aria-hidden="true"></span>UNIT-7 Escape Protocol</a>' +
    '<button class="btn menu-btn" aria-expanded="false" aria-controls="siteNav">Menu</button>' +
    '<nav class="site-nav" id="siteNav" aria-label="Pages">' +
    PAGES.map(([href, label, id]) => `<a href="${href}"${id === current ? ' aria-current="page"' : ''}>${label}</a>`).join('') +
    '</nav>' +
    `<a class="gh" href="${REPO}" target="_blank" rel="noopener">Source on GitHub</a>`;
  document.body.prepend(header);
  const btn = header.querySelector('.menu-btn'), nav = header.querySelector('.site-nav');
  btn.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
  });

  const footer = document.createElement('footer');
  footer.className = 'site-footer';
  footer.innerHTML =
    '<div class="inner">' +
    '<span>CSCI218 Group Project, Group 2. Search, constraint satisfaction, a behaviour tree, fuzzy logic, a state machine and Q-learning, written in Python.</span>' +
    `<span><a href="testing.html">Testing guide</a> · <a href="${REPO}" target="_blank" rel="noopener">GitHub</a> · <a href="${REPO}/blob/main/docs/REPORT.md" target="_blank" rel="noopener">Report</a></span>` +
    '</div>';
  document.body.appendChild(footer);

  /* ---------------- Python ---------------- */
  const FILES = ['__init__', 'world', 'search', 'csp', 'bt', 'fuzzy', 'drone', 'agent', 'sim', 'qlearn', 'evaluation', 'checks', 'view', 'web'];
  let loading = null;
  function load() {
    if (loading) return loading;
    loading = (async () => {
      if (typeof loadPyodide !== 'function') throw new Error('the Pyodide script did not load (check your connection)');
      const py = await loadPyodide();
      py.FS.mkdirTree('/home/pyodide/escape_room');
      await Promise.all(FILES.map(async (f) => {
        const res = await fetch(`../escape_room/${f}.py`, { cache: 'no-cache' });
        if (!res.ok) throw new Error(`could not load escape_room/${f}.py`);
        py.FS.writeFile(`/home/pyodide/escape_room/${f}.py`, await res.text());
      }));
      const web = py.pyimport('escape_room.web');
      // Call a Python function and parse the JSON it returns.
      return (fn, ...args) => JSON.parse(web[fn](...args));
    })();
    return loading;
  }
  /* Show progress in an overlay (and optional status note) until Python is ready. */
  function boot(overlay, note) {
    if (overlay) overlay.innerHTML = '<div><div class="spin"></div><b>Starting Python…</b>The simulation is Python code running in your browser. The first visit takes about 10 seconds; after that it is cached.</div>';
    if (note) { note.className = 'pynote'; note.textContent = 'Starting Python…'; }
    return load().then((py) => {
      if (overlay) overlay.hidden = true;
      if (note) { note.className = 'pynote ready'; note.textContent = 'Python ready'; }
      return py;
    }, (err) => {
      const local = location.protocol === 'file:'
        ? ' Browsers block this when index.html is opened as a file: run <code>python -m http.server</code> in the project folder and open http://localhost:8000 instead.' : '';
      if (overlay) overlay.innerHTML = `<div><b>Could not start Python</b>${esc(err.message)}.${local}</div>`;
      if (note) { note.className = 'pynote error'; note.textContent = 'Python failed to start: ' + err.message; }
      throw err;
    });
  }
  window.PY = { load, boot };
  window.UNIT7_REPO = REPO;
})();
