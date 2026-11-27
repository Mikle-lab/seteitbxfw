import {signedXlm} from '../../shared/money.js';
import {account, date, el, number} from '../../shared/ui.js';

const fractionalXlm = new Intl.NumberFormat('ru', {maximumFractionDigits: 7, signDisplay: 'exceptZero'});

function changeAmount(value) {
  const amount = Number(value);
  return amount && Math.abs(amount) < 0.01 ? fractionalXlm.format(amount) : signedXlm(value);
}

function privateWhales(balance) {
  const title = el('h2', {}, 'Частные киты');
  const candidates = el('a', {href: '#accumulation'}, 'Кандидаты на проверку');
  const whales = el('a', {href: '#whales'}, 'Открыть «Киты»');
  if (balance?.status === 'no_holders') {
    return el('section', {class: 'panel'}, title,
      el('p', {}, 'Нет подтверждённых держателей'), candidates);
  }
  if (!balance || balance.status === 'insufficient') {
    return el('section', {class: 'panel'}, title,
      el('p', {}, 'Недостаточно истории'),
      balance ? el('p', {class: 'muted'}, '0 из ' + number(balance.approved) +
        ' допущенных адресов имеют сопоставимые замеры') : null,
      el('p', {class: 'muted'}, 'Для выбранного периода нужны сопоставимые замеры у обеих границ.'), whales);
  }

  const partial = balance.status === 'partial';
  return el('section', {class: 'panel'}, title,
    partial ? el('p', {class: 'warning'}, 'Частичное покрытие. Результат относится только к адресам с сопоставимыми замерами.') : null,
    el('p', {}, el('strong', {}, 'Чистое изменение баланса, XLM'), ' ', changeAmount(balance.net)),
    el('p', {}, 'Увеличили баланс: ' + number(balance.increased) + ' · Сократили: ' + number(balance.decreased)),
    el('p', {class: 'muted'}, 'В расчёте ' + number(balance.measured) + ' из ' + number(balance.approved) +
      ' допущенных адресов · Замеры до ' + date(balance.observed_through) + ' UTC'),
    balance.largest ? el('p', {class: 'muted'}, 'Крупнейший вклад, XLM: ', changeAmount(balance.largest.delta),
      ' · ', account(balance.largest.address)) : null,
    whales);
}

export function dashboard(summary, period) {
  return el('section', {}, el('h1', {}, 'Обзор'),
    privateWhales(summary.periods[period].private_balance),
    el('p', {class: 'muted'}, summary.last_operation ? 'Последняя обработанная операция: ' +
      date(summary.last_operation) + ' UTC' : 'Время последней обработанной операции пока неизвестно.'));
}
