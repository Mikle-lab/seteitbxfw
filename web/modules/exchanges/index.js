import {el} from '../../shared/ui.js';
export const exchanges = () => el('section', {}, el('h1', {}, 'Биржи'),
  el('p', {}, 'В разработке для v0.2. Для расчёта потоков необходим реестр подтверждённых адресов бирж.'));
