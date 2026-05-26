import { parseHTML } from 'linkedom';
import { fetchDoc, extractId, parseName } from './_utils.mjs';

const BASE_PATH = '/rinkimai/1304/rnk1630/kandidatai';

// Concurrency-limited fetch helper
async function fetchAll(tasks, concurrency = 10) {
  const results = [];
  for (let i = 0; i < tasks.length; i += concurrency) {
    const batch = await Promise.all(tasks.slice(i, i + concurrency).map(fn => fn()));
    results.push(...batch);
  }
  return results;
}

// --- Step 1: Collect all list URLs from the lists overview ---
const listsDoc = await fetchDoc(`${BASE_PATH}/savKandidataiSarasai.html`);

// Each row in table2 represents one party list in one municipality
const listRows = [...listsDoc.querySelectorAll('#table2 tr:not(thead tr)')];
let currentMuni = null;

const listEntries = [];
for (const row of listRows) {
  const cells = [...row.querySelectorAll('td')];
  if (!cells.length) continue;

  // Municipality column is in the first cell of a municipality group row
  const muniLink = cells[0]?.querySelector('a[href*="Apygardoje_rpgId"]');
  if (muniLink && !muniLink.getAttribute('href').includes('TarNar')) {
    const muniText = muniLink.textContent.trim();
    const muniMatch = muniText.match(/^(\d+)\.\s+(.+)/);
    currentMuni = {
      id: extractId(muniLink.getAttribute('href'), /rpgId-(\d+)/),
      number: muniMatch ? parseInt(muniMatch[1]) : null,
      name: muniMatch ? muniMatch[2] : muniText,
    };
  }

  const listLink = cells.find(c => c.querySelector('a[href*="TarNarApygardoje"]'))?.querySelector('a');
  if (!listLink || !currentMuni) continue;

  const listHref = listLink.getAttribute('href');
  const listNumCell = cells.find(c => c.textContent.trim().match(/^\d+\s*$/));
  const listNum = listNumCell ? parseInt(listNumCell.textContent.trim()) : null;

  listEntries.push({
    municipality: currentMuni,
    partyList: {
      id: extractId(listHref, /rorgId-(\d+)/),
      number: listNum,
      name: listLink.textContent.trim(),
    },
    path: listHref.replace('?srcUrl=', ''),
  });
}

// --- Step 2: Fetch each list page and extract candidates ---
const councilCandidates = (await fetchAll(
  listEntries.map(entry => async () => {
    const doc = await fetchDoc(entry.path);
    const rows = [...doc.querySelectorAll('#table3 tr:not(thead tr)')];
    return rows.flatMap(row => {
      const cells = [...row.querySelectorAll('td')];
      if (cells.length < 3) return [];
      const listPosition = parseInt(cells[0].textContent.trim()) || null;
      const nameLink = cells[1].querySelector('a');
      if (!nameLink) return [];
      const isElected = nameLink.innerHTML.includes('color="blue"') || nameLink.innerHTML.includes('color: blue');
      const rawName = nameLink.textContent.trim().replace(/\s+/g, ' ');
      const isMayorCandidate = rawName.includes('kandidatas į savivaldybės merus') || rawName.includes('kandidatė į savivaldybės merus');
      const cleanName = rawName.replace(/\s*\(kandidat[aė][s]?\s+į\s+savivaldybės\s+merus\)/i, '').trim();
      const postElectionPosition = parseInt(cells[2].textContent.trim()) || null;
      const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
      return [{
        id,
        ...parseName(cleanName),
        municipality: entry.municipality,
        partyList: entry.partyList,
        ...(listPosition ? { listPosition } : {}),
        ...(postElectionPosition ? { postElectionPosition } : {}),
        isElected,
        isMayorCandidate,
      }];
    });
  }),
  10
)).flat();

// --- Step 3: Mayor candidates (round/elected info from the mayors page) ---
const mayorDoc = await fetchDoc(`${BASE_PATH}/savKandidataiMerai.html`);
const mayorRows = [...mayorDoc.querySelectorAll('#table2 tr:not(thead tr)')];
let currentMayorMuni = null;
const mayorCandidates = [];

for (const row of mayorRows) {
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 5) continue;

  const munLink = cells[0].querySelector('a');
  if (munLink) {
    const munMatch = munLink.textContent.trim().match(/^(\d+)\.\s+(.+)/);
    currentMayorMuni = {
      id: extractId(munLink.getAttribute('href'), /rpgId-(\d+)/),
      number: munMatch ? parseInt(munMatch[1]) : null,
      name: munMatch ? munMatch[2] : munLink.textContent.trim(),
    };
  }

  const nameLink = cells[2].querySelector('a');
  if (!nameLink) continue;

  const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
  const rawName = nameLink.textContent.trim();
  const statusMatch = cells[2].textContent.trim().match(/\(([^)]+)\)/);
  const isElectedMayor = nameLink.innerHTML.includes('color="blue"') || nameLink.innerHTML.includes('color: blue');
  const nominatedBy = cells[4].querySelector('a')?.textContent.trim() || cells[4].textContent.trim() || undefined;
  const round = cells[3].textContent.trim() || undefined;

  mayorCandidates.push({
    id,
    ...parseName(rawName),
    municipality: currentMayorMuni,
    ...(round ? { round } : {}),
    ...(nominatedBy ? { nominatedBy } : {}),
    isElectedMayor,
    ...(statusMatch ? { status: statusMatch[1].trim() } : {}),
  });
}

console.log(JSON.stringify({ councilCandidates, mayorCandidates }, null, 2));
