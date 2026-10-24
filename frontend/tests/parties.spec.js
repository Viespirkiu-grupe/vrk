import { test, expect } from '@playwright/test';
import { partyOrder } from '../src/lib/parties.js';

// partyOrder (issue #212) on a synthetic parties table. Pure functions, so
// these run without a page.
const parties = {
  big: { n: 'Didžioji partija', t: 'partija' },
  merged: { n: 'Sujungtoji partija', t: 'partija', pr: ['old', 'oldkom'] },
  old: { n: 'Senoji partija', t: 'partija' },
  oldkom: { n: 'Senasis komitetas', t: 'komitetas' },
  kom: { n: 'Žalias komitetas', t: 'komitetas' },
  alpha: { n: 'Alfa partija', t: 'partija' },
  beta: { n: 'Beta partija', t: 'partija' },
  gamma: { n: 'Gama partija', t: 'partija' },
  none1: { n: '„Ąžuolo“ koalicija', t: 'koalicija' },
  none2: { n: 'Bevardžių partija', t: 'partija' },
  self: { n: 'Išsikėlė pats', t: 'issikelimas' },
  unused: { n: 'Niekieno partija', t: 'partija' },
};

// A person: their candidacies as [nominator, won]; the election is irrelevant.
const person = (...runs) => ({ e: runs.map(([p, w]) => ({ id: 'x', p, w })) });
const many = (n, ...runs) => Array.from({ length: n }, () => person(...runs));
const people = [
  ...many(3, ['big', true]),
  // Two people for the merged lineage, one of them elected under two of its
  // members and counted once.
  person(['old', true], ['merged', true], ['oldkom', true]),
  person(['merged', true]),
  // A committee with councillors ranks by its results like any party.
  ...many(4, ['kom', true]),
  // alpha and beta tie on one elected; beta fielded one more person. gamma
  // ties beta on both and loses on name.
  person(['alpha', true]),
  person(['beta', true]), person(['beta', false]),
  person(['gamma', true]), person(['gamma', false]),
  // Elected nobody: alphabetical at the bottom whatever they fielded.
  ...many(5, ['none2', false]),
  person(['none1', false]),
  // Self-nomination last, though it elected the most.
  ...many(9, ['self', true]),
];

const roots = units => units.map(u => u.root);

test('the facet orders by people elected, committees included, self-nomination last (#212)', () => {
  expect(roots(partyOrder(parties, people)))
    .toEqual(['kom', 'big', 'merged', 'beta', 'gamma', 'alpha', 'none1', 'none2', 'self']);
});

test('a lineage counts each elected person once and keeps its member order (#212)', () => {
  const merged = partyOrder(parties, people).find(u => u.root === 'merged');
  expect(merged.elected).toBe(2);
  expect(merged.ran).toBe(2);
  expect(merged.lineage).toEqual([{ id: 'merged', depth: 0 }, { id: 'old', depth: 1 }, { id: 'oldkom', depth: 1 }]);
});

test('an elected-nobody nominator sorts by name, not by the people it fielded (#212)', () => {
  const order = partyOrder(parties, people);
  const none = order.filter(u => !u.elected && u.root !== 'self');
  // „Ąžuolo“ sorts under A, past its opening quote mark, ahead of a bigger list.
  expect(roots(none)).toEqual(['none1', 'none2']);
  expect(none.map(u => u.ran)).toEqual([1, 5]);
  // A party with no candidacy here is no row.
  expect(roots(order)).not.toContain('unused');
});

test('a won candidacy under a nominator makes a person elected there, not elsewhere (#212)', () => {
  // The merged lineage stays listed with no candidacies, as the facet always
  // listed a lineage; it elected nobody and sorts by name.
  const order = partyOrder(parties, [person(['alpha', false], ['beta', true])]);
  expect(order.map(u => [u.root, u.elected, u.ran])).toEqual([['beta', 1, 1], ['alpha', 0, 1], ['merged', 0, 0]]);
});
