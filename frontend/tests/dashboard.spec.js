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

// Each nominator item's tooltip, found through its aria-describedby (issue #200).
async function fullNames(chain) {
  return chain.locator('.pitem .pname').evaluateAll(items => items.map(item =>
    document.getElementById(item.getAttribute('aria-describedby')).querySelector('strong').textContent));
}

function tipOf(page, trigger) {
  return trigger.getAttribute('aria-describedby').then(id => page.locator(`#${id}`));
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

// Nationality is declared per candidacy, but the filter lists people (issue
// #176): the dropdown counts each person once per group they ever declared,
// so a count is the rows that group returns.
test('the nationality dropdown counts people, the rows its filter returns (#176)', async ({ page }) => {
  const candidacy = (id, c, tb) => ({ id, c, p: 'test-party', tb, m: [null, null, null, null] });
  const served = {
    ...index,
    people: [
      ...people,
      { pid: 'test-ingus', n: 'Ingušas TRISKART', b: null, k: 'INGUŠAS TRISKART|',
        e: [candidacy('2020-seimo', 'test-ingus', 2), candidacy('2024-seimo', 'test-ingus', 2), candidacy('2024-seimo', 'test-ingus-2', 2)] },
      { pid: 'test-dvi', n: 'Sergejus DVIGUBAS', b: null, k: 'SERGEJUS DVIGUBAS|',
        e: [candidacy('2020-seimo', 'test-dvi', 3), candidacy('2024-seimo', 'test-dvi', 4)] },
    ],
    nationalities: [...index.nationalities, { label: 'ingušai' }, { label: 'rusai' }, { label: 'mariai' }],
  };
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(served),
  }));
  await page.goto('/');
  await expect(page.locator('#results .row')).toHaveCount(5);
  await openFilters(page);
  await expect(page.locator('#fNationality option')).toHaveText([
    '— visos tautybės —', 'Lietuviai (1)', 'Lenkai (1)', 'Ingušai (1)', 'Rusai (1)', 'Mariai (1)',
  ]);
  for (const [value, names] of [['2', ['Ingušas TRISKART']], ['3', ['Sergejus DVIGUBAS']], ['4', ['Sergejus DVIGUBAS']]]) {
    await page.locator('#fNationality').selectOption(value);
    await expect(page.locator('#results .row')).toHaveCount(names.length);
    for (const name of names) await expect(page.locator('#results')).toContainText(name);
  }
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
  // The full names moved from `title` into the custom tooltips (issue #200).
  expect(await fullNames(chain)).toEqual([
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

  // A label that opens its own line, card header or option capitalises the
  // type word; inside the chain above it stays lower case.
  await expect(page.locator('#person summary .party').filter({ hasText: 'Kartu mes bandom' }).first()).toHaveText('Koalicija „Kartu mes bandom!“');
  await expect(page.locator('#fParty option[value="syn-joint"]')).toHaveText(/^Koalicija SP-B \+ Kita partija \(\d+\)$/);

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
  expect(await fullNames(chain)).toEqual([
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
  ['/partiju-keitimai', 'Partijų keitimai', 'switchesBtn'],
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

// Eight alternating runs, 2001-2008: a Tomaševski-shaped line (issue #198).
const foldElections = Array.from({ length: 8 }, (_, i) => ({
  id: `${2001 + i}-seimo`, kind: 'seimo', date: `${2001 + i}-10-01`, name: `${2001 + i} Seimas`, shortName: `${2001 + i} Seimas`,
}));
const foldParties = {
  ...index.parties,
  'syn-party': { n: 'SP-B', t: 'partija', f: 'Sintetinė partija – Bandymų sąjunga' },
  'syn-joint': { n: 'SP-B + Kita partija', t: 'koalicija', f: 'Sintetinė partija – Bandymų sąjunga, Kita partija', nr: ['syn-party', 'other-party'] },
};
const foldPerson = {
  pid: 'test-folded', n: 'Valdemar SINTETINIS', b: '1965-06-07', k: 'VALDEMAR SINTETINIS|1965-06-07',
  e: foldElections.map((e, i) => ({ id: e.id, c: 'test-anna', p: i % 2 ? 'syn-joint' : 'syn-party', w: false })),
};

async function foldFixture(page) {
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...index, elections: [...foldElections, ...index.elections], parties: foldParties, people: [...index.people, foldPerson] }),
  }));
  await page.goto('/asmuo/test-folded');
  return page.locator('#person .phead .parties');
}

