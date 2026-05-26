import { parseHTML } from 'linkedom';
import { fetchDoc, extractId, parseName } from './_utils.mjs';

const doc = await fetchDoc('/rinkimai/1104/rnk1424/kandidatai/SeiKandidataiPilnasSarasas.html');
const rows = [...doc.querySelectorAll('#table3 tr:not(thead tr)')];

const candidates = rows.flatMap(row => {
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 7) return [];

  const nameLink = cells[0].querySelector('a');
  if (!nameLink) return [];

  const isElected = (nameLink.getAttribute('style') || '').includes('color: blue');
  const rawName = nameLink.textContent.trim().replace(/\s+/g, ' ');
  const electionTypeMatch = rawName.match(/\(([DV])\)\s*$/);
  const electionType = electionTypeMatch ? electionTypeMatch[1] : null;
  const cleanName = rawName.replace(/\([DV]\)\s*$/, '').trim();
  const id = extractId(nameLink.getAttribute('href'), /rkndId-(\d+)/);

  const listLink = cells[1].querySelector('a');
  const partyList = listLink ? {
    name: listLink.textContent.trim(),
    id: extractId(listLink.getAttribute('href'), /rorgId-(\d+)/),
  } : null;

  const listPosition = parseInt(cells[2].textContent.trim()) || null;
  const postElectionPosition = parseInt(cells[3].textContent.trim()) || null;

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
    ...parseName(cleanName),
    isElected,
    ...(electionType ? { electionType } : {}),
    ...(partyList ? { partyList } : {}),
    ...(listPosition ? { listPosition } : {}),
    ...(postElectionPosition ? { postElectionPosition } : {}),
    ...(district ? { district } : {}),
    ...(nominatedBy ? { nominatedBy } : {}),
    ...(round ? { round } : {}),
  }];
});

console.log(JSON.stringify(candidates, null, 2));
