import { fetchDoc, parseMayorTable } from './_utils.mjs';
const doc = await fetchDoc('/rinkimai/748/rnk948/kandidatai/savKandidataiMerai.html');
console.log(JSON.stringify(parseMayorTable(doc), null, 2));
