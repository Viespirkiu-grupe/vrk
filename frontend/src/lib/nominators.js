// A person's nominators in time order (issue #195): one run per stretch of
// consecutive candidacies under the same nominator, so a return to an earlier
// one reads as a return, not as a single first appearance.

// An election's year: its date's, else the id's YYYY prefix.
function electionYear(election, id) {
  const m = /^(\d{4})/.exec((election && election.date) || id || "");
  return m ? Number(m[1]) : null;
}

// [{id, from, to}] over `candidacies` ({id: election id, p: nominator id}),
// ordered by `elections` (the index's chronological list) rather than by the
// candidacies' own order; the sort is stable, so same-election candidacies
// keep theirs. An election the list lacks sorts last. Candidacies with no
// nominator are skipped and do not break a run.
function nominatorRuns(candidacies, elections) {
  const byId = new Map(elections.map((e, i) => [e.id, [i, e]]));
  const at = c => (byId.has(c.id) ? byId.get(c.id)[0] : elections.length);
  const runs = [];
  for (const c of [...candidacies].sort((a, b) => at(a) - at(b))) {
    if (!c.p) continue;
    const year = electionYear(byId.has(c.id) ? byId.get(c.id)[1] : null, c.id);
    const last = runs[runs.length - 1];
    if (last && last.id === c.p) {
      if (year !== null) {
        last.from = last.from === null ? year : Math.min(last.from, year);
        last.to = last.to === null ? year : Math.max(last.to, year);
      }
    } else {
      runs.push({ id: c.p, from: year, to: year });
    }
  }
  return runs;
}

// "1996" for a one-year run, "1996–1997" for a longer one, "" with no year.
function runYears(run) {
  if (run.from === null) return "";
  return run.from === run.to ? String(run.from) : `${run.from}–${run.to}`;
}

export { electionYear, nominatorRuns, runYears };
