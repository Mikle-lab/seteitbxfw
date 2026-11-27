import {xlm} from '../../shared/money.js';
import {account, date, el, number, panel, table, transaction} from '../../shared/ui.js';

export function inactivityText(status) {
  if (!status) return 'Недостаточно наблюдений';
  if (status.days === 0) return 'Менее суток';
  return number(status.days) + ' сут.';
}

export function interactionTable(rows, wallet) {
  const headers = wallet ? ['Контрагент'] : ['Адрес 1', 'Адрес 2'];
  return table([...headers, 'Транзакций', 'Дней с переводами', 'Сумма XLM', 'Последний перевод UTC', 'Примеры'],
    rows.map(row => [
      ...(wallet ? [account(row.left === wallet ? row.right : row.left)] : [account(row.left), account(row.right)]),
      number(row.transactions), number(row.days), xlm(row.amount), date(row.last),
      el('span', {}, row.examples.flatMap((hash, index) => [index ? ' · ' : '', transaction(hash)])),
    ]), 'Пока нет известных пар, удовлетворяющих критериям.');
}

export function interactionsView(data) {
  return el('section', {}, el('h1', {}, 'Повторные переводы'),
    el('p', {class: 'muted'}, 'За последние 30 дней. В выборку попадают пары отслеживаемых адресов с крупными прямыми переводами минимум в трёх транзакциях и в два разных дня UTC. Учитываются адреса без известных служебных и биржевых меток. Принадлежность адресов одному владельцу по этим данным установить нельзя.'),
    el('p', {class: 'muted'}, 'Операции просмотрены до ' + date(data.through) + ' UTC. Пар в архиве за период: ' + number(data.total) + '.'),
    panel('Наблюдаемые пары', interactionTable(data.pairs)));
}
