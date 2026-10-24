import { test, expect } from '@playwright/test';
import { installFixtures, people, index } from './fixtures.js';

const ANNA = '/asmuo/ona-naujoji-test-anna';
const JONAS = '/asmuo/jonas-bandomasis-test-jonas';

async function ready(page, path = '/') {
  await page.goto(path);
  await expect(page.locator('#results .row')).toHaveCount(3);
}

async function openFilters(page) {
  if (!await page.locator('#filters').isVisible()) await page.locator('#filterToggle').click();
}

async function selectView(page, id) {
  const menu = page.getByRole('button', { name: 'Atidaryti meniu', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.locator(`#${id}`).click();
}

async function noPageOverflow(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow, 'tables should scroll in their own containers, never widen the page').toBe(false);
}

test.beforeEach(async ({ page }) => {
  await installFixtures(page);
});

test('the built Astro page loads its data, navigation and stylesheet', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await ready(page);
  await expect(page.locator('html')).toHaveAttribute('lang', 'lt');
  await expect(page.locator('script[type="module"]:not([src])')).toHaveCount(0);
  await expect(page.locator('#topstats')).toContainText('3 asmenys');
  await expect(page.locator('#count')).toContainText('3');
  await expect(page.locator('.navbar-brand')).toHaveAttribute('href', '/');
  await expect(page.locator('.navbar-brand')).toHaveAccessibleName('Viešpirkiai VRK – kandidatų pradžia');
  await expect(page.locator('.navbar-brand-section')).toHaveText('VRK');
  await openFilters(page);
  await expect(page.locator('#fElection option')).toHaveText(['— visi rinkimai —', '2024 Seimas', '2020 Seimas']);
  for (const control of ['search', 'fElection', 'fParty', 'fMunicipality', 'fConstituency', 'fRole', 'fWon', 'fNationality']) {
    await expect(page.locator(`#${control}`)).toHaveAccessibleName(/\S/);
  }
  for (const asset of await page.locator('img').all()) {
    expect(await asset.evaluate(el => el.complete && el.naturalWidth > 0)).toBe(true);
  }
  expect(await page.locator('#results').evaluate(el => getComputedStyle(el).overflowY)).toBe('auto');
  await noPageOverflow(page);
  expect(errors).toEqual([]);
});

test('search finds a former name and facets compose on the same candidacy', async ({ page }) => {
  await ready(page);
  await page.locator('#search').fill('senesne');
  await expect(page.locator('#results .row')).toHaveCount(1);
  await expect(page.locator('#results')).toContainText('Ona NAUJOJI');
  await page.locator('#search').fill('');
  await expect(page.locator('#results .row')).toHaveCount(3);
  await openFilters(page);
  await page.locator('#fMunicipality').selectOption('0');
  await page.locator('#fParty').selectOption('test-party');
  await page.locator('#fWon').selectOption('won');
  await expect(page.locator('#results .row')).toHaveCount(1);
  await page.locator('#fElection').selectOption('2020-seimo');
  await expect(page.locator('#results .row')).toHaveCount(0);
  await page.locator('#fWon').selectOption('lost');
  await expect(page.locator('#results .row')).toHaveCount(1);
});

