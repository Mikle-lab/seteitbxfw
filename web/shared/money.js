import {date, el, number, signed} from './ui.js';

const usd = new Intl.NumberFormat('ru', {style: 'currency', currency: 'USD', maximumFractionDigits: 2});
const usdQuote = new Intl.NumberFormat('ru', {style: 'currency', currency: 'USD', maximumFractionDigits: 8});
const maxAge = 15 * 60 * 1000;
let spot = null;

export function currentQuote(quote) {
  const age = Date.now() - Date.parse(quote?.time);
  return Number(quote?.price) > 0 && age >= -60000 && age <= maxAge;
}

export function setSpot(quote) {
  spot = quote;
}

export function dollars(value) {
  return value == null ? '—' : usd.format(Number(value));
}

export function xlmText(value) {
  if (value == null) return '—';
  const text = number(value) + ' XLM';
  return currentQuote(spot) ? text + ' · ≈ ' + dollars(Number(value) * Number(spot.price)) : text;
}

export function xlm(value, withSign = false) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  return el('span', {class: 'xlm-value'}, withSign ? signed(value) : number(value),
    currentQuote(spot) ? el('span', {class: 'xlm-usd'}, '≈ ' + dollars(Number(value) * Number(spot.price))) : null);
}

export function signedXlm(value) {
  return xlm(value, true);
}

export function spotText(quote) {
  if (!currentQuote(quote)) return 'Курс XLM/USD недоступен или устарел';
  return '1 XLM ≈ ' + usdQuote.format(Number(quote.price)) +
    ' · Coinbase Exchange · ' + date(quote.time) + ' UTC';
}


export function portfolioTotal(summary) {
  if (!summary || summary.usd == null || !currentQuote({price: 1, time: summary.time})) return '—';
  const missing = summary.total - summary.valued;
  return el('span', {class: 'xlm-value'}, '≈ ' + dollars(summary.usd),
    missing ? el('span', {class: 'xlm-usd'}, 'Без оценки: ' + missing) : null);
}
