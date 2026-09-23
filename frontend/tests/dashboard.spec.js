import { test, expect } from '@playwright/test';
import { installFixtures, people } from './fixtures.js';

async function ready(page, path = '/dashboard/') {
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
  await expect(page.locator('.navbar-brand')).toHaveAttribute('href', '/dashboard/');
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

test('legacy links canonicalize and Back/Forward restore the selected person', async ({ page }) => {
  await ready(page, `/dashboard/#${encodeURIComponent(people[0].ak[0])}`);
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page).toHaveURL(/#test-anna$/);
  await expect(page.locator('#person')).toBeFocused();
  await page.locator('#results a[href="#test-jonas"]').click();
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await page.goBack();
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page).toHaveURL(/#test-anna$/);
  await page.goForward();
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await expect(page.locator('#announce')).toContainText('Jonas BANDOMASIS');
  await selectView(page, 'overviewBtn');
  await expect(page.getByRole('heading', { name: 'Kandidatai ir rinkimai', exact: true })).toBeVisible();
  await expect(page.locator('#topstats')).toContainText('3 asmenys');
  await page.locator('#results a[href="#test-jonas"]').click();
  await expect(page.locator('#person h2')).toHaveText('Jonas BANDOMASIS');
  await page.locator('.navbar-brand').click();
  await expect(page).toHaveURL(/\/dashboard\/$/);
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
  await ready(page, '/dashboard/#test-anna');
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
  await ready(page, '/dashboard/#test-anna');
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

test('failed index reports a visible error', async ({ page }) => {
  await installFixtures(page, { failedIndex: true });
  await page.goto('/dashboard/');
  await expect(page.locator('#topstats')).toContainText('indekso įkelti nepavyko');
  await expect(page.locator('#person [role="alert"]')).toContainText('Duomenų šiuo metu pasiekti nepavyko');
  await expect(page.getByRole('button', { name: 'Bandyti dar kartą' })).toBeVisible();
  await installFixtures(page);
  await page.getByRole('button', { name: 'Bandyti dar kartą' }).click();
  await expect(page.locator('#results .row')).toHaveCount(3);
});

test('a missing record warns while retaining the loaded election', async ({ page }) => {
  await installFixtures(page, { failedRecord: '/data/2020-seimo/test-anna-2020-seimo.json' });
  await ready(page, '/dashboard/#test-anna');
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
  await ready(page, '/dashboard/#test-anna');
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await page.locator('#themeToggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('#themeToggle')).toHaveAttribute('aria-pressed', 'true');
  await page.reload();
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.locator('.skip-link').focus();
  await page.locator('.skip-link').press('Enter');
  await expect(page).toHaveURL(/#test-anna$/);
  await expect(page.locator('#workspace')).toBeFocused();
  await expect(page.locator('#person h2')).toHaveText('Ona NAUJOJI');
  await selectView(page, 'overviewBtn');
  await expect(page.locator('#search')).toBeFocused();
});

test('narrow viewports contain wide financial and coverage tables', async ({ page }) => {
  test.skip(test.info().project.name !== 'phone', '320px stress check');
  await page.setViewportSize({ width: 320, height: 740 });
  await ready(page, '/dashboard/#test-anna');
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
