import {xlm} from '../../shared/money.js';
import {account, date, el, link, number, panel, table, tile} from '../../shared/ui.js';

const side = {buy: 'Покупка XLM', sell: 'Продажа XLM'};
const venue = {orderbook: 'Стакан', liquidity_pool: 'Пул'};

export function dex(data, period) {
  const stats = data.periods[period];
  const available = Boolean(data.coverage);
  const metric = key => xlm(available ? stats[key] : null);
  const indicator = data.error ? 'Последнее сканирование DEX завершилось ошибкой.' : 'Обновлено ' + date(data.updated) + ' UTC.';
  return el('section', {}, el('h1', {}, 'Stellar DEX'),
    el('p', {class: 'muted'}, 'Подтверждённые исполнения Horizon. Направление сделки определяется со стороны инициатора операции, если его можно сопоставить со стороной исполнения. Каждое исполнение маршрута учитывается один раз. ' + indicator),
    stats.complete ? null : el('p', {class: 'warning'}, 'История за выбранный период неполная.'),
    el('div', {class: 'grid'}, tile('Исполнений', number(available ? stats.count : null)), tile('Объём XLM', metric('volume')),
      tile('Покупки XLM', el('span', {class: 'positive'}, metric('buy'))),
      tile('Продажи XLM', el('span', {class: 'negative'}, metric('sell'))),
      tile('Направление не установлено, XLM', metric('unknown')),
      tile('Покупки / продажи', Number(stats.sell) > 0 ? number(Number(stats.buy) / Number(stats.sell)) : '—')),
    el('div', {class: 'panels'},
      panel('Торговые пары', table(['Пара', 'Эмитент', 'Объём XLM', 'Исполнений'],
        stats.pairs.map(row => ['XLM / ' + row.code, account(row.issuer), xlm(row.volume), number(row.count)]))),
      panel('Динамика по дням UTC', table(['День', 'Покупки XLM', 'Продажи XLM', 'Без направления XLM'],
        stats.history.map(row => [row.day, xlm(row.buy), xlm(row.sell), xlm(row.unknown)])))),
    panel('Крупнейшие исполнения', table(['Время UTC', 'Пара', 'Объём XLM', 'Инициатор', 'Площадка', 'Покупатель', 'Продавец', 'Операция'],
      stats.top.map(row => [date(row.time), 'XLM / ' + row.code, xlm(row.amount), side[row.direction] ?? '—',
        venue[row.venue] ?? row.venue, account(row.buyer), account(row.seller),
        /^\d+$/.test(row.operation) ? link('https://horizon.stellar.org/operations/' + row.operation, 'Horizon') : '—']))));
}
