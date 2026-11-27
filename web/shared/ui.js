export const expert = 'https://stellar.expert/explorer/public';
export const addressPattern = /^G[A-Z2-7]{55}$/;
const hashPattern = /^[a-f\d]{64}$/;
const numbers = new Intl.NumberFormat('ru', {maximumFractionDigits: 2});
const dates = new Intl.DateTimeFormat('ru', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC'});

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (value == null) continue;
    if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value);
  }
  node.append(...children.flat().filter(child => child != null));
  return node;
}

export function number(value) {
  return value == null || value === '' ? '—' : numbers.format(Number(value));
}

export function date(value) {
  return value ? dates.format(new Date(value)) : '—';
}

export function signed(value) {
  const amount = Number(value);
  return el('span', {class: amount > 0 ? 'positive' : amount < 0 ? 'negative' : ''}, amount > 0 ? '+' + number(value) : number(value));
}

export function link(url, text) {
  return el('a', {href: url, target: '_blank', rel: 'noopener noreferrer'}, text);
}

export function account(address, actions = false) {
  if (!addressPattern.test(address ?? '')) return el('span', {class: 'muted'}, address ? address.slice(0, 8) + '…' : '—');
  const short = address.slice(0, 6) + '…' + address.slice(-4);
  const anchor = el('a', {href: '#wallet/' + address, title: address}, short);
  if (!actions) return anchor;
  const copy = el('button', {type: 'button', title: 'Копировать ' + address, onclick: async () => {
    try {
      await navigator.clipboard.writeText(address);
      copy.textContent = 'Готово';
    } catch {
      copy.textContent = 'Ошибка';
    }
  }}, 'Копировать');
  return el('span', {class: 'account'}, anchor, copy, link(expert + '/account/' + address, 'Stellar Expert'));
}

export function transaction(hash) {
  return hashPattern.test(hash ?? '') ? link(expert + '/tx/' + hash, 'Открыть') : '—';
}

export function table(headers, rows, empty = 'Данных пока нет.') {
  if (!rows.length) return el('p', {class: 'muted'}, empty);
  const region = el('div', {class: 'table', tabindex: '0', role: 'region', 'aria-label': 'Таблица данных, прокручивается по горизонтали'});
  const head = el('thead', {}, el('tr', {}, headers.map(title => el('th', {scope: 'col'}, title))));
  const body = el('tbody', {}, rows.map(row => el('tr', {}, row.map(cell => el('td', {}, cell)))));
  region.append(el('table', {}, head, body));
  return region;
}

export function tile(title, value) {
  return el('div', {class: 'tile'}, el('span', {}, title), el('strong', {}, value));
}

export function panel(title, child) {
  const details = el('details', {class: 'panel', open: ''});
  details.append(el('summary', {}, title), child);
  return details;
}

export function select(options, value, change, attributes = {}) {
  const node = el('select', {...attributes, onchange: event => change(event.target.value)},
    Object.entries(options).map(([key, label]) => el('option', {value: key}, label)));
  node.value = value;
  return node;
}

export function chart(rows) {
  if (rows.length < 2) return el('p', {class: 'muted'}, 'Для графика нужны минимум два снимка.');
  const values = rows.map(row => Number(row.balance));
  const low = Math.min(...values), high = Math.max(...values);
  const first = Date.parse(rows[0].time), last = Date.parse(rows.at(-1).time);
  const canvas = el('canvas', {class: 'chart', width: '720', height: '150', role: 'img',
    'aria-label': 'Динамика баланса от ' + number(values[0]) + ' до ' + number(values.at(-1)) + ' XLM'});
  const ctx = canvas.getContext('2d');
  ctx.strokeStyle = '#2b363d';
  for (const y of [14, 75, 136]) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(720, y);
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.strokeStyle = '#7de5da';
  ctx.lineWidth = 2.5;
  rows.forEach((row, index) => {
    const x = 4 + 712 * (Date.parse(row.time) - first) / (last - first || 1);
    const y = high === low ? 75 : 136 - 122 * (values[index] - low) / (high - low);
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
  return el('div', {}, canvas, el('div', {class: 'legend'}, date(rows[0].time), number(low) + ' – ' + number(high) + ' XLM', date(rows.at(-1).time)));
}

export async function json(path, version) {
  const url = new URL('./data/' + path, document.baseURI);
  if (version) url.searchParams.set('v', version);
  const response = await fetch(url, {cache: 'no-store'});
  if (!response.ok) throw new Error('HTTP ' + response.status);
  return response.json();
}