test('a nominator chain shows short labels, muted coalition words and full names on hover', async ({ page }) => {
  // Issue #189: synthetic nominators shaped like the registry's three kinds
  // of label -- a party shortName, a coalition's brand, a joint list.
  const parties = {
    ...index.parties,
    'syn-party': { n: 'SP-B', t: 'partija', f: 'Sintetinė partija – Bandymų sąjunga' },
    'syn-brand': { n: '„Kartu mes bandom!“', t: 'koalicija', f: 'Sintetinės partijos ir Kitos partijos koalicija „Kartu mes bandom!“', nr: ['syn-party', 'syn-other'] },
    'syn-joint': { n: 'SP-B + Kita partija', t: 'koalicija', f: 'Sintetinė partija – Bandymų sąjunga, Kita partija', nr: ['syn-party', 'syn-other'] },
    'syn-named': { n: 'Bandymų koalicija', t: 'koalicija' },
  };
  const valdas = {
    pid: 'test-valdas', n: 'Valdas SINTETINIS', b: '1965-06-07', k: 'VALDAS SINTETINIS|1965-06-07',
    e: [
      { id: '2020-seimo', c: 'test-anna', p: 'syn-party', w: true },
      { id: '2020-seimo', c: 'test-anna', p: 'syn-brand', w: true },
      { id: '2024-seimo', c: 'test-anna', p: 'syn-joint', w: false },
      { id: '2024-seimo', c: 'test-anna', p: 'syn-named', w: false },
    ],
  };
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...index, parties, people: [...index.people, valdas] }),
  }));
  await page.goto('/#test-valdas');
  const chain = page.locator('#person .phead .parties');
  await expect(chain).toHaveText('SP-B 2020 → koalicija „Kartu mes bandom!“ 2020 → koalicija SP-B + Kita partija 2024 → Bandymų koalicija 2024');
  const titles = await chain.locator('> span').evaluateAll(spans => spans.map(s => s.title));
  expect(titles).toEqual([
    'Sintetinė partija – Bandymų sąjunga',
    'Sintetinės partijos ir Kitos partijos koalicija „Kartu mes bandom!“',
    'Sintetinė partija – Bandymų sąjunga, Kita partija',
    'Bandymų koalicija',
  ]);
  // The type word is quieter than the name beside it.
  const [word, name] = await chain.locator('> span').nth(1).evaluate(span => [
    getComputedStyle(span.querySelector('.ptype')).color, getComputedStyle(span).color,
  ]);
  expect(word).not.toBe(name);

  // The party's "su koalicijomis" row finds its joint lists as well, while
  // its own row still finds only its own candidacy.
  await openFilters(page);
  await expect(page.locator('#fParty option[value="&syn-party"]')).toHaveText('SP-B su koalicijomis (3)');
  await page.locator('#fParty').selectOption('&syn-party');
  await page.locator('#fElection').selectOption('2024-seimo');
  await expect(page.locator('#results .row')).toHaveCount(1);
  await page.locator('#fParty').selectOption('syn-party');
  await expect(page.locator('#results .row')).toHaveCount(0);
});

test('a nominator chain runs in time order, merging only consecutive repeats, with years', async ({ page }) => {
  // Issue #195: a Vėsaitė-shaped person -- one party, a coalition list in
  // 2000, the party again -- listed out of order and with a nominator-less
  // presidential run, which must not split the second party run.
  const elections = [
    { id: '1996-seimo', kind: 'seimo', date: '1996-10-20', name: '1996 Seimas', shortName: '1996 Seimas' },
    { id: '1997-savivaldybiu', kind: 'savivaldybiu', date: '1997-03-23', name: '1997 savivaldybės', shortName: '1997 savivaldybės' },
    { id: '2000-seimo', kind: 'seimo', date: '2000-10-08', name: '2000 Seimas', shortName: '2000 Seimas' },
    { id: '2002-savivaldybiu', kind: 'savivaldybiu', date: '2002-12-22', name: '2002 savivaldybės', shortName: '2002 savivaldybės' },
    { id: '2004-prezidento', kind: 'prezidento', date: '2004-06-13', name: '2004 prezidentas', shortName: '2004 prezidentas' },
    ...index.elections,
  ];
  const parties = {
    ...index.parties,
    'syn-party': { n: 'SP-B', t: 'partija', f: 'Sintetinė partija – Bandymų sąjunga' },
    'syn-brand': { n: '„Kartu mes bandom!“', t: 'koalicija', f: 'Sintetinės partijos ir Kitos partijos koalicija „Kartu mes bandom!“', nr: ['syn-party'] },
  };
  const birute = {
    pid: 'test-birute', n: 'Birutė SINTETINĖ', b: '1955-01-01', k: 'BIRUTĖ SINTETINĖ|1955-01-01',
    e: [
      { id: '2024-seimo', c: 'test-anna', p: 'syn-party', w: true },
      { id: '2000-seimo', c: 'test-anna', p: 'syn-brand', w: true },
      { id: '1996-seimo', c: 'test-anna', p: 'syn-party', w: false },
      { id: '2004-prezidento', c: 'test-anna', w: false },
      { id: '2002-savivaldybiu', c: 'test-anna', p: 'syn-party', w: true },
      { id: '1997-savivaldybiu', c: 'test-anna', p: 'syn-party', w: true },
      { id: '2020-seimo', c: 'test-anna', p: 'syn-party', w: true },
    ],
  };
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...index, elections, parties, people: [...index.people, birute] }),
  }));
  await page.goto('/#test-birute');
  const chain = page.locator('#person .phead .parties');
  await expect(chain).toHaveText('SP-B 1996–1997 → koalicija „Kartu mes bandom!“ 2000 → SP-B 2002–2024');
  const titles = await chain.locator('> span').evaluateAll(spans => spans.map(s => s.title));
  expect(titles).toEqual([
    'Sintetinė partija – Bandymų sąjunga',
    'Sintetinės partijos ir Kitos partijos koalicija „Kartu mes bandom!“',
    'Sintetinė partija – Bandymų sąjunga',
  ]);
  // The years are quieter than the name they follow.
  const [years, name] = await chain.locator('> span').first().evaluate(span => [
    getComputedStyle(span.querySelector('.pyears')).color, getComputedStyle(span).color,
  ]);
  expect(years).not.toBe(name);
});

