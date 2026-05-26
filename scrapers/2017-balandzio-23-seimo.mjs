import { fetchDoc, parseSeimasFullList } from './_utils.mjs';
const doc = await fetchDoc('/rinkimai/748/rnk984/kandidatai/lrsKandidataiPilnasSarasas.html');
console.log(JSON.stringify(parseSeimasFullList(doc), null, 2));
