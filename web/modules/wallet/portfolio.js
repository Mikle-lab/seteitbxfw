import {account, date, el, number, panel, table, tile} from '../../shared/ui.js';
import {currentQuote, dollars} from '../../shared/money.js';

export function portfolioView(portfolio) {
  if (!portfolio) return panel('Активы кошелька', el('p', {class: 'muted'}, 'Ожидается обновление состава активов.'));
  const current = currentQuote({price: 1, time: portfolio.quote_time});
  const incomplete = portfolio.valued < portfolio.assets.length;
  const title = current && !incomplete ? 'Общая оценка' : 'Стоимость оценённых активов';
  return panel('Активы кошелька', el('div', {},
    el('div', {class: 'grid'}, tile(title, current ? dollars(portfolio.usd) : '—'),
      tile('Активов с оценкой', (current ? portfolio.valued : 0) + ' / ' + portfolio.assets.length)),
    el('p', {class: 'muted'}, 'Остатки на ' + date(portfolio.updated) + ' UTC. ' +
      (current ? 'Курс XLM на ' + date(portfolio.quote_time) + ' UTC.' : 'Свежая долларовая котировка недоступна.')),
    table(['Актив', 'Эмитент', 'Остаток', 'Оценка USD'], portfolio.assets.map(row => [
      row.kind === 'native' ? 'XLM' : row.code ?? 'Доля пула ' + (row.pool?.slice(0, 8) ?? ''),
      row.issuer ? account(row.issuer) : '—', number(row.amount),
      current && row.usd !== null ? '≈ ' + dollars(row.usd) : 'Нет котировки',
    ]), 'Horizon не вернул ненулевых остатков.'),
    el('p', {class: 'muted'}, 'Оценка основана на балансах Horizon и доступных рыночных котировках.')));
}
