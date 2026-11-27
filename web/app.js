import {addressPattern, date, el, json, number} from './shared/ui.js';
import {dashboard} from './modules/dashboard/index.js';
import {whales} from './modules/whales/index.js';
import {wallet} from './modules/wallet/index.js';
import {filters as operationFilters, matches, operationTable} from './modules/transactions/index.js';
import {anomalyTable, filters as anomalyFilters} from './modules/anomalies/index.js';
import {watchlist} from './modules/watchlist/index.js';
import {exchanges} from './modules/exchanges/index.js';
import {dex} from './modules/dex/index.js';
import {interactionsView} from './modules/activity/index.js';
import {accumulationView} from './modules/accumulation/index.js';
import {setSpot, spotText, xlmText} from './shared/money.js';
import {trendView} from './modules/trends/index.js';

const view = document.querySelector('#view');
const status = document.querySelector('#status');
const notice = document.querySelector('#notice');
const refresh = document.querySelector('#refresh');
const periodSelect = document.querySelector('#period');
const hours = {'1h': 1, '24h': 24, '7d': 168, '30d': 720, '90d': 2160};
const whaleState = {sort: 'balance', exited: false, page: 0};
const ops = {page: 0, min: '', max: '', address: '', kind: '', direction: 'any'};
const anomalies = {page: 0, level: ''};
let trendWindow = '7d';
let accumulationWindow = '7';
let data, rendered, generation = 0, updateTime, cache = new Map(), refreshing = false;

function cutoff(summary, period) {
  if (!summary.updated || period === 'all') return summary.coverage ?? '';
  return new Date(Date.parse(summary.updated) - hours[period] * 3600000).toISOString().replace('.000', '');
}

function statusLine(summary) {
  if (!summary.updated) return 'Ожидается первое успешное сканирование';
  const freshness = Math.max(0, Math.floor((Date.now() - Date.parse(summary.updated)) / 60000));
  const state = summary.error > summary.updated ? 'Ошибка последнего сканирования' :
    summary.lag > 0 ? 'Догоняет сеть · ' + number(summary.lag) + ' реестров' :
    freshness > 20 ? 'Данные устарели' : 'Сканирование выполнено';
  return state + ' · ' + date(summary.updated) + ' UTC · ' + number(freshness) + ' мин · ' +
    number(summary.processed) + ' операций прочитано · интерфейс ' + date(updateTime) + ' UTC' +
    (summary.automatic ? ' · автосбор ' + date(summary.automatic) + ' UTC' :
      summary.scheduled ? ' · по расписанию ' + date(summary.scheduled) + ' UTC' : ' · запуск по расписанию пока не подтверждён') +
    (summary.fallback ? ' · резервный сбор ' + date(summary.fallback) + ' UTC' : '');
}

function cached(path, summary) {
  if (!cache.has(path)) {
    cache.set(path, json(path, summary.updated).catch(error => { cache.delete(path); throw error; }));
  }
  return cache.get(path);
}

async function feed(summary, period, type) {
  const time = cutoff(summary, period);
  const isOps = type === 'operations';
  const state = isOps ? ops : anomalies;
  const chunks = summary.sections[type].filter(segment => segment.day >= time.slice(0, 10));
  state.page = Math.min(state.page, Math.max(0, chunks.length - 1));
  const segment = chunks[state.page];
  const values = segment ? await cached(segment.path, summary) : [];
  const rows = isOps ? values.filter(row => matches(row, state, time)) :
    values.filter(row => row.time >= time && (!state.level || row.level === state.level));
  const pager = el('div', {class: 'paginator'},
    el('button', {disabled: state.page === 0 ? '' : null, onclick: () => { state.page--; render(); }}, 'Назад'),
    el('span', {class: 'muted'}, chunks.length ? `Страница ${state.page + 1} из ${chunks.length} · ${segment.day} UTC` : 'Страниц пока нет'),
    el('button', {disabled: state.page >= chunks.length - 1 ? '' : null, onclick: () => { state.page++; render(); }}, 'Далее'));
  return el('section', {}, el('h1', {}, isOps ? 'Крупные операции' : 'Аномалии'),
    isOps ? operationFilters(state, render) : anomalyFilters(state, render),
    isOps ? operationTable(rows, summary.labels) : anomalyTable(rows), pager);
}

