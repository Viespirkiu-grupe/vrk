import { fetchDoc, parseSeimasFullList } from './_utils.mjs';
const doc = await fetchDoc('/rinkimai/1384/rnk1704/kandidatai/SeiKandidataiPilnasSarasas.html');
console.log(JSON.stringify(parseSeimasFullList(doc), null, 2));
