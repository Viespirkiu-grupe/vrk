// Party predecessor traversal, preserving registry order and avoiding cycles.

// The entry and everything it continues, depth-first in registry order, as
// [{id, depth}] over the ids the index carries -- a predecessor a subset
// build lacks is skipped, not invented.
function partyLineage(parties, id) {
  const out = [];
  const seen = new Set();
  const walk = (pid, depth) => {
    if (seen.has(pid) || !parties[pid]) return;
    seen.add(pid);
    out.push({ id: pid, depth });
    for (const pred of parties[pid].pr || []) walk(pred, depth + 1);
  };
  walk(id, 0);
  return out;
}

// The lineage roots: entries with predecessors that no other entry lists as
// one. Each becomes a group in the party facet.
function partyLineageRoots(parties) {
  const listed = new Set();
  for (const party of Object.values(parties)) for (const pred of party.pr || []) listed.add(pred);
  return Object.keys(parties).filter(id => (parties[id].pr || []).length && !listed.has(id));
}

// Nominator labels (issue #189). people.json's "n" is already short -- a
// shortName, a joint list's member labels ("LLRA-KŠS + Rusų aljansas"), a
// coalition's quoted brand -- and "f" the full legal name where "n" is not
// it. A coalition always reads as one: "koalicija" goes before every
// label that does not already say so, since a brand alone could be a
// committee or a party.
function partyTypeWord(party) {
  return party && party.t === "koalicija" && !/koalicij/i.test(party.n || "") ? "koalicija" : "";
}

// The label as plain text, type word included, for option rows and lists.
function partyText(parties, id) {
  const party = parties[id];
  if (!party) return id;
  const word = partyTypeWord(party);
  return word ? `${word} ${party.n}` : party.n;
}

// The hover text: the full legal name, so a short form is never a dead end.
function partyTitle(parties, id) {
  const party = parties[id];
  return party ? party.f || party.n : id;
}

// Member id -> the coalitions that list it in "nr", for the party facet's
// "su koalicijomis" row. The coalitions stay their own nominators; this only
// lets one row find the joint lists a party also ran on.
function partyCoalitions(parties) {
  const out = new Map();
  for (const [id, party] of Object.entries(parties)) {
    for (const member of party.nr || []) {
      if (!parties[member]) continue;
      if (!out.has(member)) out.set(member, []);
      out.get(member).push(id);
    }
  }
  return out;
}

// The party facet's order (issue #212): by Seimas seats, not by size, so
// the list opens with the parties in the Seimas now and re-sorts itself
// after the next election. A lineage (#123) is one unit -- its root with
// everything it continues, or a lone nominator -- and its seats are the
// won candidacies (`w === true`) of any member in a general Seimas
// election: `kind` "seimo" and no `parent` (#122), so a by-election's seat
// fill counts for nobody. Three groups:
//   current -- lineages that won seats in the latest general election, by
//              those seats, then all-time seats, elected people, name;
//   other   -- every other `partija` lineage, by all-time general seats,
//              then people elected in any election, then name;
//   rest    -- committees, coalitions and self-nomination, alphabetical,
//              "Išsikėlė pats" first: the one row that is no organisation,
//              and the largest, opens the group rather than hiding under I.
// `people` is the index's people ([{e: [{id, p, w}]}]); a lone nominator
// with no candidacy is left out, a lineage of two or more always kept, as
// the facet always listed it. Each unit is {root, lineage: [{id, depth}],
// seats, allSeats, elected}; `year` is the latest general election's.
function partyRanking(parties, elections, people) {
  const general = elections.filter(e => e.kind === "seimo" && !e.parent);
  const latest = general.reduce((best, e) => (!best || (e.date || e.id) > (best.date || best.id) ? e : best), null);
  const generalIds = new Set(general.map(e => e.id));
  const rootOf = new Map();
  const units = [];
  for (const root of partyLineageRoots(parties)) {
    const lineage = partyLineage(parties, root);
    if (lineage.length < 2) continue;
    for (const { id } of lineage) rootOf.set(id, root);
    units.push({ root, lineage });
  }
  const used = new Set();
  for (const p of people) for (const e of p.e) if (e.p) used.add(e.p);
  for (const id of used) if (!rootOf.has(id)) { rootOf.set(id, id); units.push({ root: id, lineage: [{ id, depth: 0 }] }); }
  const byRoot = new Map(units.map(u => [u.root, Object.assign(u, { seats: 0, allSeats: 0, elected: 0 })]));
  for (const p of people) {
    const electedIn = new Set();
    for (const e of p.e) {
      if (!e.p || e.w !== true) continue;
      const unit = byRoot.get(rootOf.get(e.p));
      electedIn.add(unit);
      if (generalIds.has(e.id)) unit.allSeats++;
      if (latest && e.id === latest.id) unit.seats++;
    }
    for (const unit of electedIn) unit.elected++;
  }
  const type = u => (parties[u.root] || {}).t;
  const name = u => ((parties[u.root] || {}).n || u.root).replace(/^[^\p{L}\p{N}]+/u, "");
  const byName = (a, b) => name(a).localeCompare(name(b), "lt") || a.root.localeCompare(b.root);
  const byHistory = (a, b) => b.allSeats - a.allSeats || b.elected - a.elected || byName(a, b);
  const current = units.filter(u => u.seats && type(u) !== "issikelimas")
    .sort((a, b) => b.seats - a.seats || byHistory(a, b));
  const other = units.filter(u => !u.seats && type(u) === "partija").sort(byHistory);
  const rest = units.filter(u => !current.includes(u) && !other.includes(u))
    .sort((a, b) => (type(b) === "issikelimas") - (type(a) === "issikelimas") || byName(a, b));
  const year = latest ? Number(/^(\d{4})/.exec(latest.date || latest.id)?.[1]) || null : null;
  return { year, current, other, rest };
}

export { partyLineage, partyLineageRoots, partyTypeWord, partyText, partyTitle, partyCoalitions, partyRanking };
