import { parseHTML } from 'linkedom';

const STATIC_BASE = 'https://www.vrk.lt/statiniai/puslapiai';
const BASE_PATH = '/rinkimai/1504/rnk1786/kandidatai';

async function fetchDoc(path) {
  const res = await fetch(STATIC_BASE + path);
  const html = (await res.text()).replace(/data:[^"]+/g, '');
  return parseHTML(html).document;
}

function parseName(raw) {
  const text = raw.trim().replace(/\s+/g, ' ');
  const parts = text.split(' ');
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

async function fetchNominatedBy(id) {
  const doc = await fetchDoc(`${BASE_PATH}/KandidatasAnketa_rkndId-${id}.html`);
  const table = doc.querySelector('table.partydata');
  if (!table) return null;
  for (const row of table.querySelectorAll('tr')) {
    const text = row.textContent.trim().replace(/\s+/g, ' ');
    if (text.toLowerCase().includes('iškėlė')) {
      // "Kandidatą iškėlė <Party Name>" — extract after "iškėlė"
      const match = text.match(/iškėlė\s+(.+)/i);
      if (match) return match[1].trim();
    }
  }
  return null;
}

const doc = await fetchDoc(`${BASE_PATH}/preKandidatai.html`);
const rows = [...doc.querySelectorAll('#table2 tbody tr')];

const candidates = await Promise.all(rows.map(async row => {
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 3) return null;

  const nameLink = cells[1]?.querySelector('a');
  if (!nameLink) return null;

  const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
  const rawName = nameLink.textContent.trim().replace(/\s+/g, ' ');
  const { firstName, lastName } = parseName(rawName);
  const statusText = cells[2].textContent.trim();
  const isElected = (row.getAttribute('style') || '').includes('color: blue');

  const roundMatch = statusText.match(/([I]+)\s+ture?/);
  const round = roundMatch ? roundMatch[1] : null;
  const advancedToRound2 = statusText.includes('II');

  const nominatedBy = await fetchNominatedBy(id);

  return {
    id,
    firstName,
    lastName,
    isElected,
    advancedToRound2,
    ...(round ? { lastRound: round } : {}),
    ...(nominatedBy ? { nominatedBy } : {}),
  };
}));

console.log(JSON.stringify(candidates.filter(Boolean), null, 2));