test('the page fetches its data by absolute URL, so a deep path loads too (#184)', async ({ page }) => {
  const requested = [];
  page.on('request', request => requested.push(new URL(request.url()).pathname));
  await ready(page, JONAS);
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  for (const path of ['/people.json', '/docs/concept-map.json', '/field-labels.json']) {
    expect(requested, path).toContain(path);
  }
  expect(requested.some(path => path.startsWith('/data/'))).toBe(true);
  expect(requested.filter(path => path.startsWith('/asmuo/') && path !== JONAS)).toEqual([]);
  expect(requested.filter(path => path.startsWith('/dashboard'))).toEqual([]);
});

// Issue #184: every view has its own path, and a link to one opens straight
// into it from a fresh tab -- the server answers each with the page.
for (const [path, heading, view] of [
  ['/', 'Kandidatai ir rinkimai', 'overviewBtn'],
  [ANNA, 'Ona NAUJOJI', 'overviewBtn'],
  ['/suvestine', 'Rinkimų suvestinė', 'aggBtn'],
  ['/iskelejai', 'Iškėlėjo suvestinė', 'nominatorBtn'],
  ['/apreptis', 'Ką klausė kiekvienų rinkimų anketa', 'coverageBtn'],
  ['/pokyciai', 'Didžiausi pokyčiai', 'moversBtn'],
  ['/palyginti/test-anna,test-jonas', 'Asmenų palyginimas', 'overviewBtn'],
]) {
  test(`${path} opens its view directly`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(path);
    expect(response.status()).toBe(200);
    await expect(page.locator('#results .row')).toHaveCount(3);
    const title = path === '/' ? page.getByRole('heading', { name: heading, exact: true }) : page.locator('#person h2');
    await expect(title).toHaveText(heading);
    await expect(page.locator(`#${view}`)).toHaveAttribute('aria-current', 'page');
    expect(new URL(page.url()).pathname).toBe(path);
    expect(errors).toEqual([]);
  });
}

test('a comparison link checks its people and the compare bar', async ({ page }) => {
  await ready(page, '/palyginti/test-anna,test-jonas');
  await expect(page.locator('#person table.cmp thead th')).toHaveCount(3);
  await expect(page.getByRole('checkbox', { name: 'Pažymėti palyginimui: Ona NAUJOJI' })).toBeChecked();
  await expect(page.getByRole('checkbox', { name: 'Pažymėti palyginimui: Jonas BANDOMASIS' })).toBeChecked();
  await expect(page.locator('#cmpcount')).toHaveText('pažymėta: 2 asmenys');
});

test('a missing or wrong slug, a bare pid and an old hash all rewrite to the canonical path', async ({ page }) => {
  for (const from of ['/asmuo/test-anna', '/asmuo/kazkas-kitas-test-anna/', '/#test-anna', `/#${encodeURIComponent(people[0].k)}`]) {
    await ready(page, from);
    await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
    await expect(page).toHaveURL(/\/asmuo\/ona-naujoji-test-anna$/);
    // Rewritten in place: Back leaves the page rather than revisiting the old URL.
    const entries = await page.evaluate(() => history.length);
    await page.goto('about:blank');
    await page.goBack();
    await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
    expect(await page.evaluate(() => history.length)).toBe(entries + 1);
  }
});

