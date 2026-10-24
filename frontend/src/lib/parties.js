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

export { partyLineage, partyLineageRoots, partyTypeWord, partyText, partyTitle, partyCoalitions };
