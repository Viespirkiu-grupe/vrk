import { fetchDoc, parseMayorTable } from './_utils.mjs';

const BASE_PATH = '/rinkimai/1426/rnk1746/kandidatai';
const doc = await fetchDoc(`${BASE_PATH}/savKandidataiMerai.html`);
const candidates = parseMayorTable(doc, BASE_PATH);
console.log(JSON.stringify(candidates, null, 2));
