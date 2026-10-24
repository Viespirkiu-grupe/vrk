// Entirely synthetic candidates. Only public schema and election identifiers are
// shared with the real index; no scraped personal records enter browser fixtures.
export const elections = [
  { id: '2020-seimo', kind: 'seimo', date: '2020-10-11', name: '2020 m. Lietuvos Respublikos Seimo rinkimai', shortName: '2020 Seimas' },
  { id: '2024-seimo', kind: 'seimo', date: '2024-10-13', name: '2024 m. Lietuvos Respublikos Seimo rinkimai', shortName: '2024 Seimas' },
];

export const people = [
  {
    pid: 'test-anna', n: 'Ona NAUJOJI', b: '1980-01-02', k: 'ONA NAUJOJI|1980-01-02',
    ak: ['ONA SENESNĖ|1980-01-02'],
    e: [
      { id: '2020-seimo', c: 'test-anna', p: 'test-party', w: false, sv: 0, ap: 0, tb: 0, ck: 1, ed: 1, v: 123, wp: 'Bandymų universitetas', m: [10000, 500, 20000, null] },
      { id: '2024-seimo', c: 'test-anna', p: 'test-party', w: true, sv: 0, ap: 0, ck: 0, ed: 1, v: 234, wp: 'Bandymų universitetas', m: [20000, 1000, 30000, null] },
    ],
  },
  {
    pid: 'test-jonas', n: 'Jonas BANDOMASIS', b: '1975-03-04', k: 'JONAS BANDOMASIS|1975-03-04',
    e: [{ id: '2024-seimo', c: 'test-jonas', p: 'other-party', w: false, sv: 1, ap: 1, ed: 1, v: 11541, cv: 6999, m: [1000, 0, 5000, null] }],
  },
  {
    pid: 'test-ruta', n: 'Rūta PAVYZDINĖ', b: null, k: 'RŪTA PAVYZDINĖ|',
    e: [{ id: '2020-seimo', c: 'test-ruta', p: 'other-party', sv: 1, ap: 1, tb: 1, m: [null, null, null, null] }],
  },
];

export const index = {
  stats: { persons: 3, records: 4, personsInMultipleElections: 1, corpusParsedAt: '2026-01-01T00:00:00Z' },
  elections,
  people,
  parties: { 'test-party': { n: 'Bandymų partija' }, 'other-party': { n: 'Pavyzdžių komitetas' } },
  municipalities: ['Akmenės rajono', 'Vilniaus miesto'],
  municipalityCounties: ['Šiaulių', 'Vilniaus'],
  counties: ['Vilniaus', 'Kauno', 'Klaipėdos', 'Šiaulių', 'Panevėžio', 'Marijampolės', 'Alytaus', 'Telšių', 'Utenos', 'Tauragės'],
  constituencies: ['Aukštaitijos', 'Žirmūnų'],
  nationalities: [{ label: 'lietuviai' }, { label: 'lenkai' }],
  educationLevels: [{ label: 'Aukštasis universitetinis' }],
  // A party's list campaign shared by 120 candidacies, and one candidate's own.
  campaigns: [{ k: 'dalyvis-test-shared', d: 54321.5, n: 120 }, { k: 'dalyvis-test-own', d: 1500, n: 1 }],
  coverage: {
    concepts: ['issilavinimas', 'tautybe'],
    records: { '2020-seimo': 2, '2024-seimo': 2 },
    filled: { '2020-seimo': [1, 2], '2024-seimo': [2, null] },
  },
};

export const records = Object.fromEntries(people.flatMap(person => person.e.map(e => [
  `/data/${e.id}/${e.c}-${e.id}.json`,
  {
    normalized: {
      anketa: { 'einamos-pareigos': 'Bandymų specialistas' },
      biografija: {
        tautybe: e.tb === 1 ? 'Lenkas (-ė)' : 'Lietuvis (-ė)',
        issilavinimas: { irasai: [{ issilavinimas: 'Aukštasis universitetinis', 'mokymo-istaigos-pavadinimas': 'Bandymų universitetas', specialybe: 'Informatika', 'baigimo-metai': '2005' }] },
      },
      'turto-ir-pajamu-deklaracijos': {
        'privalomas-registruoti-turtas': e.m[0], 'pinigines-lesos': e.m[1], 'gautos-pajamos': e.m[2],
      },
    },
  },
])));

// The root candidacy block of the 2000-2015 records, with its vote counts
// (issue #204): the opened card prints them in thousands, the other numbers
// verbatim.
records['/data/2024-seimo/test-jonas-2024-seimo.json'].kandidatavimas = {
  pirmumoBalsai: 11541,
  reitingoBalai: 12345,
  vienmandatesBalsai: { isViso: 6999, procentai: 8.84, vieta: 2 },
};