test('a long nominator line folds its middle and expands in place', async ({ page }) => {
  const chain = await foldFixture(page);
  const more = chain.getByRole('button', { name: 'Rodyti dar 4' });
  const less = chain.getByRole('button', { name: 'Suskleisti' });
  const collapsed = 'SP-B 2001 → koalicija SP-B + Kita partija 2002 → … → SP-B 2007 → koalicija SP-B + Kita partija 2008';
  await expect(chain).toHaveText(collapsed, { useInnerText: true });
  await expect(more).toHaveAttribute('aria-expanded', 'false');
  await expect(chain.locator('.pitem:visible')).toHaveCount(4);
  await expect(less).toBeHidden();

  await more.click();
  await expect(chain.locator('.pitem:visible')).toHaveCount(8);
  await expect(chain).toHaveText(
    'SP-B 2001 → koalicija SP-B + Kita partija 2002 → SP-B 2003 → koalicija SP-B + Kita partija 2004 → SP-B 2005 → koalicija SP-B + Kita partija 2006 → SP-B 2007 → koalicija SP-B + Kita partija 2008 Suskleisti',
    { useInnerText: true },
  );
  await expect(more).toBeHidden();
  await expect(less).toHaveAttribute('aria-expanded', 'true');

  // Collapsing hands focus back to the button that expands it again.
  await less.click();
  await expect(chain).toHaveText(collapsed, { useInnerText: true });
  await expect(more).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(chain.locator('.pitem:visible')).toHaveCount(8);
  await less.focus();
  await page.keyboard.press('Enter');
  await expect(chain.locator('.pitem:visible')).toHaveCount(4);
  await noPageOverflow(page);
});

test('nominator tooltips show on hover with name, members and elections, and replace title', async ({ page }) => {
  const chain = await foldFixture(page);
  const items = chain.locator('.pitem .pname');
  await expect(chain.locator('[title]')).toHaveCount(0);
  const tip = await tipOf(page, items.nth(1));
  await expect(tip).toHaveAttribute('role', 'tooltip');
  await expect(tip).toBeHidden();

  await items.nth(1).hover();
  await expect(tip).toBeVisible();
  await expect(tip).toContainText('Sintetinė partija – Bandymų sąjunga, Kita partija');
  await expect(tip).toContainText('SP-B + Pavyzdžių komitetas');
  await expect(tip).not.toContainText('Koalicija');
  await expect(tip).toContainText('Seimas 2002');
  // Moving to the next item swaps the bubble rather than stacking a second.
  await items.nth(0).hover();
  const first = await tipOf(page, items.nth(0));
  await expect(first).toBeVisible();
  await expect(first).toContainText('Seimas 2001');
  await expect(tip).toBeHidden();
  await page.mouse.move(1, 1);
  await expect(first).toBeHidden();

  // The fold button is a bare ellipsis with no tooltip of its own.
  const more = chain.getByRole('button', { name: 'Rodyti dar 4' });
  await expect(more).toHaveText('…');
  await expect(more).not.toHaveAttribute('aria-describedby', /.+/);
  await more.click();
  await expect(chain.locator('.pitem [title], .pitem[title]')).toHaveCount(0);
});

test('only the name opens a nominator tooltip, not the type word or the years', async ({ page }) => {
  const chain = await foldFixture(page);
  await chain.locator('.pitem .ptype').first().hover();
  await page.waitForTimeout(300);
  await expect(page.locator('.vp-tip.is-visible')).toHaveCount(0);
  await chain.locator('.pitem .pyears').first().hover();
  await page.waitForTimeout(300);
  await expect(page.locator('.vp-tip.is-visible')).toHaveCount(0);
  await chain.locator('.pitem .pname').first().hover();
  await expect(page.locator('.vp-tip.is-visible')).toHaveCount(1);
});

