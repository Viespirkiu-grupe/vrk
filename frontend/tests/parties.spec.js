import { test, expect } from '@playwright/test';
import { partyRanking } from '../src/lib/parties.js';

// partyRanking (issue #212) on a synthetic index: two general Seimas
// elections, a by-election of the newer term and a municipal election.
// Pure functions, so these run without a page.
const elections = [
  { id: '2020-seimo', kind: 'seimo', date: '2020-10-11' },
  { id: '2023-seimo-pakartotiniai', kind: 'seimo', date: '2023-09-03', parent: '2020-seimo' },
  { id: '2023-savivaldybiu', kind: 'savivaldybiu', date: '2023-03-05' },
  { id: '2024-seimo', kind: 'seimo', date: '2024-10-13' },
];

const parties = {
  big: { n: 'Didžioji partija', t: 'partija' },
  old: { n: 'Senoji partija', t: 'partija' },
  merged: { n: 'Sujungtoji partija', t: 'partija', pr: ['old', 'oldkom'] },
  oldkom: { n: 'Senasis komitetas', t: 'komitetas' },
  past: { n: 'Buvusi partija', t: 'partija' },
  alpha: { n: 'Alfa partija', t: 'partija' },
  beta: { n: 'Beta partija', t: 'partija' },
  byonly: { n: 'Papildomųjų partija', t: 'partija' },
  self: { n: 'Išsikėlė pats', t: 'issikelimas' },
  kom: { n: 'Žalias komitetas', t: 'komitetas' },
  koal: { n: '„Ąžuolo“ koalicija', t: 'koalicija', nr: ['big'] },
  unused: { n: 'Niekieno partija', t: 'partija' },
};

// One person per candidacy list; `[election, nominator, won]`.
const person = (...runs) => ({ e: runs.map(([id, p, w]) => ({ id, p, w })) });
const seats = (n, id, p) => Array.from({ length: n }, () => person([id, p, true]));
const people = [
  ...seats(3, '2024-seimo', 'big'),
  ...seats(1, '2020-seimo', 'big'),
  // The merged lineage: 2 seats in 2024 through its two members, 5 before.
  ...seats(1, '2024-seimo', 'merged'),
  ...seats(1, '2024-seimo', 'old'),
  ...seats(5, '2020-seimo', 'old'),
  // A by-election seat and a municipal one never count as Seimas seats.
  ...seats(9, '2023-seimo-pakartotiniai', 'byonly'),
  ...seats(4, '2020-seimo', 'past'),
  // alpha and beta tie on general seats (1), beta wins on elected people.
  ...seats(1, '2020-seimo', 'alpha'),
  ...seats(1, '2020-seimo', 'beta'),
  ...seats(1, '2023-savivaldybiu', 'beta'),
  person(['2024-seimo', 'alpha', false]),
  ...seats(2, '2024-seimo', 'self'),
  person(['2023-savivaldybiu', 'kom', true]),
  person(['2023-savivaldybiu', 'koal', false]),
];

const roots = units => units.map(u => u.root);

test('the current group is the latest general election, by its seats (#212)', () => {
  const r = partyRanking(parties, elections, people);
  expect(r.year).toBe(2024);
  // big 3 seats ahead of the merged lineage's 2; self-nomination's 2 never rank.
  expect(roots(r.current)).toEqual(['big', 'merged']);
  expect(r.current.map(u => u.seats)).toEqual([3, 2]);
});

test('a lineage merges its members through pr, including a committee (#212)', () => {
  const merged = partyRanking(parties, elections, people).current.find(u => u.root === 'merged');
  expect(merged.lineage).toEqual([{ id: 'merged', depth: 0 }, { id: 'old', depth: 1 }, { id: 'oldkom', depth: 1 }]);
  expect(merged.allSeats).toBe(7);
  expect(merged.elected).toBe(7);
});

test('other parties go by all-time general seats, then elected people, then name (#212)', () => {
  const r = partyRanking(parties, elections, people);
  // The by-election's nine seats are no general seats: byonly sorts behind
  // every party that won one, its nine elected people notwithstanding.
  expect(roots(r.other)).toEqual(['past', 'beta', 'alpha', 'byonly']);
  expect(r.other.find(u => u.root === 'byonly').allSeats).toBe(0);
  // A party with no candidacy here is no row.
  expect(roots(r.other)).not.toContain('unused');
});

test('committees and coalitions go alphabetically, self-nomination first (#212)', () => {
  const r = partyRanking(parties, elections, people);
  // „Ąžuolo“ sorts under A, past its opening quote mark.
  expect(roots(r.rest)).toEqual(['self', 'koal', 'kom']);
});

test('a name breaks a full tie, and no general election leaves one group of parties (#212)', () => {
  const tie = partyRanking(parties, elections, [person(['2024-seimo', 'beta', true]), person(['2024-seimo', 'alpha', true])]);
  expect(roots(tie.current)).toEqual(['alpha', 'beta']);
  const none = partyRanking(parties, elections.filter(e => e.kind !== 'seimo'), people);
  expect(none.year).toBe(null);
  expect(none.current).toEqual([]);
});
