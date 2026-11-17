// Behavioral test for the home-page client JS, run against the live server.
const http = require('http');

function fetchHtml(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: 'localhost', port: 8000, path }, (res) => {
      let b = '';
      res.on('data', (c) => (b += c));
      res.on('end', () => resolve({ status: res.statusCode, body: b }));
    }).on('error', reject);
  });
}

class El {
  constructor(tag, id) {
    this.tagName = tag;
    this.id = id || '';
    this.children = [];
    this.listeners = {};
    this.value = '';
    this.hidden = false;
    this.text = '';
    this.attrs = {};
    this._innerHTML = '';
  }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }
  dispatch(ev, arg) { (this.listeners[ev] || []).forEach((fn) => fn(arg)); }
  appendChild(c) { this.children.push(c); return c; }
  set innerHTML(v) { this._innerHTML = v; if (v === '') this.children = []; }
  get innerHTML() { return this._innerHTML; }
  set textContent(v) { this.text = String(v); this.children = []; }
  get textContent() {
    if (this.children.length === 0) return this.text;
    return this.children.map((c) => c.textContent).join('');
  }
  cardCount() { return this.children.filter((c) => c.attrs && c.attrs['data-testid'] === 'spot-card').length; }
  cardNames() { return this.children.filter((c) => c.attrs && c.attrs['data-testid'] === 'spot-card').map((c) => c.children[0].children[0].text); }
  cardCity0() { return this.children.filter((c) => c.attrs && c.attrs['data-testid'] === 'spot-card').map((c) => c.children[1].text); }
}

const els = {};
['q', 'country', 'type', 'results', 'result-count', 'empty', 'filters'].forEach((id) => (els[id] = new El('div', id)));
els.empty.text = 'No capybaras here yet';
global.document = {
  getElementById: (id) => els[id],
  createElement: (tag) => new El(tag),
};
global.URLSearchParams = URLSearchParams;
global.fetch = (url) => fetchHtml(url).then((r) => ({ json: () => Promise.resolve(JSON.parse(r.body)) }));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const home = await fetchHtml('/');
  const m = home.body.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) throw new Error('no script block');
  eval(m[1]);

  let fails = 0;
  const check = (label, cond, extra = '') => {
    if (!cond) fails++;
    console.log((cond ? 'PASS' : 'FAIL'), label, cond ? '' : extra);
  };

  // 1. type as you go: "capy" (debounce 200ms)
  els.q.value = 'capy';
  els.q.dispatch('input');
  await sleep(400);
  const api1 = JSON.parse((await fetchHtml('/api/spots?q=capy')).body);
  check('typed query rendered', els.results.cardCount() === api1.length, `${els.results.cardCount()} vs ${api1.length}`);
  check('typed query count text', els['result-count'].textContent === (api1.length === 1 ? '1 spot' : api1.length + ' spots'), els['result-count'].textContent);
  check('empty state hidden when results', els.empty.hidden === true);

  // 2. nonsense query -> empty state
  els.q.value = 'zzzznope';
  els.q.dispatch('input');
  await sleep(400);
  check('nonsense -> 0 cards', els.results.cardCount() === 0);
  check('nonsense -> 0 spots text', els['result-count'].textContent === '0 spots', els['result-count'].textContent);
  check('nonsense -> empty state visible', els.empty.hidden === false);
  check('empty state text', els.empty.text === 'No capybaras here yet', els.empty.text);

  // 3. Enter (form submit) with q + type select
  els.q.value = 'zoo';
  els.type.value = 'zoo';
  els.q.dispatch('keydown', { key: 'Enter', preventDefault() {} });
  els.filters.dispatch('submit', { preventDefault() {} });
  await sleep(400);
  const api2 = JSON.parse((await fetchHtml('/api/spots?q=zoo&type=zoo')).body);
  check('enter+select combo', els.results.cardCount() === api2.length, `${els.results.cardCount()} vs ${api2.length}`);
  check('combo singular/plural', els['result-count'].textContent === (api2.length === 1 ? '1 spot' : api2.length + ' spots'), els['result-count'].textContent);

  // 4. country select change only
  els.q.value = '';
  els.type.value = '';
  els.country.value = 'gb';
  els.country.dispatch('change');
  await sleep(400);
  const api3 = JSON.parse((await fetchHtml('/api/spots?country=gb')).body);
  check('country select only', els.results.cardCount() === api3.length, `${els.results.cardCount()} vs ${api3.length}`);

  // 5. clear all -> back to 40
  els.country.value = '';
  els.country.dispatch('change');
  await sleep(400);
  check('cleared -> 40', els.results.cardCount() === 40, String(els.results.cardCount()));
  check('cleared count text', els['result-count'].textContent === '40 spots', els['result-count'].textContent);

  // 6. card internals: heading link + source link
  const card0 = els.results.children[0];
  const h2link = card0.children[0].children[0];
  const src = card0.children[card0.children.length - 1];
  check('card heading is h2>a', card0.children[0].tagName === 'h2' && h2link.tagName === 'a');
  check('card name link href', typeof h2link.href === 'string' && h2link.href.startsWith('/spots/'), String(h2link.href));
  check('card source link text', src.text === 'Source');
  check('card source href', typeof src.href === 'string' && src.href.startsWith('http'), String(src.href));

  console.log();
  console.log(fails ? `FAILURES: ${fails}` : 'ALL PASS');
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error('HARNESS ERROR:', e.message); process.exit(2); });