import { parseHTML } from 'linkedom';

const res = await fetch('https://www.vrk.lt/pagal-data');
const html = await res.text();
const { document } = parseHTML(html);

function classifyType(title) {
  const t = title.toLowerCase();
  if (t.includes('referendumas')) return 'referendumas';
  if (t.includes('europos parlamento') || t.includes('į europos parlamentą')) return 'europosParlamento';
  if (t.includes('prezidento rinkimai')) return 'prezidento';
  if (t.includes('savivaldybių tarybų ir merų')) return 'savivaldybiuTarybуIrMeru';
  if (t.includes('tarybos nario') || t.includes('tarybų narių') || t.includes('mero rinkimai') || t.includes('merų rinkimai')) return 'meroIrTarybosNario';
  if (t.includes('savivaldybių tarybų')) return 'savivaldybiuTarybu';
  if (t.includes('seimo') || t.includes('seimą')) return 'seimo';
  return 'kita';
}

function classifySubtype(title) {
  const t = title.toLowerCase();
  if (t.includes('pirmalaikiai')) return 'pirmalaikiai';
  if (t.includes('pakartotiniai')) return 'pakartotiniai';
  if (t.includes('nauji')) return 'nauji';
  return null;
}

const rows = [...document.querySelectorAll('tr')];

const elections = rows.flatMap(row => {
  const cells = [...row.querySelectorAll('td')];
  if (cells.length < 2) return [];

  const dateText = cells[0].textContent.trim().replace(/\s+/g, '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateText)) return [];

  const links = [...cells[1].querySelectorAll('a')];
  if (!links.length) return [];

  return links.map(link => {
    const title = link.textContent.trim().replace(/\s+/g, ' ').replace(/ /g, '');
    const href = link.getAttribute('href') || '';
    const url = href.startsWith('http') ? href : `https://www.vrk.lt${href}`;
    const isMain = !!link.closest('strong');
    const type = classifyType(title);
    const subtype = classifySubtype(title);

    return {
      date: dateText,
      title,
      url,
      type,
      ...(subtype ? { subtype } : {}),
      isMain,
    };
  });
});

console.log(JSON.stringify(elections, null, 2));
