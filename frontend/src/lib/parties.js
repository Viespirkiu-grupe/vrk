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

export { partyLineage, partyLineageRoots };
