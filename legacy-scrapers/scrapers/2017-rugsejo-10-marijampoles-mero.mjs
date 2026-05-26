import { fetchDoc, parseMayorTable } from './_utils.mjs';
const doc = await fetchDoc('/rinkimai/784/rnk1024/kandidatai/savKandidataiMerai.html');
console.log(JSON.stringify(parseMayorTable(doc), null, 2));