// Campaign participants (issue #210). Anna's 2024 card holds her party's
// shared campaign with long donation and contract lists; her 2020 card her
// own, shaped as the public build leaves it: no phones or e-mails.
const donation = i => ({ rowNumber: `${i + 1}.`, donor: `AUKOTOJAS ${i + 1}`, municipality: 'Vilniaus miesto', date: '2024-05-01', incomeSourceCode: 'FAA', amount: 100 + i, notes: null });
records['/data/2024-seimo/test-anna-2024-seimo.json'].normalized['politines-kampanijos-dalyvio-duomenys'] = [{
  statusas: 'Savarankiškas',
  'registravimo-data': '2024-03-01',
  'sprendimo-numeris': 'PK1-TEST-1',
  kontaktai: { 'telefonas-pasiteirauti': '8 500 00000', 'el-pastas': 'bandymai@example.org' },
  izdininkas: { 'vardas-pavarde': 'Pavyzdinis Iždininkas', telefonas: '8 600 00000', 'el-pastas': 'izdas@example.org', 'imones-pavadinimas': null, 'imones-kodas': null },
  auditorius: { 'vardas-pavarde': null, telefonas: null, 'el-pastas': null, 'imones-pavadinimas': 'UAB Bandymų auditas', 'imones-kodas': '123456789' },
  'aukos-pagal-sekcija': {
    'gautos-ir-priimtos-aukos': {
      title: 'Gautos ir priimtos aukos',
      records: Array.from({ length: 45 }, (_, i) => donation(i)),
      totals: { 'is-viso': 54321.5, 'fiziniu-asmenu': 4321.5 },
    },
    'nepriimtos-aukos': { title: 'Nepriimtos aukos', records: [donation(99)], totals: { 'is-viso': 199 } },
  },
  'finansavimo-ataskaitos': [
    { rowNumber: '1.', approvedDate: '2024-11-01', status: 'Pateikta', reportUrls: ['https://example.org/ataskaitos/ataskaita.pdf'] },
  ],
  sutartys: Array.from({ length: 30 }, (_, i) => ({ rowNumber: `${i + 1}.`, counterparty: `UAB Tiekėjas ${i + 1}`, agreementDate: '2024-04-01', agreementNumber: String(i + 1), subject: 'Reklama', textUrls: [] })),
  sprendimai: [],
}];
records['/data/2020-seimo/test-anna-2020-seimo.json'].normalized['politines-kampanijos-dalyvio-duomenys'] = [{
  statusas: 'Atstovaujamasis',
  'registravimo-data': null,
  'sprendimo-numeris': null,
  kontaktai: {},
  izdininkas: { 'vardas-pavarde': null, 'imones-pavadinimas': null, 'imones-kodas': null },
  auditorius: { 'vardas-pavarde': null, 'imones-pavadinimas': null, 'imones-kodas': null },
  'aukos-pagal-sekcija': {},
  'finansavimo-ataskaitos': [],
  sutartys: [],
  sprendimai: [],
  atstovauja: { pavadinimas: 'PAVYZDINĖ ILGO PAVADINIMO POLITINĖ ORGANIZACIJA', nuoroda: 'https://example.org/ataskaitos/2024/politines-kampanijos-dalyvio-duomenys/ilga-saltinio-nuoroda' },
}];

// The general rule (issue #210): a one-row list whose cells nest is a
// record, two rows of anything stay a table.
Object.assign(records['/data/2024-seimo/test-jonas-2024-seimo.json'].normalized.anketa, {
  'teistumo-detales': { irasai: [{ 'nuosprendzio-data': '2013-03-06', 'nusikalstamos-veikos': [{ sunkumas: 'Nesunkus', 'kaltes-forma': 'Tyčinis' }] }] },
  'ankstesnes-pareigos': [
    { pareigos: 'Mokytojas', laikotarpis: { nuo: '2001', iki: '2005' } },
    { pareigos: 'Direktorius', laikotarpis: { nuo: '2005', iki: '2020' } },
  ],
});

// A 1×1 PNG, enough for the portrait loader to decode.
const PIXEL = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64');

// `portraits` maps a pid to its web portrait's HTTP status: the person gains
// `ph: 1`, the index the portrait set's version, and portraits/<pid>.webp
// answers, after `photoDelay` ms, with the pixel or an empty 404.
// `recordPhotos` gives every record an archive sidecar path, which the page
// must not request (issue #187).
export async function installFixtures(page, { failedRecord, failedIndex = false, portraits = {}, photoDelay = 0, recordPhotos = false } = {}) {
  const served = {
    ...index,
    people: people.map(p => (p.pid in portraits ? { ...p, ph: 1 } : p)),
    ...(Object.keys(portraits).length ? { portraits: { v: 'test1', n: Object.keys(portraits).length } } : {}),
  };
  // UI assets, the real concept map and field labels still pass through the
  // production preview server, so missing bundles / bad base URLs fail the suite.
  await page.route(url => url.pathname === '/people.json', route => route.fulfill({
    status: failedIndex ? 503 : 200,
    contentType: 'application/json',
    body: JSON.stringify(failedIndex ? { error: 'fixture unavailable' } : served),
  }));
  await page.route('**/data/**/*.json', route => {
    const path = new URL(route.request().url()).pathname;
    let record = records[path];
    if (record && recordPhotos) {
      const file = path.split('/').pop().replace(/\.json$/, '.jpg');
      record = { ...record, rawData: { profile: { photoSrc: `photos/${file}` } } };
    }
    return route.fulfill({
      status: path === failedRecord ? 503 : record ? 200 : 404,
      contentType: 'application/json',
      body: JSON.stringify(record || { error: 'unknown fixture' }),
    });
  });
  await page.route('**/portraits/*', async route => {
    const pid = new URL(route.request().url()).pathname.split('/').pop().replace(/\.webp$/, '');
    await new Promise(resolve => setTimeout(resolve, photoDelay));
    return portraits[pid] === 200
      ? route.fulfill({ status: 200, contentType: 'image/png', body: PIXEL })
      : route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' });
  });
}
