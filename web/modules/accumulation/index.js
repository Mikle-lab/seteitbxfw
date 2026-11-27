import {signedXlm, xlm} from '../../shared/money.js';
import {account, el, number, panel, select, table} from '../../shared/ui.js';

const periods = {'1': '1 день', '7': '7 дней', '30': '30 дней'};

export function paymentHistory(history) {
  return panel('История прямых платежей XLM',
    history ? el('div', {}, el('p', {class: 'muted'},
      'За завершённые сутки до ' + history.end + ' UTC. Учитываются входящие и исходящие прямые платежи XLM.'),
    table(['Период', 'Получено XLM', 'Отправлено XLM', 'Разница XLM', 'Платежей', 'Покрытие'],
      Object.entries(periods).map(([key, text]) => {
        const row = history.periods[key];
        return [text, xlm(row.incoming), xlm(row.outgoing), signedXlm(row.net), number(row.payments),
          row.complete ? 'Полное' : 'Догружается или неполное'];
      }))) : el('p', {class: 'muted'}, 'История ожидает загрузки.'));
}

export function accumulationView(data, holders, window, change) {
  const result = data.periods[window];
  function ranking(group) {
    return el('div', {}, el('p', {class: 'muted'}, 'Полная история: ' + number(group.complete) + ' из ' + number(group.total)),
      table(['Адрес', 'Баланс XLM', 'Получено XLM', 'Отправлено XLM', 'Разница XLM'], group.rows.map(
        row => [account(row.address), xlm(row.balance), xlm(row.flows.incoming), xlm(row.flows.outgoing), signedXlm(row.flows.net)]),
      'Пока нет полного периода с положительным итогом.'));
  }
  const candidates = holders.filter(row => row.review === 'candidate' && row.active);
  return el('section', {}, el('h1', {}, 'Накопление'),
    el('p', {class: 'muted'}, 'Рейтинг по разнице между полученными и отправленными XLM в прямых платежах. Перевод сам по себе не подтверждает покупку или продажу. Окна заканчиваются перед ' + data.through + ' UTC.'),
    el('div', {class: 'filters'}, el('label', {}, 'Период платежей', select(periods, window, change))),
    panel('Допущенные держатели', ranking(result.approved)),
    panel('Положительный итог у кандидатов', ranking(result.candidates)),
    panel('Кандидаты на проверку', table(['Адрес', 'Баланс XLM', 'История для периода'],
      candidates.map(row => [account(row.address), xlm(row.balance), row.payments?.end === data.through &&
        row.payments.periods[window].complete ? 'Готова' : 'Догружается или неполная'])),
    ));
}
