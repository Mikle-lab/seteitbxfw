import {account, chart, date, el, number, panel, signed, table, tile} from '../../shared/ui.js';
import {anomalyTable} from '../anomalies/index.js';
import {operationTable} from '../transactions/index.js';
import {walletTrends} from '../trends/index.js';
import {star} from '../watchlist/index.js';

export function wallet(data, period, cutoff, labels) {
  const {wallet, history, operations, anomalies, counterparts} = data;
  const stats = wallet.periods[period];
  return el('section', {}, el('h1', {}, 'Кошелёк'),
    el('div', {class: 'account'}, account(wallet.address, true), star(wallet.address)),
    el('p', {class: 'muted break'}, wallet.address + ' · ' + (wallet.label?.name ?? wallet.category)),
    el('div', {class: 'grid'}, tile('Баланс XLM', number(wallet.balance)), tile('Минимум XLM', number(wallet.minimum)),
      tile('Максимум XLM', number(wallet.maximum)), tile('Изменение XLM', signed(stats.delta)),
      tile('Получено крупными движениями', number(stats.received)), tile('Отправлено крупными движениями', number(stats.sent))),
    el('p', {class: 'muted'}, 'Обнаружен ' + date(wallet.first_seen) + ' · Баланс проверен ' + date(wallet.updated) + ' UTC'),
    walletTrends(data.trends),
    panel('История баланса', chart(history.filter(row => row.time >= cutoff))),
    panel('Крупные движения', operationTable(operations.filter(row => row.time >= cutoff), labels)),
    panel('Аномалии', anomalyTable(anomalies.filter(row => row.time >= cutoff))),
    panel('Частые контрагенты в крупных движениях', table(['Адрес', 'За всё время'], counterparts.map(
      ([address, count]) => [account(address), number(count)]))));
}