for (const [path, key] of [
  ['/asmuo/nera-tokio-pzzzzzzzzzzzz', 'nera-tokio-pzzzzzzzzzzzz'],
  ['/#nera-tokio', 'nera-tokio'],
  ['/palyginti/test-anna,nera-tokio', 'test-anna,nera-tokio'],
]) {
  test(`${path} names nobody and says so`, async ({ page }) => {
    await ready(page, path);
    await expect(page.locator('#person .placeholder')).toHaveText(`Nuoroda „${key}“ nieko neatitinka.`);
  });
}

test('Back and Forward move between a person and the statistics', async ({ page }) => {
  await ready(page, ANNA);
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await selectView(page, 'aggBtn');
  await expect(page.locator('#person h2')).toHaveText('Rinkimų suvestinė');
  await expect(page).toHaveURL(/:8792\/suvestine$/);
  await page.goBack();
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page).toHaveURL(/\/asmuo\/ona-naujoji-test-anna$/);
  await page.goForward();
  await expect(page.locator('#person h2')).toHaveText('Rinkimų suvestinė');
  await expect(page.locator('#aggBtn')).toHaveAttribute('aria-current', 'page');
  // A person linked from inside a view is a real link, routed in place.
  await selectView(page, 'moversBtn');
  await expect(page).toHaveURL(/\/pokyciai$/);
  const link = page.locator('#person table.ranking a').first();
  await expect(link).toHaveAttribute('href', /^\/asmuo\/[a-z-]+-test-[a-z]+$/);
  const name = await link.textContent();
  await link.click();
  await expect(page.locator('#person h2')).toHaveText(name.split(' · ')[0]);
  await page.goBack();
  await expect(page.locator('#person h2')).toHaveText('Didžiausi pokyčiai');
});

test('legacy links canonicalize and Back/Forward restore the selected person', async ({ page }) => {
  await ready(page, `/#${encodeURIComponent(people[0].ak[0])}`);
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page).toHaveURL(/\/asmuo\/ona-naujoji-test-anna$/);
  await expect(page.locator('#person')).toBeFocused();
  await page.locator(`#results a[href="${JONAS}"]`).click();
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await page.goBack();
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page).toHaveURL(/\/asmuo\/ona-naujoji-test-anna$/);
  await page.goForward();
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await expect(page.locator('#announce')).toContainText('Jonas BANDOMASIS');
  await selectView(page, 'overviewBtn');
  await expect(page.getByRole('heading', { name: 'Kandidatai ir rinkimai', exact: true })).toBeVisible();
  await expect(page.locator('#topstats')).toContainText('3 asmenys');
  await page.locator(`#results a[href="${JONAS}"]`).click();
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await page.locator('.navbar-brand').click();
  await expect(page).toHaveURL(/:8792\/$/);
  await expect(page.getByRole('heading', { name: 'Kandidatai ir rinkimai', exact: true })).toBeVisible();
  await expect(page.locator('#results .row')).toHaveCount(3);
});

test('keyboard checkboxes compare people and clear the selection', async ({ page }) => {
  await ready(page);
  for (const name of ['Ona NAUJOJI', 'Jonas BANDOMASIS']) {
    const checkbox = page.getByRole('checkbox', { name: `Pažymėti palyginimui: ${name}` });
    await checkbox.focus();
    await checkbox.press('Space');
    await expect(checkbox).toBeChecked();
  }
  await page.locator('#cmpGo').click();
  await expect(page.locator('#person h2')).toHaveText('Asmenų palyginimas');
  await expect(page.locator('#person table.cmp thead th')).toHaveCount(3);
  await expect(page.locator('#person table.cmp')).toContainText('Bandymų universitetas');
  await noPageOverflow(page);
  await page.locator('#cmpClear').click();
  await expect(page.locator('#cmpbar')).toBeHidden();
  await expect(page.locator('#results input:checked')).toHaveCount(0);
});

