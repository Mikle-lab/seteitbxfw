import {signedXlm, xlm} from '../../shared/money.js';
import {account, el, link, number, panel, select, signed, table, tile} from '../../shared/ui.js';

const usd = new Intl.NumberFormat('ru', {style: 'currency', currency: 'USD', maximumFractionDigits: 6});
const priceText = value => value == null ? '—' : usd.format(Number(value));

const windows = {'7d': '7 дней', '30d': '30 дней'};

export function trendView(data, selected, change) {
  const stats = data.periods[selected];
  const ranking = rows => table(['Кошелёк', 'Категория', 'Накопление XLM', 'Сокращение XLM', 'Итог XLM'],
    rows.map(row => [account(row.address), row.category, xlm(row.up), xlm(row.down), signedXlm(row.net)]),
    'Пока нет кошельков с полным покрытием периода и движением в этом направлении.');
  return el('section', {}, el('h1', {}, 'Динамика балансов'),
    el('p', {class: 'muted'}, 'Завершённые дни UTC по ' + data.through +
      '. Изменение рассчитывается между наблюдениями у границ суток. Пропуски не заполняются нулями.'),
    el('div', {class: 'filters'}, el('label', {}, 'Окно динамики', select(windows, selected, change))),
    el('div', {class: 'grid'},
      tile('Кошельков с полным периодом', number(stats.complete)),
      tile('Кошельков с наблюдениями', number(stats.observed)),
      tile('Кошельков в выборке', number(stats.total))),
    stats.complete === 0 ? el('p', {class: 'warning'},
      'Для рейтинга пока недостаточно истории. Индивидуальные наблюдения доступны в карточках кошельков.') : null,
    el('div', {class: 'panels'}, panel('Накопление', ranking(stats.accumulation)), panel('Сокращение', ranking(stats.reduction))),
    panel('Закрытие XLM/USD · Coinbase Exchange',
      el('div', {}, data.price_source ? link(data.price_source, 'Источник котировок') : null,
        data.price_error ? el('p', {class: 'warning'}, 'Последнее обновление котировок не удалось. Ниже сохранённые данные.') : null,
        table(['Дата UTC', 'Закрытие', 'Изменение, %'], (data.prices ?? []).slice(-stats.required).reverse()
          .map(row => [row.day, priceText(row.usd), signed(row.percent)])))));
}

export function walletTrends(trends) {
  if (!trends) return null;
  const stats = Object.entries(windows).map(([key, label]) => {
    const row = trends[key];
    return [label, row.observed + ' / ' + row.required, xlm(row.up), xlm(row.down), signedXlm(row.net)];
  });
  const daily = trends['30d'].daily.slice().reverse();
  return panel('Долгосрочная динамика',
    el('div', {},
      el('p', {class: 'muted'}, 'Суммы включают завершённые сутки с наблюдениями у обеих границ. Неполные периоды можно узнать по столбцу «Наблюдалось суток».'),
      table(['Окно', 'Наблюдалось суток', 'Накопление XLM', 'Сокращение XLM', 'Итог XLM'], stats),
      panel('Изменения по дням UTC', table(['Дата', 'Изменение XLM', 'Закрытие XLM/USD', 'Изменение цены, %'],
        daily.map(row => [row.day, signedXlm(row.delta), priceText(row.price?.usd), signed(row.price?.percent)]), 'Пока нет двух последовательных наблюдений у границ суток.'))));
}
