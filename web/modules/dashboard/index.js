import {signedXlm, xlm, xlmText} from '../../shared/money.js';
import {chart, date, el, number, panel, tile} from '../../shared/ui.js';

function balanceFlows(rows) {
  const observed = rows.filter(row => row.up != null && row.down != null);
  if (!observed.length) return el('p', {class: 'muted'}, 'Ожидаются повторные снимки.');
  const maximum = Math.max(0, ...observed.flatMap(row => [Number(row.up), Number(row.down)]));
  const canvas = el('canvas', {class: 'chart', width: '720', height: '150', role: 'img',
    'aria-label': 'Накопление зелёным и сокращение красным между снимками'});
  const context = canvas.getContext('2d');
  const width = 720 / observed.length;
  context.fillStyle = '#2b363d';
  context.fillRect(0, 74, 720, 2);
  observed.forEach((row, index) => {
    const up = 66 * Number(row.up) / (maximum || 1);
    const down = 66 * Number(row.down) / (maximum || 1);
    const x = width * index + width / 4;
    const bar = Math.max(1, Math.min(18, width / 2));
    context.fillStyle = '#8ce0a1';
    context.fillRect(x, 74 - up, bar, up);
    context.fillStyle = '#ffa1a1';
    context.fillRect(x, 76, bar, down);
  });
  return el('div', {}, canvas, el('div', {class: 'legend'}, date(observed[0].time),
    'Пик за снимок: ' + xlmText(maximum), date(observed.at(-1).time)));
}

export function dashboard(summary, period) {
  const stats = summary.periods[period];
  const cards = el('div', {class: 'grid'},
    tile('Обнаружено держателей', number(summary.discovered)),
    tile('Киты выше порога', number(summary.active)),
    tile('Баланс китов, XLM', xlm(summary.total)),
    tile('Накопление, XLM', signedXlm(stats.up)),
    tile('Сокращение, XLM', signedXlm('-' + stats.down)),
    tile('Чистое изменение, XLM', signedXlm(stats.net)),
    tile('Крупных движений', number(stats.large)),
    tile('Новых китов', number(stats.new)),
    tile('Сигналов', el('span', {class: 'warning'}, number(stats.anomalies))),
    ...(summary.private_only ? [] : [tile('Приток на биржевые адреса, XLM', xlm(stats.markets?.inflow)),
    tile('Отток с биржевых адресов, XLM', xlm(stats.markets?.outflow)),
    tile('DEX · покупки XLM', el('span', {class: 'positive'}, xlm(stats.markets?.buy))),
    tile('DEX · продажи XLM', el('span', {class: 'negative'}, xlm(stats.markets?.sell)))]));
  const distribution = Object.entries(summary.categories).map(([name, count]) => el('div', {},
    el('span', {}, name), el('strong', {}, number(count)), el('meter', {min: 0, max: summary.active, value: count, 'aria-label': name})));
  return el('section', {}, el('h1', {}, 'Обзор'),
    el('p', {class: 'muted'}, 'Stellar Mainnet · статистика допущенных держателей'),
    cards,
    summary.candidates ? el('p', {class: 'muted'}, number(summary.candidates) + ' кандидатов проходят отдельную проверку.', ' ', el('a', {href: '#accumulation'}, 'Смотреть историю платежей')) : null,
    el('div', {class: 'panels'}, panel('Совокупный баланс китов', chart(stats.chart, xlmText)),
      panel('Категории держателей', el('div', {class: 'distribution'}, distribution.length ? distribution : 'Пока нет данных.'))),
    el('div', {class: 'panels'}, panel('Накопление и сокращение по снимкам', balanceFlows(stats.chart)),
      panel('Покрытие наблюдений', el('p', {class: 'muted'},
      'Начало сканирования: ' + date(summary.coverage) + ' UTC. Изменения рассчитаны по снимкам известных кошельков. ' +
      'Первый баланс нового адреса не засчитывается как накопление. Индексация всех держателей сети не выполняется.'))));
}