test('person tabs show actual records, money and election comparison', async ({ page }) => {
  await ready(page, ANNA);
  await expect(page.locator('#person details.ecard')).toHaveCount(2);
  await expect(page.locator('#person details.ecard summary').first()).toContainText('2024 m.');
  await expect(page.locator('#person details.ecard summary').last()).toContainText('2020 m.');
  await page.getByRole('button', { name: 'Palyginimas tarp rinkimų', exact: true }).click();
  const comparison = page.locator('#person table.cmp:visible');
  await expect(comparison).toContainText('Bandymų universitetas');
  await expect(comparison.locator('thead th')).toHaveText(['Laukas', '2024 Seimas', '2020 Seimas']);
  await noPageOverflow(page);
  await page.getByRole('button', { name: 'Turtas ir pajamos', exact: true }).click();
  await expect(page.locator('#person svg:visible')).toHaveCount(1);
  await expect(page.locator('#person table:visible')).toContainText('€');
  await expect(page.locator('#person table:visible thead th')).toHaveText(['Rodiklis', '2024 Seimas', '2020 Seimas']);
  await expect(page.locator('#person table:visible tbody tr').first().locator('td').first()).toHaveText(/20\s000\s€/);
  const chartElections = (await page.locator('#person svg:visible text').allTextContents()).filter(text => text.endsWith('Seimas'));
  expect(chartElections).toEqual(['2020 Seimas', '2024 Seimas']);
  await noPageOverflow(page);
});

test('wide record tables keep nested labels and values readable', async ({ page }) => {
  await ready(page, ANNA);
  const section = page.locator('.ecard .sec').filter({ has: page.getByRole('heading', { name: 'Politinės kampanijos dalyvio duomenys', exact: true }) });
  const table = section.locator('table.rec');
  await expect(table).toBeVisible();
  const layout = await table.evaluate(table => {
    const status = table.tBodies[0].rows[0].cells[0].firstElementChild;
    const pairs = [...table.querySelectorAll('dl > dd')].map(dd => ({
      width: dd.getBoundingClientRect().width,
      top: dd.getBoundingClientRect().top,
      labelBottom: dd.previousElementSibling.getBoundingClientRect().bottom,
    }));
    return {
      statusHeight: status.getBoundingClientRect().height,
      lineHeight: parseFloat(getComputedStyle(status).lineHeight),
      height: table.getBoundingClientRect().height,
      scrolls: table.parentElement.scrollWidth > table.parentElement.clientWidth,
      pairs,
    };
  });
  expect(layout.statusHeight, 'a single word must not split across lines').toBeLessThanOrEqual(layout.lineHeight + 1);
  expect(layout.height, 'nested data should not create a page of single letters').toBeLessThan(600);
  expect(layout.scrolls, 'wide records scroll inside their wrapper').toBe(true);
  for (const pair of layout.pairs) {
    expect(pair.width).toBeGreaterThanOrEqual(200);
    expect(pair.top).toBeGreaterThanOrEqual(pair.labelBottom);
  }
  await expect(table.getByRole('link')).toHaveAttribute('href', /example\.org\/ataskaitos/);
  await noPageOverflow(page);
});

test('all four summary views remain usable', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await ready(page);
  for (const [button, heading] of [
    ['aggBtn', 'Rinkimų suvestinė'],
    ['nominatorBtn', 'Iškėlėjo suvestinė'],
    ['coverageBtn', 'Ką klausė kiekvienų rinkimų anketa'],
    ['moversBtn', 'Didžiausi pokyčiai'],
  ]) {
    await selectView(page, button);
    await expect(page.locator('#person h2')).toHaveText(heading);
    await expect(page.locator('#topstats')).toHaveCount(0);
    await expect(page.locator('#person table').first()).toBeVisible();
    if (button === 'aggBtn') {
      await expect(page.locator('#aggElection option')).toHaveText(['2024 Seimas', '2020 Seimas']);
    } else if (button === 'nominatorBtn') {
      await expect(page.locator('#person table').first().locator('tbody th')).toHaveText(['2024 Seimas', '2020 Seimas']);
    } else if (button === 'coverageBtn') {
      await expect(page.locator('table.covgrid thead th.vert')).toHaveText(['2024 Seimas', '2020 Seimas']);
      await expect(page.locator('table.covgrid tbody tr').first().locator('td')).toHaveText(['100', '50']);
    } else if (button === 'moversBtn') {
      await expect(page.locator('table.ranking tbody tr').first().locator('td').last()).toHaveText(/\+10\s000\s€/);
    }
    for (const select of await page.locator('#person select').all()) {
      await expect(select).toHaveAccessibleName(/\S/);
    }
    await noPageOverflow(page);
  }
  await selectView(page, 'overviewBtn');
  await expect(page.locator('#topstats')).toContainText('3 asmenys');
  expect(errors).toEqual([]);
});

