import {account, addressPattern, el, number, table} from '../../shared/ui.js';
const key = 'xlm-radar.watchlist.v1';

function read() {
  try { return JSON.parse(localStorage.getItem(key)) ?? {}; } catch { return {}; }
}

function save(address, name) {
  const list = read();
  if (name === null) delete list[address];
  else list[address] = name;
  localStorage.setItem(key, JSON.stringify(list));
}

export function star(address) {
  const button = el('button', {type: 'button'}, '');
  const update = () => {
    const selected = Object.hasOwn(read(), address);
    button.textContent = selected ? 'В избранном' : 'В избранное';
    button.setAttribute('aria-pressed', String(selected));
  };
  button.onclick = () => {
    try { save(address, Object.hasOwn(read(), address) ? null : ''); update(); }
    catch { button.textContent = 'Хранилище недоступно'; }
  };
  update();
  return button;
}

export function watchlist(whales, period, rerender) {
  const list = read();
  const balances = new Map(whales.map(wallet => [wallet.address, wallet]));
  const address = el('input', {'aria-label': 'Адрес Stellar', placeholder: 'Адрес Stellar', maxlength: 56});
  const label = el('input', {'aria-label': 'Название', placeholder: 'Название', maxlength: 80});
  const message = el('span', {role: 'status'});
  const button = el('button', {type: 'button', onclick: () => {
    const value = address.value.trim().toUpperCase();
    if (!addressPattern.test(value)) { message.textContent = 'Введите публичный адрес Stellar.'; return; }
    try { save(value, label.value.trim()); rerender(); }
    catch { message.textContent = 'Локальное хранилище недоступно.'; }
  }}, 'Сохранить');
  const download = el('button', {type: 'button', onclick: () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(list, null, 2)], {type: 'application/json'}));
    const anchor = el('a', {href: url, download: 'xlm-radar-watchlist.json'});
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }}, 'Экспорт JSON');
  const rows = Object.entries(list).map(([id, name]) => {
    const wallet = balances.get(id);
    const remove = el('button', {type: 'button', onclick: () => {
      try { save(id, null); rerender(); }
      catch { message.textContent = 'Локальное хранилище недоступно.'; }
    }}, 'Удалить');
    return [account(id, true), name || '—', number(wallet?.balance), number(wallet?.periods[period].delta),
      number(wallet?.periods[period].anomalies), remove];
  });
  return el('section', {}, el('h1', {}, 'Избранное'),
    el('p', {class: 'muted'}, 'Названия и адреса сохраняются в этом браузере. Балансы доступны для обнаруженных сборщиком адресов.'),
    el('div', {class: 'filters'}, address, label, button, download, message),
    table(['Адрес', 'Название', 'Баланс XLM', 'Изменение XLM', 'Сигналы', ''], rows));
}
