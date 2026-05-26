import { parseHTML } from 'linkedom';

export const STATIC_BASE = 'https://www.vrk.lt/statiniai/puslapiai';

export async function fetchDoc(path) {
  const res = await fetch(STATIC_BASE + path);
  const html = (await res.text()).replace(/data:[^"]+/g, '');
  return parseHTML(html).document;
}

export function extractId(href, pattern) {
  const match = (href || '').match(pattern);
  return match ? match[1] : null;
}

export function parseName(raw) {
  const text = raw.trim().replace(/\s+/g, ' ');
  const parts = text.split(' ');
  const lastNameIdx = parts.findIndex(p => p === p.toUpperCase() && /\p{L}/u.test(p) && p.length > 1);
  if (lastNameIdx === -1) return { firstName: parts.slice(0, -1).join(' '), lastName: parts.at(-1) };
  return {
    firstName: parts.slice(0, lastNameIdx).join(' '),
    lastName: parts.slice(lastNameIdx).join(' '),
  };
}

// Parses Seimas full candidate list. Works for both modern (#table3) and older (table.partydata) layouts.
export function parseSeimasFullList(doc) {
  const t3 = doc.querySelector('#table3.partydata');
  const table = t3 || [...doc.querySelectorAll('table.partydata')].at(-1);
  if (!table) return [];
  const rows = [...table.querySelectorAll('tr')].filter(r => r.querySelectorAll('td').length >= 5);
  return rows.flatMap(row => {
    const cells = [...row.querySelectorAll('td')];
    const nameLink = cells[0].querySelector('a');
    if (!nameLink) return [];
    const isElected = (nameLink.getAttribute('style') || '').includes('color: blue');
    const rawName = nameLink.textContent.trim().replace(/\s+/g, ' ');
    const electionTypeMatch = rawName.match(/\(([DV])\)\s*$/);
    const cleanName = rawName.replace(/\([DV]\)\s*$/, '').trim();
    const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
    const listLink = cells[1].querySelector('a');
    const listRaw = listLink?.textContent.trim().replace(/\s+/g, ' ');
    const listNumMatch = listRaw?.match(/^(\d+)\.\s+(.+)/);
    const partyList = listLink ? {
      name: listNumMatch ? listNumMatch[2] : listRaw,
      ...(listNumMatch ? { number: parseInt(listNumMatch[1]) } : {}),
      id: extractId(listLink.getAttribute('href'), /rorgId-(\d+)/),
    } : null;
    const listPosition = parseInt(cells[2].textContent.trim()) || null;
    const postElectionPosition = parseInt(cells[3].textContent.trim()) || null;
    const districtLink = cells[4].querySelector('a');
    const district = districtLink ? (() => {
      const m = districtLink.textContent.trim().match(/^(\d+)\.\s+(.+)/);
      return { id: extractId(districtLink.getAttribute('href'), /rpgId-(\d+)/), number: m ? parseInt(m[1]) : null, name: m ? m[2] : districtLink.textContent.trim() };
    })() : null;
    const nominatedByLink = cells[5]?.querySelector('a');
    const nominatedBy = nominatedByLink ? nominatedByLink.textContent.trim() : cells[5]?.textContent.trim() || null;
    const round = cells[6]?.textContent.trim().replace(/\s+/g,'') || null;
    return [{ id, ...parseName(cleanName), isElected, ...(electionTypeMatch ? { electionType: electionTypeMatch[1] } : {}), ...(partyList ? { partyList } : {}), ...(listPosition ? { listPosition } : {}), ...(postElectionPosition ? { postElectionPosition } : {}), ...(district ? { district } : {}), ...(nominatedBy ? { nominatedBy } : {}), ...(round ? { round } : {}) }];
  });
}

// Parses EP full candidate list (epKandidataiPilnasSarasas.html)
export function parseEPFullList(doc) {
  const table = doc.querySelector('#table2') || doc.querySelector('table.partydata');
  if (!table) return [];
  const rows = [...table.querySelectorAll('tr')].filter(r => r.querySelectorAll('td').length >= 4);
  return rows.flatMap(row => {
    const cells = [...row.querySelectorAll('td')];
    const nameLink = cells[0].querySelector('a');
    if (!nameLink) return [];
    const isElected = (row.getAttribute('style') || '').includes('color: blue') || (nameLink.getAttribute('style') || '').includes('color: blue');
    const rawName = nameLink.textContent.trim().replace(/\s+/g, ' ');
    const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
    const listLink = cells[1].querySelector('a');
    const listRaw = listLink?.textContent.trim().replace(/\s+/g, ' ');
    const listNumMatch = listRaw?.match(/^(\d+)\.\s+(.+)/);
    const partyList = listLink ? {
      id: extractId(listLink.getAttribute('href'), /sarasoId-(\d+)/),
      ...(listNumMatch ? { number: parseInt(listNumMatch[1]) } : {}),
      name: listNumMatch ? listNumMatch[2] : listRaw,
    } : null;
    const listPosition = parseInt(cells[2].textContent.trim()) || null;
    const postElectionPosition = parseInt(cells[3].textContent.trim()) || null;
    return [{ id, ...parseName(rawName), isElected, ...(partyList ? { partyList } : {}), ...(listPosition ? { listPosition } : {}), ...(postElectionPosition ? { postElectionPosition } : {}) }];
  });
}

// Parses the standard mayor by-election table (#table2) used across multiple elections.
// basePath: e.g. '/rinkimai/1586/rnk1906/kandidatai'
export function parseMayorTable(doc, basePath) {
  const rows = [...doc.querySelectorAll('#table2 tr:not(thead tr)')];
  const candidates = [];
  let currentMunicipality = null;

  for (const row of rows) {
    const cells = [...row.querySelectorAll('td')];
    if (cells.length < 5) continue;

    const munLink = cells[0].querySelector('a');
    if (munLink) {
      const munHref = munLink.getAttribute('href') || '';
      const munMatch = munLink.textContent.trim().match(/^(\d+)\.\s+(.+)/);
      currentMunicipality = {
        id: extractId(munHref, /rpgId-(\d+)/),
        number: munMatch ? parseInt(munMatch[1]) : null,
        name: munMatch ? munMatch[2] : munLink.textContent.trim(),
      };
    }

    const nameLink = cells[2].querySelector('a');
    if (!nameLink) continue;

    const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
    const rawName = nameLink.textContent.trim();
    const statusMatch = cells[2].textContent.trim().match(/\(([^)]+)\)/);
    const status = statusMatch ? statusMatch[1].trim() : undefined;
    const isElected = nameLink.innerHTML.includes('color="blue"') || nameLink.innerHTML.includes('color: blue');

    const round = cells[3].textContent.trim() || undefined;
    const nominatedBy = cells[4].textContent.trim() || undefined;

    candidates.push({
      id,
      ...parseName(rawName),
      municipality: currentMunicipality,
      ...(round ? { round } : {}),
      ...(nominatedBy ? { nominatedBy } : {}),
      isElected,
      ...(status ? { status } : {}),
    });
  }

  return candidates;
}

// Parses a full municipal election (council lists + mayors) given the base candidate path.
// concurrency: number of parallel requests for list pages.
export async function parseMunicipalElection(basePath, concurrency = 10) {
  async function fetchAll(tasks) {
    const results = [];
    for (let i = 0; i < tasks.length; i += concurrency) {
      const batch = await Promise.all(tasks.slice(i, i + concurrency).map(fn => fn()));
      results.push(...batch);
    }
    return results;
  }

  // Collect all list page paths from the lists overview
  const listsDoc = await fetchDoc(`${basePath}/savKandidataiSarasai.html`);
  const listRows = [...listsDoc.querySelectorAll('#table2 tr:not(thead tr)')];
  let currentMuni = null;
  const listEntries = [];

  for (const row of listRows) {
    const cells = [...row.querySelectorAll('td')];
    if (!cells.length) continue;
    const muniLink = [...cells].map(c => c.querySelector('a')).find(a => a?.getAttribute('href')?.includes('Apygardoje_rpgId') && !a.getAttribute('href').includes('TarNar'));
    if (muniLink) {
      const muniText = muniLink.textContent.trim();
      const muniMatch = muniText.match(/^(\d+)\.\s+(.+)/);
      currentMuni = { id: extractId(muniLink.getAttribute('href'), /rpgId-(\d+)/), number: muniMatch ? parseInt(muniMatch[1]) : null, name: muniMatch ? muniMatch[2] : muniText };
    }
    const listLink = [...cells].map(c => c.querySelector('a')).find(a => a?.getAttribute('href')?.includes('TarNarApygardoje'));
    if (!listLink || !currentMuni) continue;
    const listHref = listLink.getAttribute('href');
    const listNumCell = [...cells].find(c => /^\d+\s*$/.test(c.textContent.trim()));
    listEntries.push({
      municipality: currentMuni,
      partyList: { id: extractId(listHref, /rorgId-(\d+)/), number: listNumCell ? parseInt(listNumCell.textContent.trim()) : null, name: listLink.textContent.trim() },
      path: listHref.replace('?srcUrl=', ''),
    });
  }

  // Fetch each list page and extract council candidates
  const councilCandidates = (await fetchAll(listEntries.map(entry => async () => {
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
      const isMayorCandidate = /kandidat[aė][s]?\s+į\s+savivaldybės\s+merus/i.test(rawName);
      const cleanName = rawName.replace(/\s*\(kandidat[aė][s]?\s+į\s+savivaldybės\s+merus\)/i, '').trim();
      const postElectionPosition = parseInt(cells[2].textContent.trim()) || null;
      const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
      return [{ id, ...parseName(cleanName), municipality: entry.municipality, partyList: entry.partyList, ...(listPosition ? { listPosition } : {}), ...(postElectionPosition ? { postElectionPosition } : {}), isElected, isMayorCandidate }];
    });
  }))).flat();

  // Fetch mayor candidates
  const mayorDoc = await fetchDoc(`${basePath}/savKandidataiMerai.html`);
  const mayorRows = [...mayorDoc.querySelectorAll('#table2 tr:not(thead tr)')];
  let currentMayorMuni = null;
  const mayorCandidates = [];

  for (const row of mayorRows) {
    const cells = [...row.querySelectorAll('td')];
    if (cells.length < 5) continue;
    const munLink = cells[0].querySelector('a');
    if (munLink) {
      const munMatch = munLink.textContent.trim().match(/^(\d+)\.\s+(.+)/);
      currentMayorMuni = { id: extractId(munLink.getAttribute('href'), /rpgId-(\d+)/), number: munMatch ? parseInt(munMatch[1]) : null, name: munMatch ? munMatch[2] : munLink.textContent.trim() };
    }
    const nameLink = cells[2].querySelector('a');
    if (!nameLink) continue;
    const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
    const statusMatch = cells[2].textContent.trim().match(/\(([^)]+)\)/);
    const isElectedMayor = nameLink.innerHTML.includes('color="blue"') || nameLink.innerHTML.includes('color: blue');
    const nominatedByLink = cells[4].querySelector('a');
    const nominatedBy = nominatedByLink ? nominatedByLink.textContent.trim() : cells[4].textContent.trim() || undefined;
    const round = cells[3].textContent.trim() || undefined;
    mayorCandidates.push({ id, ...parseName(nameLink.textContent.trim()), municipality: currentMayorMuni, ...(round ? { round } : {}), ...(nominatedBy ? { nominatedBy } : {}), isElectedMayor, ...(statusMatch ? { status: statusMatch[1].trim() } : {}) });
  }

  return { councilCandidates, mayorCandidates };
}