test('nominator tooltips follow the keyboard: Tab shows, Esc closes', async ({ page }) => {
  const chain = await foldFixture(page);
  const items = chain.locator('.pitem .pname');
  await page.locator('#person .phead h2').click();
  await page.keyboard.press('Tab');
  await expect(items.nth(0)).toBeFocused();
  const first = await tipOf(page, items.nth(0));
  await expect(first).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(first).toBeHidden();
  await expect(items.nth(0)).toBeFocused();

  await page.keyboard.press('Tab');
  const second = await tipOf(page, items.nth(1));
  await expect(second).toBeVisible();
  await page.keyboard.press('Tab');
  const more = chain.getByRole('button', { name: 'Rodyti dar 4' });
  await expect(more).toBeFocused();
  await expect(second).toBeHidden();
  await page.keyboard.press('Enter');
  await expect(chain.locator('.pitem')).toHaveCount(8);
  await expect(chain.locator('.pitem:visible')).toHaveCount(8);
});

test('on a 320px touch screen a tap opens one tooltip inside the viewport and a tap outside closes it', async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'its own 320px touch context; once is enough');
  const context = await browser.newContext({ viewport: { width: 320, height: 640 }, hasTouch: true, isMobile: true });
  const page = await context.newPage();
  await installFixtures(page);
  const chain = await foldFixture(page);
  const items = chain.locator('.pitem .pname');
  await expect(chain.locator('.pitem [title], .pitem[title]')).toHaveCount(0);

  const last = items.last();
  await last.tap();
  const lastTip = await tipOf(page, last);
  await expect(lastTip).toBeVisible();
  await expect(lastTip).toHaveClass(/is-open/);
  const box = await lastTip.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(320);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(640);
  await noPageOverflow(page);

  // Only one at a time: tapping another item moves the bubble.
  await items.first().tap();
  const firstTip = await tipOf(page, items.first());
  await expect(firstTip).toBeVisible();
  await expect(lastTip).toBeHidden();
  // Tapping the open item again closes it, and a tap outside closes any.
  await items.first().tap();
  await expect(firstTip).toBeHidden();
  await items.first().tap();
  await expect(firstTip).toBeVisible();
  await page.locator('#person .phead h2').tap();
  await expect(firstTip).toBeHidden();

  // With no room above, the bubble flips below its item: scrolled to sit
  // just under the sticky site header, which a tap would otherwise scroll
  // away from.
  await items.first().evaluate(el => {
    const header = document.querySelector('.site-header, header').getBoundingClientRect().bottom;
    window.scrollBy(0, el.getBoundingClientRect().top - header - 4);
  });
  await items.first().tap();
  await expect(firstTip).toHaveAttribute('data-side', 'below');
  const below = await firstTip.boundingBox();
  const item = await items.first().boundingBox();
  expect(below.y).toBeGreaterThan(item.y);
  expect(below.x + below.width).toBeLessThanOrEqual(320);
  await noPageOverflow(page);
  await context.close();
});

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

