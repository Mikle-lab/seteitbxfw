import {signedXlm, xlm, xlmText} from '../../shared/money.js';
import {account, chart, date, el, number, panel, table, tile} from '../../shared/ui.js';
import {anomalyTable} from '../anomalies/index.js';
import {operationTable} from '../transactions/index.js';
import {paymentHistory} from '../accumulation/index.js';
import {walletTrends} from '../trends/index.js';
import {inactivityText, interactionTable} from '../activity/index.js';
import {portfolioView} from './portfolio.js';
import {star} from '../watchlist/index.js';

export function wallet(data, period, cutoff, labels) {
  const {wallet, history, operations, anomalies, counterparts} = data;
  const stats = wallet.periods[period];
  return el('section', {}, el('h1', {}, 'Кошелёк'),
    el('div', {class: 'account wallet-actions'}, account(wallet.address, true), star(wallet.address)),
    el('p', {class: 'muted break'}, wallet.address + ' · ' + (wallet.label?.name ?? wallet.category)),
    el('div', {class: 'grid'}, tile('Баланс XLM', xlm(wallet.balance)), tile('Минимум XLM', xlm(wallet.minimum)),
      tile('Максимум XLM', xlm(wallet.maximum)), tile('Изменение XLM', signedXlm(stats.delta)),
      tile('Получено крупными движениями', xlm(stats.received)), tile('Отправлено крупными движениями', xlm(stats.sent))),
    el('p', {class: 'muted'}, 'Обнаружен ' + date(wallet.first_seen) + ' · Баланс проверен ' + date(wallet.updated) + ' UTC'),
    el('p', {class: 'muted'}, 'Последняя замеченная операция: ' + date(wallet.last_activity) +
      ' UTC · Тишина: ' + inactivityText(wallet.inactivity)),
    wallet.review === 'candidate' ? el('p', {class: 'warning'}, 'Кандидат. Тип владельца ещё не проверен.') : null,
    portfolioView(data.portfolio),
    paymentHistory(wallet.payments),
    walletTrends(data.trends),
    panel('Повторные прямые переводы за 30 дней', interactionTable(data.interactions ?? [], wallet.address)),
    panel('История баланса', chart(history.filter(row => row.time >= cutoff), xlmText)),
    panel('Крупные движения', operationTable(operations.filter(row => row.time >= cutoff), labels)),
    panel('Аномалии', anomalyTable(anomalies.filter(row => row.time >= cutoff))),
    panel('Частые контрагенты в крупных движениях', table(['Адрес', 'За всё время'], counterparts.map(
      ([address, count]) => [account(address), number(count)]))));
}
