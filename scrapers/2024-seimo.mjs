import { parseHTML } from 'linkedom';

const STATIC_BASE = 'https://www.vrk.lt/statiniai/puslapiai';

async function fetchDoc(path) {
  const res = await fetch(STATIC_BASE + path);
  const html = await res.text();
  return parseHTML(html).document;
}

function parseName(raw) {
  // Strip election type suffix: (D) = daugiamandatė, (V) = vienmandatė
  const electionTypeMatch = raw.match(/\(([DV])\)\s*$/);
  const electionType = electionTypeMatch ? electionTypeMatch[1] : null;
  const text = raw.replace(/\([DV]\)\s*$/, '').replace(/\(.*?\)/g, '').trim();
  const parts = text.split(/\s+/);
  const lastNameIdx = parts.findIndex(p => p === p.toUpperCase() && p.length > 1);
  if (lastNameIdx === -1) return { firstName: parts.slice(0, -1).join(' '), lastName: parts.at(-1), electionType };
  return {
    firstName: parts.slice(0, lastNameIdx).join(' '),
    lastName: parts.slice(lastNameIdx).join(' '),
    electionType,
  };
}

function extractId(href, pattern) {
  const match = (href || '').match(pattern);
  return match ? match[1] : null;
}

const doc = await fetchDoc('/rinkimai/1544/rnk1870/kandidatai/SeiKandidataiPilnasSarasas.html');
const rows = [...doc.querySelectorAll('#table3 tr:not(thead tr)')];

const candidates = rows.flatMap(row => {
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 7) return [];

  const nameLink = cells[0].querySelector('a');
  if (!nameLink) return [];

  const isElected = (nameLink.getAttribute('style') || '').includes('color: blue');
  const rawName = nameLink.textContent.trim();
  const { firstName, lastName, electionType } = parseName(rawName);
  const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);

  const listLink = cells[1].querySelector('a');
  const partyList = listLink ? {
    name: listLink.textContent.trim(),
    id: extractId(listLink.getAttribute('href'), /rorgId-(\d+)/),
  } : null;

  const listPosition = cells[2].textContent.trim() || null;
  const postElectionPosition = cells[3].textContent.trim() || null;

  const districtLink = cells[4].querySelector('a');
  const district = districtLink ? (() => {
    const m = districtLink.textContent.trim().match(/^(\d+)\.\s+(.+)/);
    return {
      id: extractId(districtLink.getAttribute('href'), /rpgId-(\d+)/),
      number: m ? parseInt(m[1]) : null,
      name: m ? m[2] : districtLink.textContent.trim(),
    };
  })() : null;

  const nominatedByLink = cells[5].querySelector('a');
  const nominatedBy = nominatedByLink
    ? nominatedByLink.textContent.trim()
    : cells[5].textContent.trim() || null;

  const round = cells[6].textContent.trim() || null;

  return [{
    id,
    firstName,
    lastName,
    isElected,
    ...(electionType ? { electionType } : {}),
    ...(partyList ? { partyList } : {}),
    ...(listPosition ? { listPosition: parseInt(listPosition) } : {}),
    ...(postElectionPosition ? { postElectionPosition: parseInt(postElectionPosition) } : {}),
    ...(district ? { district } : {}),
    ...(nominatedBy ? { nominatedBy } : {}),
    ...(round ? { round } : {}),
  }];
});

console.log(JSON.stringify(candidates, null, 2));
