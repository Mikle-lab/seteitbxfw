import {account, date, el, number, select, signed, table} from '../../shared/ui.js';
import {star} from '../watchlist/index.js';

const sorting = {balance: 'Баланс', up: 'Накопление', down: 'Сокращение', percent: 'Изменение, %', last: 'Последняя активность'};

export function whales(rows, period, state, rerender) {
  const list = rows.filter(row => !row.label && (state.exited || row.active));
  const value = row => state.sort === 'last' ? Date.parse(row.last_activity ?? 0) :
    Number(state.sort === 'balance' ? row.balance : row.periods[period][state.sort]);
  list.sort((a, b) => value(b) - value(a));
  const filters = el('div', {class: 'filters'},
    el('label', {}, 'Сортировка', select(sorting, state.sort, value => { state.sort = value; state.page = 0; rerender(); })),
    el('label', {}, 'Показывать', select({active: 'Выше порога', all: 'Все обнаруженные'}, state.exited ? 'all' : 'active',
      value => { state.exited = value === 'all'; state.page = 0; rerender(); })));
  const last = Math.max(0, Math.ceil(list.length / 25) - 1);
  state.page = Math.min(last, state.page);
  const nav = el('div', {class: 'paginator'},
    el('button', {disabled: state.page === 0 ? '' : null, onclick: () => { state.page--; rerender(); }}, 'Назад'),
    el('span', {class: 'muted'}, `Страница ${state.page + 1} из ${last + 1}`),
    el('button', {disabled: state.page >= last ? '' : null, onclick: () => { state.page++; rerender(); }}, 'Далее'));
  const result = list.slice(state.page * 25, (state.page + 1) * 25).map(row => {
    const stats = row.periods[period];
    return [el('div', {class: 'account'}, account(row.address, true), star(row.address)), row.category,
      number(row.balance), signed(stats.delta), signed(stats.percent), number(stats.received), number(stats.sent),
      number(stats.operations), date(row.last_activity), stats.anomalies ? el('span', {class: 'warning'}, number(stats.anomalies)) : '—'];
  });
  return el('section', {}, el('h1', {}, 'Киты'), filters,
    table(['Адрес', 'Категория', 'Баланс XLM', 'Изменение XLM', 'Изменение %', 'Получено XLM', 'Отправлено XLM',
      'Крупных движений', 'Активность UTC', 'Сигналы'], result), nav);
}
