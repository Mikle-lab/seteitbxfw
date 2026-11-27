import {account, chart, date, el, link, number, panel, signed, table, tile, transaction} from '../../shared/ui.js';

function transfers(rows, labels) {
  return table(['Время UTC', 'Биржа', 'Сумма XLM', 'Отправитель', 'Получатель', 'Транзакция'],
    rows.map(row => [date(row.time), labels[row.address]?.name ?? '—', number(row.amount),
      account(row.sender), account(row.recipient), transaction(row.hash)]));
}

export function exchanges(data, period, cutoff, labels) {
  const stats = data.periods[period];
  const available = Boolean(data.coverage);
  return el('section', {}, el('h1', {}, 'Биржи'),
    el('p', {class: 'muted'}, 'Покрытие с ' + date(data.coverage) + ' UTC. Учитываются прямые платежи XLM между отслеживаемым биржевым адресом и адресом вне реестра. По переводу нельзя установить, была ли покупка или продажа.'),
    stats.complete ? null : el('p', {class: 'warning'}, 'История за выбранный период неполная.'),
    el('div', {class: 'grid'}, tile('Приток XLM', number(available ? stats.inflow : null)),
      tile('Отток XLM', number(available ? stats.outflow : null)), tile('Чистый поток XLM', signed(available ? stats.net : null)),
      tile('Платежи', number(available ? stats.count : null))),
    el('h2', {}, 'Отслеживаемые адреса'),
    table(['Биржа', 'Адрес', 'Баланс XLM', 'Снимок UTC', 'Источник', 'Достоверность'], data.balances.map(row => [
      row.name, account(row.address, true), number(row.balance), date(row.updated),
      /^https:\/\//.test(row.source) ? link(row.source, 'Источник метки') : '—',
      row.confidence === 'high' ? 'Высокая' : 'Средняя',
    ])),
    el('div', {class: 'panels'}, data.balances.map(row => panel('Баланс · ' + row.name,
      chart(row.history.filter(sample => sample.time >= cutoff))))),
    panel('Крупнейшие поступления', transfers(stats.deposits, labels)),
    panel('Крупнейшие выводы', transfers(stats.withdrawals, labels)));
}
