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
// `start`: the label opens its own line, cell or option, so the type word is
// capitalised ("Koalicija …"); inside a sentence or the nominator line it
// stays lower case.
function partyText(parties, id, { start = false } = {}) {
  const party = parties[id];
  if (!party) return id;
  const word = partyTypeWord(party);
  if (!word) return party.n;
  return `${start ? word.charAt(0).toUpperCase() + word.slice(1) : word} ${party.n}`;
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

// The party facet's order (issue #212): by the people a nominator got
// elected, not by the people it fielded, so the list opens with the
// organisations that won rather than the ones that ran the most. A lineage
// (#123) is one unit -- its root with everything it continues, or a lone
// nominator -- and `elected` counts each person once per unit when any of
// their candidacies under a member won (`w === true`), in any election of
// any kind, by-elections included; `ran` counts the people who ran for it.
// Largest `elected` first, then `ran`, then name; units that elected
// nobody follow by name alone, and self-nomination ("Išsikėlė pats", no
// organisation) comes last. Members keep their lineage order. `people` is
// the index's people ([{e: [{p, w}]}]); a lone nominator with no candidacy
// is left out, a lineage of two or more always kept, as the facet always
// listed it. Each unit is {root, lineage: [{id, depth}], elected, ran}.
function partyOrder(parties, people) {
  const rootOf = new Map();
  const units = [];
  for (const root of partyLineageRoots(parties)) {
    const lineage = partyLineage(parties, root);
    if (lineage.length < 2) continue;
    for (const { id } of lineage) rootOf.set(id, root);
    units.push({ root, lineage, elected: 0, ran: 0 });
  }
  const used = new Set();
  for (const p of people) for (const e of p.e) if (e.p) used.add(e.p);
  for (const id of used) if (!rootOf.has(id)) { rootOf.set(id, id); units.push({ root: id, lineage: [{ id, depth: 0 }], elected: 0, ran: 0 }); }
  const byRoot = new Map(units.map(u => [u.root, u]));
  for (const p of people) {
    const ran = new Set();
    const won = new Set();
    for (const e of p.e) {
      if (!e.p) continue;
      const unit = byRoot.get(rootOf.get(e.p));
      ran.add(unit);
      if (e.w === true) won.add(unit);
    }
    for (const unit of ran) unit.ran++;
    for (const unit of won) unit.elected++;
  }
  const self = u => ((parties[u.root] || {}).t === "issikelimas" ? 1 : 0);
  const name = u => ((parties[u.root] || {}).n || u.root).replace(/^[^\p{L}\p{N}]+/u, "");
  return units.sort((a, b) => self(a) - self(b)
    || b.elected - a.elected
    || (a.elected ? b.ran - a.ran : 0)
    || name(a).localeCompare(name(b), "lt") || a.root.localeCompare(b.root));
}

export { partyLineage, partyLineageRoots, partyTypeWord, partyText, partyTitle, partyCoalitions, partyOrder };
