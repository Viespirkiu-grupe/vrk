// A person's nominators in time order (issue #195): one run per stretch of
// consecutive candidacies under the same nominator, so a return to an earlier
// one reads as a return, not as a single first appearance.

// An election's year: its date's, else the id's YYYY prefix.
function electionYear(election, id) {
  const m = /^(\d{4})/.exec((election && election.date) || id || "");
  return m ? Number(m[1]) : null;
}

// [{id, from, to, elections}] over `candidacies` ({id: election id, p: nominator id}),
// ordered by `elections` (the index's chronological list) rather than by the
// candidacies' own order; the sort is stable, so same-election candidacies
// keep theirs. An election the list lacks sorts last. Candidacies with no
// nominator are skipped and do not break a run. `elections` lists the run's
// election ids once each, in order, for the item's tooltip (issue #200).
function nominatorRuns(candidacies, elections) {
  const byId = new Map(elections.map((e, i) => [e.id, [i, e]]));
  const at = c => (byId.has(c.id) ? byId.get(c.id)[0] : elections.length);
  const runs = [];
  for (const c of [...candidacies].sort((a, b) => at(a) - at(b))) {
    if (!c.p) continue;
    const year = electionYear(byId.has(c.id) ? byId.get(c.id)[1] : null, c.id);
    const last = runs[runs.length - 1];
    if (last && last.id === c.p) {
      if (!last.elections.includes(c.id)) last.elections.push(c.id);
      if (year !== null) {
        last.from = last.from === null ? year : Math.min(last.from, year);
        last.to = last.to === null ? year : Math.max(last.to, year);
      }
    } else {
      runs.push({ id: c.p, from: year, to: year, elections: [c.id] });
    }
  }
  return runs;
}

// "1996" for a one-year run, "1996–1997" for a longer one, "" with no year.
function runYears(run) {
  if (run.from === null) return "";
  return run.from === run.to ? String(run.from) : `${run.from}–${run.to}`;
}

// The elections a run covers, in a tooltip's one line (issue #200): grouped
// by kind in first-seen order, each with its years once --
// "Seimas 1996, 2000 · Savivaldybės 1997". `byId` maps an election id to its
// index entry; an unknown kind is shown as it is.
const ELECTION_KINDS = { seimo: "Seimas", savivaldybiu: "Savivaldybės", mero: "Merai", prezidento: "Prezidentas", ep: "EP" };

function electionKinds(ids, byId) {
  const groups = new Map();
  for (const id of ids) {
    const election = byId.get(id);
    const kind = (election && (ELECTION_KINDS[election.kind] || election.kind)) || "";
    const year = electionYear(election, id);
    if (!groups.has(kind)) groups.set(kind, []);
    if (year !== null && !groups.get(kind).includes(year)) groups.get(kind).push(year);
  }
  return [...groups].map(([kind, years]) => `${kind} ${years.join(", ")}`.trim()).filter(Boolean).join(" · ");
}

// A long line folds its middle (issue #198): more than COLLAPSE_OVER items
// show the first and last COLLAPSE_KEEP -- where someone started and where
// they are now -- around a button for the rest.
const COLLAPSE_OVER = 5;
const COLLAPSE_KEEP = 2;

// {head, hidden, tail} over `items`; a short line is all head.
function collapseRuns(items, over = COLLAPSE_OVER, keep = COLLAPSE_KEEP) {
  if (items.length <= over) return { head: [...items], hidden: [], tail: [] };
  return { head: items.slice(0, keep), hidden: items.slice(keep, -keep), tail: items.slice(-keep) };
}

// Party switches (issue #199). Raw changes in the nominator line overcount:
// 18,892 of them in the corpus, 11,429 real moves between organisations.
// Not a switch: (a) a rename or merger -- entries linked by the registry's
// predecessors (`pr`, issue #123) are one organisation, by union-find over
// the links, so a merger joins both of its parents' lines; (b) a coalition
// whose members (`nr`, issue #189) include the organisation on the other
// side of the move; (c) a candidacy with no nominator, which is skipped.
// A move to or from an electoral committee does count (Dan, 2026-10-24).

// Entry id -> its organisation, the root of its lineage component.
function organisationRoots(parties) {
  const up = new Map(Object.keys(parties).map(id => [id, id]));
  const find = id => {
    if (!up.has(id)) up.set(id, id);
    while (up.get(id) !== id) { up.set(id, up.get(up.get(id))); id = up.get(id); }
    return id;
  };
  for (const [id, party] of Object.entries(parties)) {
    for (const pred of party.pr || []) {
      const a = find(id), b = find(pred);
      if (a !== b) up.set(a, b);
    }
  }
  return new Map([...up.keys()].map(id => [id, find(id)]));
}

// {switches, organisations, elections} for one person's candidacies, in the
// chronological order nominatorRuns gives them. `organisations` counts the
// distinct ones (a coalition is its own), leaving out self-nomination, which
// is no organisation -- though a move to or from it is still a switch.
// `elections` counts the candidacies with a nominator. Pass `roots` from
// organisationRoots to rank many people without rebuilding it each time.
function partySwitches(candidacies, elections, parties, roots = organisationRoots(parties)) {
  const org = id => roots.get(id) || id;
  const covers = (coalition, other) =>
    ((parties[coalition] && parties[coalition].nr) || []).some(m => org(m) === org(other));
  const runs = nominatorRuns(candidacies, elections);
  let switches = 0;
  for (let i = 1; i < runs.length; i++) {
    const from = runs[i - 1].id, to = runs[i].id;
    if (org(from) === org(to) || covers(to, from) || covers(from, to)) continue;
    switches += 1;
  }
  const own = runs.filter(r => !(parties[r.id] && parties[r.id].t === "issikelimas"));
  return {
    switches,
    organisations: new Set(own.map(r => org(r.id))).size,
    elections: candidacies.filter(c => c.p).length,
  };
}

export { COLLAPSE_OVER, COLLAPSE_KEEP, electionYear, electionKinds, nominatorRuns, runYears, collapseRuns, organisationRoots, partySwitches };