test('CSV download contains only the filtered candidacies', async ({ page }) => {
  await ready(page);
  await openFilters(page);
  await page.locator('#fElection').selectOption('2024-seimo');
  await page.locator('#fParty').selectOption('test-party');
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#csvBtn').click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  const text = Buffer.concat(chunks).toString('utf8');
  expect(text.charCodeAt(0)).toBe(0xfeff);
  expect(text.trim().split('\r\n')).toHaveLength(2);
  expect(text).toContain('Ona NAUJOJI');
  expect(text).toContain('2024-seimo');
  expect(text).not.toContain('Jonas BANDOMASIS');
});

// Records every photo element that ever enters the person header, so a box
// that appears and is removed again still fails the test.
async function watchPortraits(page) {
  await page.addInitScript(() => {
    window.__portraits = [];
    new MutationObserver(mutations => {
      for (const m of mutations) for (const node of m.addedNodes) {
        if (node.nodeType !== 1) continue;
        for (const img of node.matches('img') ? [node] : node.querySelectorAll('img')) {
          if (img.closest('.phead')) window.__portraits.push(img.getAttribute('src'));
        }
      }
    }).observe(document, { childList: true, subtree: true });
  });
}

// Every image request the page makes: portraits, and the archive sidecars it
// must no longer touch.
function watchImageRequests(page) {
  const seen = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (/\/(portraits|photos)\//.test(url.pathname)) seen.push(url.pathname + url.search);
  });
  return seen;
}

test('a person with ph loads their versioned web portrait', async ({ page }) => {
  await installFixtures(page, { portraits: { 'test-anna': 200 }, recordPhotos: true });
  await watchPortraits(page);
  const requests = watchImageRequests(page);
  await ready(page, ANNA);
  const img = page.locator('.phead img');
  await expect(img).toBeVisible();
  await expect(img).toHaveAttribute('src', '/portraits/test-anna.webp?v=test1');
  expect(await page.evaluate(() => window.__portraits)).toEqual(['/portraits/test-anna.webp?v=test1']);
  // One request, and none for the records' full-resolution sidecars.
  expect(requests).toEqual(['/portraits/test-anna.webp?v=test1']);
});

test('a person without ph makes no photo request', async ({ page }) => {
  await installFixtures(page, { portraits: { 'test-anna': 200 }, recordPhotos: true });
  await watchPortraits(page);
  const requests = watchImageRequests(page);
  await ready(page, JONAS);
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await expect(page.locator('#person')).toContainText('Bandymų specialistas');
  await page.waitForTimeout(300);
  expect(requests).toEqual([]);
  expect(await page.evaluate(() => window.__portraits)).toEqual([]);
});

test('a missing portrait never shows an empty photo box', async ({ page }) => {
  await installFixtures(page, { portraits: { 'test-anna': 404 }, photoDelay: 400 });
  await watchPortraits(page);
  const requests = watchImageRequests(page);
  await ready(page, ANNA);
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  const left = await page.locator('.phead > div').boundingBox();
  // Poll while the delayed 404 is still in flight, then after it settles.
  for (let i = 0; i < 10; i++) {
    expect(await page.locator('.phead img').count()).toBe(0);
    await page.waitForTimeout(100);
  }
  await expect.poll(() => requests.length).toBe(1);
  await page.waitForTimeout(200);
  expect(requests).toEqual(['/portraits/test-anna.webp?v=test1']);
  expect(await page.evaluate(() => window.__portraits)).toEqual([]);
  expect((await page.locator('.phead > div').boundingBox()).x).toBe(left.x);
});

