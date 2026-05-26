import { parseMunicipalElection } from './_utils.mjs';

const result = await parseMunicipalElection('/rinkimai/864/rnk1144/kandidatai');
console.log(JSON.stringify(result, null, 2));