test('party switches rank the movers and the loyal, link each person and fit 320px (#199)', async ({ page }) => {
  // Synthetic shapes: a mover through six nominators (a self-nomination and
  // a committee among them, and a return), a rename plus an own-party
  // coalition that is no switch, and a single move.
  const years = [2004, 2008, 2012, 2016, 2020, 2024];
  const elections = years.map(y => ({ id: `${y}-syn`, kind: 'seimo', date: `${y}-10-10`, name: `${y} m. Seimo rinkimai`, shortName: `${y} Seimas` }));
  const parties = {
    ...index.parties,
    'syn-a': { n: 'Partija A', t: 'partija' },
    'syn-b': { n: 'Partija B', t: 'partija' },
    'syn-c': { n: 'Partija C', t: 'partija' },
    'syn-kom': { n: 'Komitetas „Mūsų kraštas“', t: 'komitetas' },
    'issikele-pats': { n: 'Išsikėlė pats', t: 'issikelimas' },
    'syn-old': { n: 'Senoji partija', t: 'partija' },
    'syn-new': { n: 'Naujoji partija', t: 'partija', pr: ['syn-old'] },
    'syn-coal': { n: 'Naujųjų koalicija', t: 'koalicija', nr: ['syn-new', 'syn-c'] },
  };
  const person = (pid, n, nominators) => ({
    pid, n, b: '1970-01-01', k: `${n.toUpperCase()}|1970-01-01`,
    e: nominators.map((p, i) => ({ id: `${years[i]}-syn`, c: pid, p, w: false })),
  });
  const synthetic = [
    person('test-kestas', 'Kęstas KEITĖJAS', ['syn-a', 'issikele-pats', 'syn-b', 'syn-kom', 'syn-a', 'syn-c']),
    person('test-lina', 'Lina LINIJA', ['syn-old', 'syn-new', 'syn-coal', 'syn-new']),
    person('test-jurgis', 'Jurgis VIENAS', ['syn-a', 'syn-b']),
  ];
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...index, elections: [...elections, ...index.elections], parties, people: [...index.people, ...synthetic] }),
  }));
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/partiju-keitimai');
  await expect(page.locator('#person h2')).toHaveText('Partijų keitimai');
  await expect(page.locator('#switchesBtn')).toHaveAttribute('aria-current', 'page');

  await expect(page.locator('.switchbar-label')).toHaveText(['nė karto', '1 kartą', '2 kartus', '3 kartus', '4 kartus', '5 kartus', '6 ir daugiau']);
  await expect(page.locator('.switchbar-count')).toHaveText(['4 (66,7 %)', '1 (16,7 %)', '0 (0,0 %)', '0 (0,0 %)', '0 (0,0 %)', '1 (16,7 %)', '0 (0,0 %)']);
  const [movers, loyal] = await page.locator('#person table.ranking').all();
  await expect(movers.locator('tbody td:nth-child(2) > a')).toHaveText(['Kęstas KEITĖJAS · 1970-01-01', 'Jurgis VIENAS · 1970-01-01']);
  await expect(movers.locator('tbody tr').first().locator('td.num')).toHaveText(['5', '4', '6']);
  await expect(loyal.locator('tbody td:nth-child(2) > a')).toHaveText(['Lina LINIJA · 1970-01-01', 'Ona NAUJOJI · 1980-01-02']);
  await expect(loyal.locator('tbody tr').first().locator('td.num')).toHaveText(['4']);
  // The header's nominator line, fold and all.
  const line = movers.locator('tbody tr').first().locator('.parties');
  await expect(line.locator('.pfold-toggle').first()).toHaveText('…');
  await line.locator('.pfold-toggle').first().click();
  await expect(line).toContainText('Komitetas „Mūsų kraštas“ 2016');
  await expect(page.locator('#person')).toContainText('išsikėlimas pačiam');
  await expect(page.locator('#person .aggnote').first()).toHaveText('Iš 6 kandidatų 2 bent kartą keitė partiją – iš viso 6 kartus.');

  // 320px: the tables scroll in their wrappers, the page never widens.
  await page.setViewportSize({ width: 320, height: 740 });
  await noPageOverflow(page);
  await expect(page.locator('#person .switches .tablewrap')).toHaveCount(2);

  await movers.locator('tbody a').first().click();
  await expect(page).toHaveURL(/\/asmuo\/kestas-keitejas-test-kestas$/);
  await expect(page.locator('#person h2')).toHaveText('Kęstas KEITĖJAS');
  await page.goBack();
  await expect(page).toHaveURL(/\/partiju-keitimai$/);
  await expect(page.locator('#person h2')).toHaveText('Partijų keitimai');
  expect(errors).toEqual([]);
});

test('a party-switch ranking shows its top 5 and a "Rodyti visus" button (#199)', async ({ page }) => {
  // Seven movers, each from Partija A to Partija B.
  const parties = { ...index.parties, 'syn-a': { n: 'Partija A', t: 'partija' }, 'syn-b': { n: 'Partija B', t: 'partija' } };
  const movers = Array.from({ length: 7 }, (_, i) => ({
    pid: `test-mover-${i}`, n: `Keitėjas NR${i}`, b: null, k: `KEITĖJAS NR${i}|`,
    e: [{ id: '2020-seimo', c: `test-mover-${i}`, p: 'syn-a' }, { id: '2024-seimo', c: `test-mover-${i}`, p: 'syn-b' }],
  }));
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...index, parties, people: [...index.people, ...movers] }),
  }));
  await page.goto('/partiju-keitimai');
  await expect(page.locator('.switches h4')).toHaveText(['Kiek kartų keitė', 'Dažniausiai keitę partiją', 'Ištikimiausi savo partijai', 'Kaip skaičiuojama']);
  const ranking = page.locator('#person table.ranking').first();
  await expect(ranking.locator('tbody tr')).toHaveCount(7);
  await expect(ranking.locator('tbody tr:visible')).toHaveCount(5);
  // The loyal list has one row, so it gets no button.
  await expect(page.locator('.switches .showall')).toHaveCount(1);
  const more = page.locator('.switches .showall');
  await expect(more).toHaveText('Rodyti visus 7');
  await expect(more).toHaveAttribute('aria-expanded', 'false');
  await more.click();
  await expect(more).toHaveAttribute('aria-expanded', 'true');
  await expect(more).toHaveText('Rodyti mažiau');
  await expect(ranking.locator('tbody tr:visible')).toHaveCount(7);
  await more.focus();
  await page.keyboard.press('Enter');
  await expect(more).toHaveAttribute('aria-expanded', 'false');
  await expect(more).toHaveText('Rodyti visus 7');
  await expect(ranking.locator('tbody tr:visible')).toHaveCount(5);
  await page.keyboard.press('Enter');
  await expect(more).toHaveAttribute('aria-expanded', 'true');
  await expect(ranking.locator('tbody tr:visible')).toHaveCount(7);
  await noPageOverflow(page);
});