async function section(source) {
  const [name, address] = (location.hash.slice(1) || 'overview').split('/');
  const {summary, holders} = source;
  const period = periodSelect.value;
  const routes = {
    overview: () => dashboard(summary, period),
    accumulation: async () => accumulationView(await cached('accumulation.json', summary), holders, accumulationWindow, value => {
      accumulationWindow = value;
      render();
    }),
    trends: async () => trendView(await cached('trends.json', summary), trendWindow, value => {
      trendWindow = value;
      render();
    }),
    interactions: async () => interactionsView(await cached('interactions.json', summary)),
    whales: () => whales(holders, period, whaleState, render),
    anomalies: () => feed(summary, period, 'anomalies'),
    transactions: () => feed(summary, period, 'operations'),
    exchanges: async () => exchanges((await cached('markets.json', summary)).exchanges, period, cutoff(summary, period), summary.labels),
    dex: async () => dex((await cached('markets.json', summary)).dex, period),
    watchlist: () => watchlist(holders, period, render),
    settings: () => el('section', {}, el('h1', {}, 'Настройки'), el('p', {}, 'Порог крупного движения: ' +
      xlmText(summary.threshold) + '. Порог и категории меняются в config.json репозитория.')),
    wallet: async () => holders.some(row => row.address === address) && addressPattern.test(address) ?
      wallet(await cached('wallets/' + address + '.json', summary), period, cutoff(summary, period), summary.labels) :
      el('section', {}, el('h1', {}, 'Кошелёк'), el('p', {}, 'У сборщика пока нет снимков этого адреса.'),
        addressPattern.test(address ?? '') ? el('a', {href: 'https://stellar.expert/explorer/public/account/' + address,
          target: '_blank', rel: 'noopener noreferrer'}, 'Stellar Expert') : null),
  };
  const selected = Object.hasOwn(routes, name) ? name : 'overview';
  return {selected, content: await routes[selected]()};
}

async function render() {
  if (!data) return;
  const ticket = ++generation;
  try {
    const result = await section(data);
    if (ticket === generation) commitView(result);
  } catch {
    if (ticket === generation) showNotice('Не удалось загрузить раздел. Предыдущий экран сохранён.');
  }
}

function showNotice(message) {
  notice.hidden = !message;
  notice.textContent = message || '';
}

function commitView(result) {
  rendered = result.selected;
  view.replaceChildren(result.content);
  for (const anchor of document.querySelectorAll('nav a')) {
    if (anchor.getAttribute('href') === '#' + rendered) anchor.setAttribute('aria-current', 'page');
    else anchor.removeAttribute('aria-current');
  }
  const incomplete = !data.summary.periods[periodSelect.value].complete;
  const coverageApplies = ['whales', 'wallet', 'anomalies', 'transactions'].includes(rendered);
  showNotice(incomplete && coverageApplies ? 'История за выбранный период пока неполная.' : '');
  status.textContent = statusLine(data.summary);
  document.querySelector('#spot').textContent = spotText(data.summary.spot_usd);
}

async function load() {
  if (refreshing) return;
  refreshing = true;
  refresh.disabled = true;
  refresh.textContent = 'Обновление…';
  const priorCache = cache;
  try {
    const summary = await json('summary.json');
    if (summary.schema !== 1) throw new Error('Unsupported data schema');
    const holders = await json('whales.json', summary.updated);
    cache = new Map();
    setSpot(summary.spot_usd);
    let result;
    let ticket;
    do {
      ticket = generation;
      result = await section({summary, holders});
    } while (ticket !== generation);
    data = {summary, holders};
    updateTime = new Date().toISOString();
    commitView(result);
  } catch {
    cache = priorCache;
    setSpot(data?.summary.spot_usd);
    if (!data) status.textContent = 'Данные недоступны';
    showNotice(data ? 'Не удалось обновить данные. Показана предыдущая версия.' : 'Не удалось загрузить опубликованные данные.');
  } finally {
    refreshing = false;
    refresh.disabled = false;
    refresh.textContent = 'Обновить';
  }
}

periodSelect.addEventListener('change', () => { ops.page = 0; anomalies.page = 0; render(); });
window.addEventListener('hashchange', () => { generation++; render(); });
refresh.addEventListener('click', load);
load();
