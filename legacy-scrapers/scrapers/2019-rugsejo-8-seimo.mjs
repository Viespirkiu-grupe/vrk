import { fetchDoc, parseSeimasFullList } from './_utils.mjs';
const doc = await fetchDoc('/rinkimai/1066/rnk1388/kandidatai/SeiKandidataiPilnasSarasas.html');
console.log(JSON.stringify(parseSeimasFullList(doc), null, 2));