test('a party-switch group under 0.1 % reads "<0,1 %", not "0,0 %" (#199)', async ({ page }) => {
  // 1,500 one-time candidates and one mover: 1 of 1,504 is 0.07 %.
  const parties = { ...index.parties, 'syn-a': { n: 'Partija A', t: 'partija' }, 'syn-b': { n: 'Partija B', t: 'partija' } };
  const many = Array.from({ length: 1500 }, (_, i) => ({
    pid: `test-many-${i}`, n: `Vardas PAVARDĖ${i}`, b: null, k: `VARDAS PAVARDĖ${i}|`,
    e: [{ id: '2024-seimo', c: `test-many-${i}`, p: 'syn-a' }],
  }));
  const mover = {
    pid: 'test-mover', n: 'Jurgis VIENAS', b: null, k: 'JURGIS VIENAS|',
    e: [{ id: '2020-seimo', c: 'test-mover', p: 'syn-a' }, { id: '2024-seimo', c: 'test-mover', p: 'syn-b' }],
  };
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...index, parties, people: [...index.people, ...many, mover] }),
  }));
  await page.goto('/partiju-keitimai');
  await expect(page.locator('.switchbar-count')).toHaveText(['1 503 (99,9 %)', '1 (<0,1 %)', '0 (0,0 %)', '0 (0,0 %)', '0 (0,0 %)', '0 (0,0 %)', '0 (0,0 %)']);
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

test('vote counts leave the card header but stay, formatted, in the card and the comparison (#204)', async ({ page }) => {
  await ready(page, JONAS);
  const card = page.locator('#person details.ecard').first();
  const summary = card.locator('summary');
  await expect(summary).toContainText('2024 m.');
  await expect(summary).not.toContainText(/pirmumo/i);
  await expect(summary).not.toContainText(/apygardoje/i);
  await expect(summary).not.toContainText(/11\s541/);
  await card.evaluate(el => { el.open = true; });
  const block = card.locator('.sec').filter({ has: page.getByRole('heading', { name: 'Kandidatavimas', exact: true }) });
  const valueOf = label => block.locator('dt', { hasText: new RegExp(`^${label}`) }).first().locator('xpath=following-sibling::dd[1]');
  await expect(block.locator('dt', { hasText: /^Pirmumo balsai$/ })).toHaveCount(1);
  await expect(valueOf('Pirmumo balsai')).toHaveText(/^11[\s  ]541$/);
  await expect(valueOf('Vienmandatės balsai').locator('dd').first()).toHaveText(/^6[\s  ]999$/);
  // Only the vote counts: a rating score keeps its digits as the record has them.
  await expect(valueOf('Reitingo balai')).toHaveText('12345');
  await page.getByRole('button', { name: 'Palyginimas tarp rinkimų', exact: true }).click();
  const rows = page.locator('#person table.cmp:visible tbody th');
  await expect(rows.filter({ hasText: /^Pirmumo balsai$/ })).toHaveCount(1);
  await expect(rows.filter({ hasText: /^Balsai apygardoje/ })).toHaveCount(1);
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

test('every summary view remains usable', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await ready(page);
  for (const [button, heading] of [
    ['aggBtn', 'Rinkimų suvestinė'],
    ['nominatorBtn', 'Iškėlėjo suvestinė'],
    ['coverageBtn', 'Ką klausė kiekvienų rinkimų anketa'],
    ['moversBtn', 'Didžiausi pokyčiai'],
    ['switchesBtn', 'Partijų keitimai'],
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
