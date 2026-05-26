import { fetchDoc, parseEPFullList } from './_utils.mjs';
const doc = await fetchDoc('/rinkimai/904/rnk1186/kandidatai/epKandidataiPilnasSarasas.html');
console.log(JSON.stringify(parseEPFullList(doc), null, 2));
