import {chart, date, el, number, panel, signed, tile} from '../../shared/ui.js';

export function dashboard(summary, period) {
  const stats = summary.periods[period];
  const cards = el('div', {class: 'grid'},
    tile('Обнаружено держателей', number(summary.discovered)),
    tile('Киты выше порога', number(summary.active)),
    tile('Баланс китов, XLM', number(summary.total)),
    tile('Накопление, XLM', signed(stats.up)),
    tile('Сокращение, XLM', signed('-' + stats.down)),
    tile('Чистое изменение, XLM', signed(stats.net)),
    tile('Крупных движений', number(stats.large)),
    tile('Новых китов', number(stats.new)),
    tile('Сигналов', el('span', {class: 'warning'}, number(stats.anomalies))));
  const distribution = Object.entries(summary.categories).map(([name, count]) => el('div', {},
    el('span', {}, name), el('strong', {}, number(count)), el('meter', {min: 0, max: summary.active, value: count, 'aria-label': name})));
  return el('section', {}, el('h1', {}, 'Обзор'),
    el('p', {class: 'muted'}, 'Stellar Mainnet · статистика обнаруженных адресов'),
    cards,
    el('div', {class: 'panels'}, panel('Совокупный баланс китов', chart(stats.chart)),
      panel('Категории держателей', el('div', {class: 'distribution'}, distribution.length ? distribution : 'Пока нет данных.'))),
    panel('Покрытие наблюдений', el('p', {class: 'muted'},
      'Начало сканирования: ' + date(summary.coverage) + ' UTC. Изменения рассчитаны по снимкам известных кошельков. ' +
      'Первый баланс нового адреса не засчитывается как накопление. Индексация всех держателей сети не выполняется.')));
}