test('a late portrait stays off the next person page', async ({ page }) => {
  await installFixtures(page, { portraits: { 'test-anna': 200 }, photoDelay: 600 });
  await ready(page, ANNA);
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await page.locator('#results .row', { hasText: 'Jonas BANDOMASIS' }).click();
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await page.waitForTimeout(900);
  await expect(page.locator('.phead img')).toHaveCount(0);
});

test('failed index reports a visible error', async ({ page }) => {
  await installFixtures(page, { failedIndex: true });
  await page.goto('/');
  await expect(page.locator('#topstats')).toContainText('indekso įkelti nepavyko');
  await expect(page.locator('#person [role="alert"]')).toContainText('Duomenų šiuo metu pasiekti nepavyko');
  await expect(page.getByRole('button', { name: 'Bandyti dar kartą' })).toBeVisible();
  await installFixtures(page);
  await page.getByRole('button', { name: 'Bandyti dar kartą' }).click();
  await expect(page.locator('#results .row')).toHaveCount(3);
});

test('a missing record warns while retaining the loaded election', async ({ page }) => {
  await installFixtures(page, { failedRecord: '/data/2020-seimo/test-anna-2020-seimo.json' });
  await ready(page, ANNA);
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page.locator('#person [role="alert"]')).toBeVisible();
  await expect(page.locator('#person')).toContainText('Bandymų universitetas');
});

test('mobile filters fold and reopening them preserves selected values', async ({ page }) => {
  test.skip(test.info().project.name === 'desktop', 'narrow-screen interaction');
  await ready(page);
  await expect(page.locator('#filters')).toBeHidden();
  await page.locator('#filterToggle').click();
  await page.locator('#fMunicipality').selectOption('0');
  await page.locator('#filterToggle').click();
  await expect(page.locator('#filters')).toBeHidden();
  await page.locator('#filterToggle').click();
  await expect(page.locator('#fMunicipality')).toHaveValue('0');
  await expect(page.locator('#results .row')).toHaveCount(1);
  await noPageOverflow(page);
});

test('theme persists and keyboard skip preserves the person link', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await ready(page, ANNA);
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await page.locator('#themeToggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('#themeToggle')).toHaveAttribute('aria-pressed', 'true');
  await page.reload();
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.locator('.skip-link').focus();
  await page.locator('.skip-link').press('Enter');
  await expect(page).toHaveURL(/\/asmuo\/ona-naujoji-test-anna$/);
  await expect(page.locator('#workspace')).toBeFocused();
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await selectView(page, 'overviewBtn');
  await expect(page.locator('#search')).toBeFocused();
});

test('narrow viewports contain wide financial and coverage tables', async ({ page }) => {
  test.skip(test.info().project.name !== 'phone', '320px stress check');
  await page.setViewportSize({ width: 320, height: 740 });
  await ready(page, ANNA);
  await page.getByRole('button', { name: 'Turtas ir pajamos', exact: true }).click();
  await expect(page.locator('#person svg:visible')).toHaveCount(1);
  const tableScroll = await page.locator('#person table:visible').evaluate(table => table.parentElement.scrollLeft);
  expect(tableScroll, 'newest-first table opens at its left edge').toBe(0);
  const chartScroll = await page.locator('#person svg:visible').evaluate(svg => {
    const wrap = svg.parentElement;
    return { left: wrap.scrollLeft, max: wrap.scrollWidth - wrap.clientWidth };
  });
  expect(chartScroll.max).toBeGreaterThan(0);
  expect(chartScroll.left, 'chronological chart still opens on its newest elections').toBe(chartScroll.max);
  await noPageOverflow(page);
  await selectView(page, 'coverageBtn');
  await expect(page.locator('#person table.covgrid')).toBeVisible();
  await noPageOverflow(page);
});

