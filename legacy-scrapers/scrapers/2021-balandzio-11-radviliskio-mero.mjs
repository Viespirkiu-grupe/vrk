import { fetchDoc, parseMayorTable } from './_utils.mjs';
const doc = await fetchDoc('/rinkimai/1144/rnk1464/kandidatai/savKandidataiMerai.html');
console.log(JSON.stringify(parseMayorTable(doc), null, 2));
