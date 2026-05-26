import { parseHTML } from 'linkedom';

const STATIC_BASE = 'https://www.vrk.lt/statiniai/puslapiai';

async function fetchDoc(path) {
  const res = await fetch(STATIC_BASE + path);
  const html = await res.text();
  return parseHTML(html).document;
}

function parseName(raw) {
  const text = raw.trim();
  const parts = text.split(/\s+/);
  const lastNameIdx = parts.findIndex(p => p === p.toUpperCase() && p.length > 1);
  if (lastNameIdx === -1) return { firstName: parts.slice(0, -1).join(' '), lastName: parts.at(-1) };
  return {
    firstName: parts.slice(0, lastNameIdx).join(' '),
    lastName: parts.slice(lastNameIdx).join(' '),
  };
}

function extractId(href, pattern) {
  const match = (href || '').match(pattern);
  return match ? match[1] : null;
}

const doc = await fetchDoc('/rinkimai/1546/rnk1866/kandidatai/epKandidataiPilnasSarasas.html');
const rows = [...doc.querySelectorAll('#table2 tr')].slice(1); // skip header

const candidates = rows.flatMap(row => {
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 4) return [];

  const nameLink = cells[0].querySelector('a');
  if (!nameLink) return [];

  const isElected = (row.getAttribute('style') || '').includes('color: blue');
  const rawName = nameLink.textContent.trim().replace(/\s+/g, ' ');
  const { firstName, lastName } = parseName(rawName);
  const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);

  const listLink = cells[1].querySelector('a');
  const listRaw = listLink ? listLink.textContent.trim().replace(/\s+/g, ' ') : null;
  const listNumMatch = listRaw?.match(/^(\d+)\.\s+(.+)/);
  const partyList = listLink ? {
    id: extractId(listLink.getAttribute('href'), /sarasoId-(\d+)/),
    number: listNumMatch ? parseInt(listNumMatch[1]) : null,
    name: listNumMatch ? listNumMatch[2] : listRaw,
  } : null;

  const listPosition = cells[2].textContent.trim();
  const postElectionPosition = cells[3].textContent.trim();

  return [{
    id,
    firstName,
    lastName,
    isElected,
    ...(partyList ? { partyList } : {}),
    ...(listPosition ? { listPosition: parseInt(listPosition) } : {}),
    ...(postElectionPosition ? { postElectionPosition: parseInt(postElectionPosition) } : {}),
  }];
});

console.log(JSON.stringify(candidates, null, 2));
