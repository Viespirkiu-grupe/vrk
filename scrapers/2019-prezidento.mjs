import { fetchDoc, extractId, parseName } from './_utils.mjs';

const doc = await fetchDoc('/rinkimai/904/rnk1184/kandidatai/preKandidatai.html');
const rows = [...doc.querySelectorAll('#table2 tr')];

const candidates = rows.flatMap(row => {
  const nameLink = row.querySelector('a');
  if (!nameLink) return [];
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 3) return [];

  const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);
  const rawName = nameLink.textContent.trim().replace(/\s+/g, ' ');
  const rowStyle = row.getAttribute('style') || '';
  const isElected = rowStyle.includes('color: blue');
  const statusText = cells[2].textContent.trim();
  const advancedToRound2 = statusText.includes('II');
  const roundMatch = statusText.match(/([I]+)\s+ture?/);

  return [{ id, ...parseName(rawName), isElected, advancedToRound2, ...(roundMatch ? { lastRound: roundMatch[1] } : {}) }];
});

console.log(JSON.stringify(candidates, null, 2));
