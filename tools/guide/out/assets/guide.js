'use strict';
for (const section of document.querySelectorAll('main section')) {
  const table = section.querySelector('table');
  const body = table.tBodies[0];
  const rows = Array.from(body.rows);
  const search = section.querySelector('input');
  const output = section.querySelector('output');
  const empty = section.querySelector('.empty');
  const texts = new Map(rows.map(row => [row, row.textContent.toLowerCase()]));
  search.addEventListener('input', () => {
    const words = search.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    let count = 0;
    for (const row of rows) {
      row.hidden = !words.every(word => texts.get(row).includes(word));
      if (!row.hidden) count++;
    }
    output.textContent = `${count} of ${rows.length} entries`;
    empty.hidden = count > 0;
  });
  table.querySelectorAll('th button').forEach((button, index) => {
    button.addEventListener('click', () => {
      const th = button.parentElement;
      const direction = th.getAttribute('aria-sort') === 'ascending' ? -1 : 1;
      table.querySelectorAll('th').forEach(head => head.setAttribute('aria-sort', 'none'));
      th.setAttribute('aria-sort', direction === 1 ? 'ascending' : 'descending');
      const sorted = rows.slice().sort((a, b) => {
        const x = a.cells[index].dataset.value;
        const y = b.cells[index].dataset.value;
        const cmp = x.trim() !== '' && y.trim() !== '' && Number.isFinite(Number(x)) && Number.isFinite(Number(y))
          ? Number(x) - Number(y) : x.localeCompare(y, 'en', {numeric: true});
        return direction * cmp;
      });
      body.append(...sorted);
    });
  });
}
function revealSpecies() {
  if (!location.hash.startsWith('#species-')) return;
  const row = document.getElementById(location.hash.slice(1));
  if (!row) return;
  const input = document.querySelector('#species-search');
  input.value = '';
  input.dispatchEvent(new Event('input'));
  row.scrollIntoView({block: 'center'});
}
window.addEventListener('hashchange', revealSpecies);
revealSpecies();
