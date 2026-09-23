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
      { id: '2020-seimo', c: 'test-anna', p: 'test-party', w: false, sv: 0, ap: 0, tb: 0, ed: 1, v: 123, wp: 'Bandymų universitetas', m: [10000, 500, 20000, null] },
      { id: '2024-seimo', c: 'test-anna', p: 'test-party', w: true, sv: 0, ap: 0, ed: 1, v: 234, wp: 'Bandymų universitetas', m: [20000, 1000, 30000, null] },
    ],
  },
  {
    pid: 'test-jonas', n: 'Jonas BANDOMASIS', b: '1975-03-04', k: 'JONAS BANDOMASIS|1975-03-04',
    e: [{ id: '2024-seimo', c: 'test-jonas', p: 'other-party', w: false, sv: 1, ap: 1, ed: 1, v: 12, m: [1000, 0, 5000, null] }],
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
  constituencies: ['Aukštaitijos', 'Žirmūnų'],
  nationalities: [{ label: 'lietuviai' }, { label: 'lenkai' }],
  educationLevels: [{ label: 'Aukštasis universitetinis' }],
  campaigns: [],
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

// A wide campaign table with nested details reproduces the crowded real schema.
records['/data/2024-seimo/test-anna-2024-seimo.json'].normalized['politines-kampanijos-dalyvio-duomenys'] = [{
  statusas: 'Atstovaujamasis',
  'registravimo-data': null,
  'sprendimo-numeris': null,
  kontaktai: { 'telefonas-pasiteirauti': '8 500 00000', 'el-pastas': 'bandymai@example.org' },
  izdininkas: { 'vardas-pavarde': 'Pavyzdinis Iždininkas', telefonas: null, 'el-pastas': null, 'imones-pavadinimas': null, 'imones-kodas': null },
  auditorius: { 'vardas-pavarde': null, telefonas: null, 'el-pastas': null, 'imones-pavadinimas': null, 'imones-kodas': null },
  'aukos-pagal-sekcija': {},
  'finansavimo-ataskaitos': [],
  sutartys: [],
  sprendimai: [],
  atstovauja: { pavadinimas: 'PAVYZDINĖ ILGO PAVADINIMO POLITINĖ ORGANIZACIJA', nuoroda: 'https://example.org/ataskaitos/2024/politines-kampanijos-dalyvio-duomenys/ilga-saltinio-nuoroda' },
}];

export async function installFixtures(page, { failedRecord, failedIndex = false } = {}) {
  // UI assets, the real concept map and field labels still pass through the
  // production preview server, so missing bundles / bad base URLs fail the suite.
  await page.route('**/dashboard/people.json', route => route.fulfill({
    status: failedIndex ? 503 : 200,
    contentType: 'application/json',
    body: JSON.stringify(failedIndex ? { error: 'fixture unavailable' } : index),
  }));
  await page.route('**/data/**/*.json', route => {
    const path = new URL(route.request().url()).pathname;
    const record = records[path];
    return route.fulfill({
      status: path === failedRecord ? 503 : record ? 200 : 404,
      contentType: 'application/json',
      body: JSON.stringify(record || { error: 'unknown fixture' }),
    });
  });
}
