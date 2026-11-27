import {account, date, el, number, select, signed, table} from '../../shared/ui.js';
const levels = {low: 'Низкий', medium: 'Средний', high: 'Высокий', critical: 'Критический'};

export function anomalyTable(rows) {
  return table(['Время UTC', 'Значимость', 'Причина', 'Кошелёк', 'Сумма XLM', 'Изменение %'],
    rows.map(row => [date(row.time), el('span', {class: 'warning'}, levels[row.level] ?? row.level),
      row.reason, account(row.address), number(row.amount), signed(row.percent)]),
  'На этой странице нет сигналов по выбранным фильтрам.');
}

export function filters(state, rerender) {
  return el('div', {class: 'filters'}, el('label', {}, 'Значимость',
    select({'': 'Все', ...levels}, state.level, value => { state.level = value; state.page = 0; rerender(); })));
}
