import {account, date, el, number, select, table, transaction} from '../../shared/ui.js';

const types = {payment: 'Перевод', create_account: 'Создание счёта', path_send: 'Маршрут · вход',
  path_receive: 'Маршрут · выход', create_claimable_balance: 'Резервирование', contract_transfer: 'Контракт · перевод',
  contract_mint: 'Контракт · выпуск', contract_burn: 'Контракт · сжигание'};

export function operationTable(rows, labels = {}) {
  const party = address => el('span', {}, account(address), labels[address]?.name ? ' · ' + labels[address].name : '');
  return table(['Время UTC', 'Тип', 'Сумма XLM', 'Отправитель', 'Получатель', 'Транзакция'],
    rows.map(row => [date(row.time), types[row.kind] ?? row.kind, number(row.amount), party(row.sender),
      party(row.recipient), transaction(row.hash)]), 'На этой странице нет движений по выбранным фильтрам.');
}

export function filters(state, rerender) {
  function field(key, label, attributes) {
    const input = el('input', {...attributes, value: state[key] ?? '', onchange: event => {
      state[key] = event.target.value.trim();
      state.page = 0;
      rerender();
    }});
    return el('label', {}, label, input);
  }
  return el('div', {class: 'filters'}, field('min', 'Мин. XLM', {type: 'number', min: 0}),
    field('max', 'Макс. XLM', {type: 'number', min: 0}), field('address', 'Адрес', {type: 'search', maxlength: 56}),
    el('label', {}, 'Тип', select({'': 'Все', ...types}, state.kind, value => { state.kind = value; state.page = 0; rerender(); })),
    el('label', {}, 'Направление для адреса', select({any: 'Любое', in: 'Входящие', out: 'Исходящие'}, state.direction,
      value => { state.direction = value; state.page = 0; rerender(); })));
}

export function matches(row, state, cutoff) {
  if (row.time < cutoff || (state.min && Number(row.amount) < Number(state.min)) ||
      (state.max && Number(row.amount) > Number(state.max)) || (state.kind && row.kind !== state.kind)) return false;
  const address = state.address.toUpperCase();
  if (!address) return true;
  return (state.direction !== 'out' && row.recipient === address) ||
    (state.direction !== 'in' && row.sender === address);
}
