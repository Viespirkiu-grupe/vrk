import { parseHTML } from 'linkedom';

const STATIC_BASE = 'https://www.vrk.lt/statiniai/puslapiai';

async function fetchDoc(path) {
  const res = await fetch(STATIC_BASE + path);
  const html = await res.text();
  return parseHTML(html).document;
}

function parseName(raw) {
  const text = raw.replace(/\(.*?\)/g, '').trim();
  const parts = text.split(/\s+/);
  const lastNameIdx = parts.findIndex(p => p === p.toUpperCase() && p.length > 1);
  if (lastNameIdx === -1) return { firstName: parts.slice(0, -1).join(' '), lastName: parts.at(-1) };
  return {
    firstName: parts.slice(0, lastNameIdx).join(' '),
    lastName: parts.slice(lastNameIdx).join(' '),
  };
}

function parseStatus(raw) {
  const match = raw.match(/\(([^)]+)\)/);
  return match ? match[1].trim() : null;
}

const doc = await fetchDoc('/rinkimai/1586/rnk1906/kandidatai/savKandidataiMerai.html');
const rows = [...doc.querySelectorAll('#table2 tbody tr, #table2 tr:not(thead tr)')];

const candidates = [];
let currentMunicipality = null;

for (const row of rows) {
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 5) continue;

  const munCell = cells[0];
  const munLink = munCell.querySelector('a');
  if (munLink) {
    const munHref = munLink.getAttribute('href') || '';
    const munMatch = munHref.match(/rpgId-(\d+)/);
    const munText = munLink.textContent.trim();
    const munNumMatch = munText.match(/^(\d+)\.\s+(.+)/);
    currentMunicipality = {
      id: munMatch ? munMatch[1] : null,
      number: munNumMatch ? parseInt(munNumMatch[1]) : null,
      name: munNumMatch ? munNumMatch[2] : munText,
    };
  }

  const nameCell = cells[2];
  const nameLink = nameCell.querySelector('a');
  if (!nameLink) continue;

  const nameHref = nameLink.getAttribute('href') || '';
  const idMatch = nameHref.match(/rkndId-(\d+)/);
  const rawName = nameLink.textContent.trim();
  const statusText = nameCell.textContent.trim();
  const status = parseStatus(statusText);
  const isElected = !!nameLink.querySelector('font[color="blue"]') || nameLink.innerHTML.includes('color="blue"');

  const roundCell = cells[3];
  const round = roundCell.textContent.trim();

  const nominatedCell = cells[4];
  const nominatedBy = nominatedCell.textContent.trim();

  candidates.push({
    id: idMatch ? idMatch[1] : null,
    ...parseName(rawName),
    municipality: currentMunicipality,
    round,
    nominatedBy,
    isElected,
    ...(status ? { status } : {}),
  });
}

console.log(JSON.stringify(candidates, null, 2));