test('wide tables fade only on the side with more to scroll, never over the sticky column', async ({ page }) => {
  const project = test.info().project.name;
  test.skip(project === 'tablet', '320px and desktop cover both outcomes');
  if (project === 'phone') await page.setViewportSize({ width: 320, height: 740 });
  await ready(page, ANNA);
  await page.getByRole('button', { name: 'Turtas ir pajamos', exact: true }).click();
  const wrap = page.locator('#person table.cmp:visible').locator('..');
  await expect(wrap).toHaveClass(/\btablewrap\b/);

  if (project === 'desktop') {
    expect(await wrap.evaluate(w => w.scrollWidth <= w.clientWidth)).toBe(true);
    await expect(wrap).not.toHaveAttribute('data-more-left');
    await expect(wrap).not.toHaveAttribute('data-more-right');
    expect(await wrap.evaluate(w => getComputedStyle(w).maskImage)).toBe('none');
    return;
  }

  await expect(wrap).toHaveAttribute('data-more-right', '');
  await expect(wrap).not.toHaveAttribute('data-more-left');
  await wrap.evaluate(w => { w.scrollLeft = w.scrollWidth; });
  await expect(wrap).toHaveAttribute('data-more-left', '');
  await expect(wrap).not.toHaveAttribute('data-more-right');

  // The fade starts where the sticky column ends: the column looks the same
  // with the mask as without, and the cells scrolled under the fade do not.
  const sticky = await wrap.evaluate(w => {
    const cell = w.querySelector('table').rows[0].cells[0];
    return { var: parseFloat(w.style.getPropertyValue('--sticky')), width: cell.getBoundingClientRect().width };
  });
  expect(Math.abs(sticky.var - sticky.width)).toBeLessThanOrEqual(1);
  await wrap.scrollIntoViewIfNeeded();
  const box = await wrap.boundingBox();
  const column = { x: box.x, y: box.y, width: sticky.width, height: box.height };
  const fade = { x: box.x + sticky.width, y: box.y, width: 24, height: box.height };
  const masked = [await page.screenshot({ clip: column }), await page.screenshot({ clip: fade })];
  await wrap.evaluate(w => w.style.setProperty('mask', 'none'));
  const plain = [await page.screenshot({ clip: column }), await page.screenshot({ clip: fade })];
  expect(masked[0].equals(plain[0]), 'the sticky column is never faded').toBe(true);
  expect(masked[1].equals(plain[1]), 'the content after it is').toBe(false);
});

test('mobile menu supports keyboard dismissal, view selection and resizing', async ({ page }) => {
  test.skip(test.info().project.name === 'desktop', 'compact navigation');
  await ready(page);
  const toggle = page.locator('#menuToggle');
  await expect(page.locator('#overviewBtn')).toBeHidden();
  await toggle.focus();
  await toggle.press('Enter');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#overviewBtn')).toBeFocused();
  await expect(page.locator('#siteMenu').getByRole('link', { name: 'Apie projektą' })).toBeVisible();
  await expect(page.locator('main')).toHaveJSProperty('inert', true);
  await toggle.focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('.navbar-brand')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(toggle).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(toggle).toBeFocused();
  await expect(page.locator('main')).toHaveJSProperty('inert', false);

  await selectView(page, 'coverageBtn');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('#person')).toBeFocused();
  await expect(page.locator('#person h2')).toHaveText('Ką klausė kiekvienų rinkimų anketa');
  await noPageOverflow(page);

  await toggle.click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(toggle).toBeHidden();
  await expect(page.locator('#coverageBtn')).toBeVisible();
  await expect(page.locator('main')).toHaveJSProperty('inert', false);
  await page.setViewportSize({ width: 375, height: 360 });
  await expect(page.locator('#overviewBtn')).toBeHidden();
  await toggle.click();
  const lastLink = page.locator('#siteMenu .navbar-links a').last();
  await lastLink.scrollIntoViewIfNeeded();
  await expect(lastLink).toBeInViewport();
  await noPageOverflow(page);
});

test('the sidebar border meets the footer on a tall desktop window', async ({ page }) => {
  test.skip(test.info().project.name !== 'desktop', 'two-column layout');
  await page.setViewportSize({ width: 1440, height: 1600 });
  await ready(page);
  const gap = await page.evaluate(() => document.querySelector('footer').getBoundingClientRect().top
    - document.querySelector('#left').getBoundingClientRect().bottom);
  expect(Math.abs(gap)).toBeLessThan(1);
});
