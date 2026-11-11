'use strict';

/* ================= помощники ================= */

const $ = (sel, root = document) => root.querySelector(sel);
const view = $('#view');
const dialog = $('#dialog');
const numberFormat = new Intl.NumberFormat('ru');
const num = (x) => numberFormat.format(x || 0);
const dayFormat = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short' });
const timeFormat = new Intl.DateTimeFormat('ru', { hour: '2-digit', minute: '2-digit' });
const utcDayFormat = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', timeZone: 'UTC' });

/** Собирает элемент. Данные попадают на страницу только как текст — разметку из них собрать нельзя. */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else if (key in el) el[key] = value;
    else el.setAttribute(key, value === true ? '' : value);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function svg(tag, attrs, ...kids) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs || {})) el.setAttribute(key, value);
  el.append(...kids);
  return el;
}

async function api(path, body) {
  const options = body === undefined
    ? {}
    : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Panel': '1' }, body: JSON.stringify(body) };
  let response;
  try {
    response = await fetch('/api/' + path, options);
  } catch (e) {
    throw new Error('Нет связи с ботом. Проверь интернет и что бот запущен.');
  }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    showGate();
    throw new Error(data.error || 'Нужно войти заново.');
  }
  if (!response.ok) throw new Error(data.error || 'Ошибка ' + response.status);
  return data;
}

function toast(message, isError) {
  const el = h('div', { class: 'toast' + (isError ? ' is-error' : '') }, message);
  $('#toasts').append(el);
  setTimeout(() => el.remove(), isError ? 6000 : 3500);
}

/** Выполняет действие по кнопке: блокирует её на время и показывает ошибку, если не вышло. */
async function run(button, action) {
  if (button) button.disabled = true;
  try {
    return await action();
  } catch (e) {
    toast(e.message, true);
    return undefined;
  } finally {
    if (button) button.disabled = false;
  }
}

function plural(n, one, few, many) {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b === 1) return one;
  if (b >= 2 && b <= 4) return few;
  return many;
}
const people = (n) => `${num(n)} ${plural(n, 'человек', 'человека', 'человек')}`;
const recipients = (n) => `${num(n)} ${plural(n, 'получателю', 'получателям', 'получателям')}`;

function delayLabel(minutes) {
  if (minutes % 1440 === 0) return `${minutes / 1440} дн.`;
  if (minutes % 60 === 0) return `${minutes / 60} ч`;
  return `${minutes} мин`;
}

function localInputValue(date) {
  const pad = (x) => String(x).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      // Без https браузер не даёт доступ к буферу обмена — копируем по старинке.
      const area = h('textarea', { value: text });
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.append(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    toast('Ссылка скопирована');
  } catch (e) {
    toast('Не получилось скопировать. Выдели ссылку и скопируй вручную.', true);
  }
}

/** Текст сообщения -> узлы страницы: **жирный**, __курсив__. */
function rich(text) {
  const fragment = document.createDocumentFragment();
  const pattern = /\*\*([\s\S]+?)\*\*|__([\s\S]+?)__/g;
  let last = 0;
  let match;
  while ((match = pattern.exec(text))) {
    fragment.append(text.slice(last, match.index));
    const el = document.createElement(match[1] !== undefined ? 'b' : 'i');
    el.append(rich(match[1] !== undefined ? match[1] : match[2]));
    fragment.append(el);
    last = pattern.lastIndex;
  }
  fragment.append(text.slice(last));
  return fragment;
}

/* ================= окно ================= */

function openDialog({ title, body, submitLabel, danger, extra, onSubmit }) {
  return new Promise((resolve) => {
    const submit = h('button', { class: 'btn ' + (danger ? 'btn-danger' : 'btn-primary'), type: 'submit' }, submitLabel || 'Сохранить');
    const close = (result) => {
      dialog.close();
      resolve(result);
    };
    const form = h('form', {
      onsubmit: async (event) => {
        event.preventDefault();
        const result = await run(submit, async () => (onSubmit ? onSubmit() : true));
        if (result !== undefined) close(result);
      },
    },
      h('div', { class: 'dialog-head' }, h('h2', {}, title)),
      h('div', { class: 'dialog-body' }, body),
      h('div', { class: 'dialog-foot' },
        extra ? extra(close) : null,
        h('div', { class: 'btn-row' },
          h('button', { class: 'btn', type: 'button', onclick: () => close(undefined) }, 'Отмена'),
          submit)));
    dialog.replaceChildren(form);
    dialog.oncancel = () => resolve(undefined);
    dialog.showModal();
  });
}

function confirmDialog(title, text, submitLabel, danger) {
  return openDialog({ title, body: h('p', {}, text), submitLabel, danger });
}

/* ================= вход и лампа «в эфире» ================= */

function showGate() {
  clearTimeout(statusTimer);
  document.body.className = 'gate';
  document.body.replaceChildren(
    h('main', { class: 'gate-box' },
      h('p', { class: 'gate-mark' }, 'Панель бота'),
      h('h1', {}, 'Вход по ссылке из бота'),
      h('p', {}, 'Открой своего бота в Telegram и отправь ему команду /panel — он пришлёт одноразовую ссылку для входа.')));
}

let statusTimer = null;
let statusKey = '';
let onStatusChange = null;

async function pollStatus() {
  clearTimeout(statusTimer);
  let delay = 6000;
  try {
    const status = await api('status');
    const lamp = $('#lamp');
    if (!lamp) return;
    $('#botName').textContent = status.bot ? '@' + status.bot : '';
    if (status.sending) {
      lamp.className = 'lamp is-live';
      $('#lampText').textContent = `В эфире · ${num(status.sending.done)} из ${num(status.sending.total)}`;
      delay = 2000;
    } else if (status.scheduled) {
      lamp.className = 'lamp is-scheduled';
      $('#lampText').textContent = `В очереди: ${status.scheduled}`;
    } else {
      lamp.className = 'lamp';
      $('#lampText').textContent = 'Эфир свободен';
    }
    const key = JSON.stringify([status.sending, status.scheduled]);
    if (key !== statusKey && statusKey && onStatusChange) onStatusChange();
    statusKey = key;
  } catch (e) {
    if (!$('#lamp')) return;
  }
  statusTimer = setTimeout(pollStatus, delay);
}

/* ================= сетка эфира (общая для обзора и рассылок) ================= */

const STATE_LABEL = { scheduled: 'Запланирована', sending: 'В эфире', done: 'Отправлена', cancelled: 'Отменена' };

function rundownItem(b, refresh) {
  const at = new Date((b.status === 'scheduled' ? b.scheduled_at : b.started_at || b.scheduled_at) * 1000);
  const meta = [b.audience];
  if (b.has_photo) meta.push('с картинкой');
  if (b.button_text) meta.push(`кнопка «${b.button_text}»`);
  const handled = b.delivered + b.blocked + b.failed;

  const side = [h('span', { class: 'state is-' + b.status }, STATE_LABEL[b.status] || b.status)];
  if (b.status === 'sending') side.push(h('span', { class: 'num muted' }, `${num(handled)} из ${num(b.total)}`));
  if (b.status === 'done' || b.status === 'cancelled') {
    if (b.started_at) side.push(h('span', { class: 'num muted' }, `дошло ${num(b.delivered)} из ${num(Math.max(b.total, handled))}`));
  }
  if (b.status === 'scheduled' || b.status === 'sending') {
    side.push(h('button', {
      class: 'btn btn-small btn-danger',
      type: 'button',
      onclick: async (event) => {
        const stop = b.status === 'sending';
        const ok = await confirmDialog(
          stop ? 'Остановить рассылку?' : 'Отменить рассылку?',
          stop ? 'Те, кто уже получил сообщение, его увидят. Остальным оно не придёт.' : 'Сообщение никому не уйдёт.',
          stop ? 'Остановить' : 'Отменить рассылку', true);
        if (!ok) return;
        await run(event.target, () => api(`broadcasts/${b.id}/cancel`, {}));
        toast(stop ? 'Рассылка остановлена' : 'Рассылка отменена');
        refresh();
        pollStatus();
      },
    }, b.status === 'sending' ? 'Остановить' : 'Отменить'));
  }

  const item = h('li', {},
    h('time', {}, h('b', {}, timeFormat.format(at)), dayFormat.format(at)),
    h('div', { class: 'what' }, h('p', {}, rich(b.text)), h('div', { class: 'meta' }, meta.join(' · '))),
    h('div', { class: 'side' }, side));
  if (b.status === 'sending') {
    const fill = h('i');
    fill.style.width = (b.total ? Math.min(100, (handled / b.total) * 100) : 0) + '%';
    item.append(h('div', { class: 'progress' }, fill));
  }
  return item;
}

/* ================= редактор сообщения ================= */

function messageForm({ lessons, withPhoto, value, onChange }) {
  const initial = value || {};
  const isLesson = (initial.button_target || '').startsWith('lesson:');
  const state = {
    text: initial.text || '',
    photo: '',
    photoUrl: '',
    buttonMode: initial.button_text ? (isLesson ? 'lesson' : 'url') : 'none',
    buttonText: initial.button_text || '',
    buttonUrl: isLesson ? '' : initial.button_target || '',
    buttonLesson: isLesson ? initial.button_target.slice(7) : lessons[0] ? String(lessons[0].id) : '',
  };
  const changed = () => onChange && onChange(state);
  const limit = () => (state.photo ? 1000 : 4000);

  const counter = h('span', { class: 'counter' });
  const updateCounter = () => {
    counter.textContent = `${state.text.length} / ${limit()}`;
    counter.className = 'counter' + (state.text.length > limit() ? ' is-over' : '');
  };
  const text = h('textarea', {
    rows: 6,
    value: state.text,
    placeholder: 'Привет, {имя}! Вышел новый урок…',
    oninput: () => { state.text = text.value; updateCounter(); changed(); },
  });

  const photoBox = h('div', { class: 'photo-pick' });
  const drawPhoto = () => {
    if (state.photo) {
      photoBox.replaceChildren(
        h('img', { src: state.photoUrl, alt: 'Картинка рассылки' }),
        h('button', {
          class: 'btn btn-small', type: 'button',
          onclick: () => { state.photo = ''; state.photoUrl = ''; drawPhoto(); updateCounter(); changed(); },
        }, 'Убрать картинку'));
      return;
    }
    const input = h('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp', hidden: true });
    const pick = h('button', { class: 'btn btn-small', type: 'button', onclick: () => input.click() }, 'Добавить картинку');
    input.addEventListener('change', () => {
      const file = input.files[0];
      if (!file) return;
      if (file.size > 10 * 1024 * 1024) { toast('Картинка должна быть не больше 10 МБ.', true); return; }
      run(pick, async () => {
        pick.textContent = 'Загружаю…';
        try {
          const dataUrl = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('Не получилось прочитать файл.'));
            reader.readAsDataURL(file);
          });
          const result = await api('photo', { data: String(dataUrl).split(',')[1] });
          state.photo = result.photo;
          state.photoUrl = URL.createObjectURL(file);
        } finally {
          pick.textContent = 'Добавить картинку';
        }
        drawPhoto(); updateCounter(); changed();
      });
    });
    photoBox.replaceChildren(pick, input, h('span', { class: 'hint' }, 'JPG, PNG или WebP до 10 МБ'));
  };

  const buttonFields = h('div', {});
  const drawButton = () => {
    buttonFields.replaceChildren();
    if (state.buttonMode === 'none') return;
    const label = h('input', {
      type: 'text', maxLength: 40, value: state.buttonText, placeholder: 'Смотреть урок',
      oninput: () => { state.buttonText = label.value; changed(); },
    });
    let target;
    if (state.buttonMode === 'url') {
      target = h('input', {
        type: 'text', value: state.buttonUrl, placeholder: 'https://…', inputMode: 'url',
        oninput: () => { state.buttonUrl = target.value; changed(); },
      });
    } else {
      target = h('select', { onchange: () => { state.buttonLesson = target.value; changed(); } },
        lessons.map((l) => h('option', { value: String(l.id), selected: String(l.id) === state.buttonLesson }, l.title)));
    }
    buttonFields.append(h('div', { class: 'field-row' },
      h('label', { class: 'field' }, h('span', {}, 'Надпись на кнопке'), label),
      h('label', { class: 'field' }, h('span', {}, state.buttonMode === 'url' ? 'Куда ведёт' : 'Какой урок открывает'), target)));
  };
  const modes = [['none', 'Без кнопки'], ['url', 'Ссылка']];
  if (lessons.length) modes.push(['lesson', 'Открыть урок']);
  const group = 'btnmode' + Math.random().toString(36).slice(2);
  const modeChoice = h('div', { class: 'choice' }, modes.map(([mode, title]) =>
    h('label', {},
      h('input', {
        type: 'radio', name: group, checked: state.buttonMode === mode,
        onchange: () => { state.buttonMode = mode; drawButton(); changed(); },
      }),
      h('span', {}, title))));

  updateCounter();
  drawButton();
  if (withPhoto) drawPhoto();

  const node = h('div', { class: 'stack' },
    h('label', { class: 'field' },
      h('span', {}, 'Текст сообщения'),
      text,
      counter,
      h('small', {}, '**жирный**, __курсив__. Напиши {имя} — бот подставит имя человека.')),
    withPhoto ? h('div', { class: 'field' }, h('span', {}, 'Картинка'), photoBox) : null,
    h('div', { class: 'field' }, h('span', {}, 'Кнопка под сообщением'), modeChoice),
    buttonFields);

  return {
    node,
    state,
    data() {
      const data = { text: state.text.trim(), photo: state.photo, button_text: '', button_target: '' };
      if (state.buttonMode !== 'none') {
        data.button_text = state.buttonText.trim();
        data.button_target = state.buttonMode === 'url' ? state.buttonUrl.trim() : 'lesson:' + state.buttonLesson;
      }
      return data;
    },
    reset() {
      Object.assign(state, { text: '', photo: '', photoUrl: '', buttonMode: 'none', buttonText: '', buttonUrl: '' });
      text.value = '';
      modeChoice.querySelector('input').checked = true;
      updateCounter(); drawButton();
      if (withPhoto) drawPhoto();
      changed();
    },
  };
}

function bubble(state) {
  const body = state.text.trim()
    ? h('p', {}, rich(state.text.replaceAll('{имя}', 'Аня')))
    : h('p', { class: 'is-empty' }, 'Здесь появится твоё сообщение');
  return h('div', {},
    h('div', { class: 'bubble' }, state.photoUrl ? h('img', { src: state.photoUrl, alt: '' }) : null, body),
    state.buttonMode !== 'none' && state.buttonText.trim() ? h('div', { class: 'bubble-btn' }, state.buttonText) : null);
}

/* ================= обзор ================= */

async function overview() {
  const data = await api('overview?tz=' + new Date().getTimezoneOffset());
  const refresh = () => current === 'overview' && route();
  onStatusChange = refresh;

  const queue = data.queue.slice().sort((a, b) => (a.status === 'sending' ? -1 : b.status === 'sending' ? 1 : a.scheduled_at - b.scheduled_at));
  const queuePanel = h('section', { class: 'panel' },
    h('div', { class: 'panel-head' },
      h('span', { class: 'label' }, 'Сетка эфира'),
      h('a', { class: 'btn btn-small', href: '#broadcasts' }, 'Новая рассылка')),
    queue.length
      ? h('ul', { class: 'rundown' }, queue.map((b) => rundownItem(b, refresh)))
      : h('div', { class: 'panel-body' }, h('p', { class: 'empty' }, 'В очереди пусто: сейчас ничего не отправляется и не запланировано.')));

  const figures = h('div', { class: 'figures' },
    [['Всего людей', data.users.total], ['Получают рассылки', data.active], ['Новых за сутки', data.users.day],
      ['Новых за 7 дней', data.users.week], ['Заблокировали бота', data.users.blocked]]
      .map(([label, value]) => h('div', { class: 'figure' }, h('span', { class: 'label' }, label), h('b', {}, num(value)))));

  const max = Math.max(1, ...data.daily.map((d) => d.n));
  const width = 100 / data.daily.length;
  const chart = svg('svg', { class: 'chart', viewBox: '0 0 100 40', preserveAspectRatio: 'none', role: 'img', 'aria-label': 'Новые пользователи по дням за 30 дней' },
    ...data.daily.map((d, i) => {
      const height = d.n ? Math.max(1.2, (d.n / max) * 38) : 0.6;
      const bar = svg('rect', { x: i * width + width * 0.14, y: 40 - height, width: width * 0.72, height, class: d.n ? '' : 'is-zero' });
      bar.append(svg('title', {}, `${utcDayFormat.format(new Date(d.day * 1000))}: ${d.n}`));
      return bar;
    }));
  const monthTotal = data.daily.reduce((sum, d) => sum + d.n, 0);
  const chartPanel = h('section', { class: 'panel' },
    h('div', { class: 'panel-head' },
      h('span', { class: 'label' }, 'Новые люди за 30 дней'),
      h('span', { class: 'num muted' }, `всего ${num(monthTotal)} · максимум ${num(max === 1 && !monthTotal ? 0 : max)} в день`)),
    h('div', { class: 'panel-body' }, chart,
      h('div', { class: 'chart-axis' },
        h('span', {}, utcDayFormat.format(new Date(data.daily[0].day * 1000))),
        h('span', {}, 'сегодня'))));

  const topOpens = Math.max(1, ...data.lessons.map((l) => l.total));
  const lessonsPanel = h('section', { class: 'panel' },
    h('div', { class: 'panel-head' }, h('span', { class: 'label' }, 'Уроки: сколько раз открыли')),
    h('div', { class: 'panel-body' }, data.lessons.length
      ? h('ul', { class: 'rows' }, data.lessons.map((l) => {
        const fill = h('i');
        fill.style.width = (l.total / topOpens) * 100 + '%';
        return h('li', {},
          h('span', { class: 'clip' }, l.title, l.hidden ? h('span', { class: 'tag' }, 'скрыт') : null),
          h('span', { class: 'num' }, num(l.total)),
          h('div', { class: 'bar' }, fill));
      }))
      : h('p', { class: 'empty' }, 'Уроков пока нет. ', h('a', { href: '#lessons' }, 'Добавить первый'))));

  const topSource = Math.max(1, ...data.sources.map((s) => s.n));
  const sourcesPanel = h('section', { class: 'panel' },
    h('div', { class: 'panel-head' }, h('span', { class: 'label' }, 'По каким ссылкам приходят')),
    h('div', { class: 'panel-body' }, data.sources.length
      ? h('ul', { class: 'rows' }, data.sources.map((s) => {
        const fill = h('i');
        fill.style.width = (s.n / topSource) * 100 + '%';
        return h('li', {}, h('code', { class: 'clip' }, s.source), h('span', { class: 'num' }, num(s.n)), h('div', { class: 'bar' }, fill));
      }))
      : h('p', { class: 'empty' }, 'Пока никто не пришёл по ссылке на урок. Ссылки для Instagram лежат в разделе «Уроки».')));

  view.replaceChildren(
    h('header', { class: 'view-head' }, h('div', {}, h('h1', {}, 'Обзор'))),
    queuePanel, figures, chartPanel,
    h('div', { class: 'cols' }, lessonsPanel, sourcesPanel));
}

/* ================= рассылки ================= */

async function broadcasts() {
  const data = await api('broadcasts');

  const preview = h('div', {});
  const form = messageForm({
    lessons: data.lessons,
    withPhoto: true,
    onChange: (state) => preview.replaceChildren(bubble(state)),
  });
  preview.replaceChildren(bubble(form.state));

  /* --- кому --- */
  const segment = { type: 'all' };
  const countLabel = h('span', { class: 'audience-count' }, 'Получат: ' + people(data.total));
  let audience = data.total;
  let countRequest = 0;
  const sendButton = h('button', { class: 'btn btn-primary', type: 'button' });
  const mode = { later: false };
  const whenInput = h('input', {
    type: 'datetime-local',
    value: localInputValue(new Date(new Date().setHours(24 + 10, 0, 0, 0))),
    min: localInputValue(new Date()),
  });
  const whenField = h('label', { class: 'field', hidden: true }, h('span', {}, 'Дата и время отправки'), whenInput);
  const updateSend = () => {
    sendButton.textContent = mode.later ? 'Запланировать' : `Отправить ${recipients(audience)}`;
  };
  const recount = async () => {
    const request = ++countRequest;
    try {
      const result = await api('audience', { segment });
      if (request !== countRequest) return;
      audience = result.count;
      countLabel.textContent = 'Получат: ' + people(audience);
    } catch (e) {
      if (request !== countRequest) return;
      countLabel.textContent = e.message;
    }
    updateSend();
  };
  const extra = h('div', {});
  const drawSegmentExtra = () => {
    extra.replaceChildren();
    if (segment.type === 'lesson' || segment.type === 'not_lesson') {
      segment.id = segment.id || (data.lessons[0] && data.lessons[0].id);
      const select = h('select', { onchange: () => { segment.id = Number(select.value); recount(); } },
        data.lessons.map((l) => h('option', { value: String(l.id), selected: l.id === segment.id }, l.title)));
      extra.append(h('label', { class: 'field' }, h('span', {}, 'Урок'), select));
    } else if (segment.type === 'source') {
      segment.value = segment.value || data.sources[0];
      const select = h('select', { onchange: () => { segment.value = select.value; recount(); } },
        data.sources.map((s) => h('option', { value: s, selected: s === segment.value }, s)));
      extra.append(h('label', { class: 'field' }, h('span', {}, 'Ссылка, по которой пришли'), select));
    } else if (segment.type === 'new') {
      segment.days = segment.days || 7;
      const input = h('input', {
        type: 'number', min: 1, max: 365, value: segment.days,
        oninput: () => { segment.days = Number(input.value); recount(); },
      });
      extra.append(h('label', { class: 'field' }, h('span', {}, 'За сколько последних дней'), input));
    }
  };
  const segmentOptions = [['all', 'Все пользователи'], ['no_views', 'Не открыли ни одного урока'], ['new', 'Новые за последние дни']];
  if (data.lessons.length) segmentOptions.push(['lesson', 'Открывали урок…'], ['not_lesson', 'Не открывали урок…']);
  if (data.sources.length) segmentOptions.push(['source', 'Пришли по ссылке…']);
  const segmentSelect = h('select', {
    onchange: () => {
      for (const key of Object.keys(segment)) delete segment[key];
      segment.type = segmentSelect.value;
      drawSegmentExtra();
      recount();
    },
  }, segmentOptions.map(([value, title]) => h('option', { value }, title)));

  /* --- когда --- */
  const whenChoice = h('div', { class: 'choice' }, [[false, 'Сейчас'], [true, 'В назначенное время']].map(([later, title]) =>
    h('label', {},
      h('input', {
        type: 'radio', name: 'when', checked: later === mode.later,
        onchange: () => { mode.later = later; whenField.hidden = !later; updateSend(); },
      }),
      h('span', {}, title))));

  /* --- отправка --- */
  const testButton = h('button', {
    class: 'btn', type: 'button',
    onclick: () => run(testButton, async () => {
      await api('broadcasts/test', form.data());
      toast('Тест отправлен тебе в Telegram');
    }),
  }, 'Отправить тест себе');

  sendButton.addEventListener('click', () => run(sendButton, async () => {
    const payload = { ...form.data(), segment };
    if (!payload.text) throw new Error('Напиши текст сообщения.');
    let when = null;
    if (mode.later) {
      when = new Date(whenInput.value);
      if (!whenInput.value || isNaN(when)) throw new Error('Выбери дату и время отправки.');
      if (when.getTime() < Date.now()) throw new Error('Это время уже прошло. Выбери время в будущем.');
      payload.scheduled_at = Math.floor(when.getTime() / 1000);
    }
    const ok = await confirmDialog(
      mode.later ? 'Запланировать рассылку?' : 'Отправить рассылку?',
      mode.later
        ? `Сообщение уйдёт ${dayFormat.format(when)} в ${timeFormat.format(when)}. До этого времени рассылку можно отменить.`
        : `Сообщение сразу уйдёт ${recipients(audience)}. Отозвать уже доставленные сообщения нельзя.`,
      mode.later ? 'Запланировать' : 'Отправить');
    if (!ok) return;
    await api('broadcasts', payload);
    toast(mode.later ? 'Рассылка запланирована' : 'Рассылка запущена');
    form.reset();
    refreshHistory();
    pollStatus();
  }));
  updateSend();

  /* --- история --- */
  const history = h('section', { class: 'panel' });
  const drawHistory = (items) => history.replaceChildren(
    h('div', { class: 'panel-head' }, h('span', { class: 'label' }, 'Сетка эфира: все рассылки')),
    items.length
      ? h('ul', { class: 'rundown' }, items.map((b) => rundownItem(b, refreshHistory)))
      : h('div', { class: 'panel-body' }, h('p', { class: 'empty' }, 'Рассылок ещё не было. Собери первую в форме выше.')));
  async function refreshHistory() {
    if (current !== 'broadcasts') return;
    try {
      drawHistory((await api('broadcasts')).items);
    } catch (e) { /* покажем при следующем обновлении */ }
  }
  onStatusChange = refreshHistory;
  drawHistory(data.items);

  view.replaceChildren(
    h('header', { class: 'view-head' },
      h('div', {}, h('h1', {}, 'Рассылки'), h('p', { class: 'lede' }, 'Сообщение всем или части людей — сразу или в назначенное время.'))),
    h('div', { class: 'compose' },
      h('section', { class: 'panel' }, h('div', { class: 'panel-body stack' },
        form.node,
        h('div', { class: 'field-row' },
          h('label', { class: 'field' }, h('span', {}, 'Кому отправить'), segmentSelect),
          extra),
        h('div', { class: 'field' }, h('span', {}, 'Когда отправить'), whenChoice),
        whenField,
        h('div', { class: 'send-bar' }, countLabel, h('div', { class: 'btn-row' }, testButton, sendButton)))),
      h('aside', { class: 'phone' }, h('span', { class: 'label' }, 'Так увидит получатель'), preview)),
    history);
}

/* ================= уроки ================= */

async function lessons() {
  const data = await api('lessons');
  const reload = () => current === 'lessons' && route();

  const edit = (lesson) => {
    const isNew = !lesson;
    const isFile = !isNew && lesson.kind !== 'url' && lesson.kind !== 'text';
    const state = { kind: isNew || isFile ? 'url' : lesson.kind };
    const title = h('input', { type: 'text', maxLength: 100, value: isNew ? '' : lesson.title, placeholder: 'Монтаж за 5 минут' });
    const description = h('textarea', { rows: 3, maxLength: 800, value: isNew ? '' : lesson.description, placeholder: 'О чём урок и что человек получит' });
    const url = h('input', { type: 'text', inputMode: 'url', placeholder: 'https://…', value: !isNew && lesson.kind === 'url' ? lesson.content : '' });
    const text = h('textarea', { rows: 6, maxLength: 3000, value: !isNew && lesson.kind === 'text' ? lesson.content : '' });
    const content = h('div', {});
    const drawContent = () => content.replaceChildren(state.kind === 'url'
      ? h('label', { class: 'field' }, h('span', {}, 'Ссылка на урок'), url, h('small', {}, 'YouTube, Google-диск, презентация — любая ссылка.'))
      : h('label', { class: 'field' }, h('span', {}, 'Текст урока'), text));
    drawContent();
    const kindChoice = h('div', { class: 'choice' }, [['url', 'Ссылка'], ['text', 'Текст']].map(([kind, label]) =>
      h('label', {},
        h('input', { type: 'radio', name: 'kind', checked: state.kind === kind, onchange: () => { state.kind = kind; drawContent(); } }),
        h('span', {}, label))));
    const code = h('input', { type: 'text', maxLength: 64, value: isNew ? '' : lesson.code });
    const hidden = h('input', { type: 'checkbox', checked: !isNew && lesson.hidden });

    const body = h('div', { class: 'stack' },
      h('label', { class: 'field' }, h('span', {}, 'Название'), title),
      h('label', { class: 'field' }, h('span', {}, 'Описание'), description),
      isFile
        ? h('div', { class: 'field' }, h('span', {}, 'Материал'),
          h('small', {}, `Сейчас это ${lesson.kind_label}. Заменить файл можно в Telegram: /admin → Уроки → этот урок → «Материал».`))
        : [h('div', { class: 'field' }, h('span', {}, 'Что в уроке'), kindChoice), h('div', { class: 'field' }, content)],
      isNew
        ? h('p', { class: 'hint field' }, 'Файл или видео уроком добавляются в Telegram: отправь боту /admin → «Добавить урок».')
        : [
          h('label', { class: 'field' }, h('span', {}, 'Код в ссылке на урок'), code,
            h('small', {}, 'Если поменять код, старая ссылка перестанет вести на этот урок.')),
          h('div', { class: 'field' }, h('label', { class: 'switch' }, hidden, h('i'), 'Скрыть урок от учеников')),
        ]);

    return openDialog({
      title: isNew ? 'Новый урок' : 'Урок',
      body,
      submitLabel: isNew ? 'Добавить урок' : 'Сохранить',
      extra: isNew ? null : (close) => h('button', {
        class: 'btn btn-danger', type: 'button',
        onclick: async (event) => {
          if (!window.confirm(`Удалить урок «${lesson.title}»? Это нельзя отменить.`)) return;
          const done = await run(event.target, () => api(`lessons/${lesson.id}/delete`, {}));
          if (done) { toast('Урок удалён'); close(true); }
        },
      }, 'Удалить'),
      onSubmit: async () => {
        const payload = { title: title.value, description: description.value, code: code.value, hidden: hidden.checked };
        if (!isFile) Object.assign(payload, { kind: state.kind, content: state.kind === 'url' ? url.value : text.value });
        await api(isNew ? 'lessons' : `lessons/${lesson.id}`, payload);
        toast(isNew ? 'Урок добавлен' : 'Урок сохранён');
        return true;
      },
    }).then((saved) => saved && reload());
  };

  const list = h('section', { class: 'panel' }, data.items.length
    ? data.items.map((lesson, index) => h('div', { class: 'lesson' + (lesson.hidden ? ' is-hidden' : '') },
      h('div', { class: 'order' },
        h('button', {
          type: 'button', 'aria-label': 'Выше', disabled: index === 0,
          onclick: (e) => run(e.target, async () => { await api(`lessons/${lesson.id}/move`, { dir: 'up' }); reload(); }),
        }, '▲'),
        h('button', {
          type: 'button', 'aria-label': 'Ниже', disabled: index === data.items.length - 1,
          onclick: (e) => run(e.target, async () => { await api(`lessons/${lesson.id}/move`, { dir: 'down' }); reload(); }),
        }, '▼')),
      h('div', {},
        h('div', { class: 'lesson-title' }, lesson.title, lesson.hidden ? h('span', { class: 'tag' }, 'скрыт') : null),
        h('div', { class: 'lesson-meta' }, `${lesson.kind_label} · открыли ${num(lesson.total)} ${plural(lesson.total, 'раз', 'раза', 'раз')} · ${people(lesson.people)}`)),
      h('div', { class: 'btn-row' },
        h('button', {
          class: 'btn btn-small', type: 'button',
          onclick: async (event) => {
            const ok = await confirmDialog('Уведомить всех об уроке?',
              `Всем пользователям придёт сообщение «Новый урок: ${lesson.title}» с кнопкой «Открыть урок».`, 'Отправить уведомление');
            if (!ok) return;
            const done = await run(event.target, () => api(`lessons/${lesson.id}/notify`, {}));
            if (done) { toast('Уведомление отправляется: ' + people(done.count)); pollStatus(); }
          },
        }, 'Уведомить'),
        h('button', { class: 'btn btn-small', type: 'button', onclick: () => edit(lesson) }, 'Изменить')),
      h('div', { class: 'lesson-link' },
        h('code', {}, lesson.link),
        h('button', { class: 'btn btn-small', type: 'button', onclick: () => copyText(lesson.link) }, 'Скопировать'))))
    : h('div', { class: 'panel-body' }, h('p', { class: 'empty' }, 'Уроков пока нет. Добавь первый — и получишь ссылку на него для Instagram.')));

  view.replaceChildren(
    h('header', { class: 'view-head' },
      h('div', {}, h('h1', {}, 'Уроки'), h('p', { class: 'lede' }, 'У каждого урока своя ссылка: вставь её в ChatPlace, и человек из Instagram сразу получит этот урок.')),
      h('button', { class: 'btn btn-primary', type: 'button', onclick: () => edit(null) }, 'Новый урок')),
    list);
}

/* ================= автосообщения ================= */

async function autos() {
  const data = await api('autos');
  const reload = () => current === 'autos' && route();

  const edit = (auto) => {
    const isNew = !auto;
    const minutes = isNew ? 1440 : auto.delay_minutes;
    const unit = minutes % 1440 === 0 ? 1440 : minutes % 60 === 0 ? 60 : 1;
    const amount = h('input', { type: 'number', min: 1, max: 9999, value: minutes / unit });
    const unitSelect = h('select', {}, [[1, 'минут'], [60, 'часов'], [1440, 'дней']].map(([value, label]) =>
      h('option', { value: String(value), selected: value === unit }, label)));
    const form = messageForm({ lessons: data.lessons, withPhoto: false, value: auto });
    const enabled = h('input', { type: 'checkbox', checked: isNew || auto.enabled });

    return openDialog({
      title: isNew ? 'Новое автосообщение' : 'Автосообщение',
      body: h('div', { class: 'stack' },
        h('div', { class: 'field-row' },
          h('label', { class: 'field' }, h('span', {}, 'Отправить через'), amount),
          h('label', { class: 'field' }, h('span', {}, 'после первого запуска бота'), unitSelect)),
        h('div', { class: 'field' }, form.node),
        h('div', { class: 'field' }, h('label', { class: 'switch' }, enabled, h('i'), 'Включено'))),
      submitLabel: isNew ? 'Добавить' : 'Сохранить',
      extra: isNew ? null : (close) => h('button', {
        class: 'btn btn-danger', type: 'button',
        onclick: async (event) => {
          if (!window.confirm('Удалить это автосообщение?')) return;
          const done = await run(event.target, () => api(`autos/${auto.id}/delete`, {}));
          if (done) { toast('Автосообщение удалено'); close(true); }
        },
      }, 'Удалить'),
      onSubmit: async () => {
        const payload = { ...form.data(), delay_minutes: Math.round(Number(amount.value) * Number(unitSelect.value)), enabled: enabled.checked };
        if (!isNew) payload.id = auto.id;
        await api('autos', payload);
        toast('Автосообщение сохранено');
        return true;
      },
    }).then((saved) => saved && reload());
  };

  const list = h('section', { class: 'panel' }, data.items.length
    ? h('ol', { class: 'chain' }, data.items.map((auto) => {
      const toggle = h('input', {
        type: 'checkbox', checked: auto.enabled,
        onchange: () => run(toggle, async () => {
          await api('autos', { ...auto, enabled: toggle.checked });
          toast(toggle.checked ? 'Автосообщение включено' : 'Автосообщение выключено');
          reload();
        }),
      });
      return h('li', { class: auto.enabled ? '' : 'is-off' },
        h('div', { class: 'when' }, '+ ' + delayLabel(auto.delay_minutes), h('small', {}, 'после старта')),
        h('div', {}, h('p', {}, rich(auto.text)),
          h('div', { class: 'lesson-meta' }, `получили: ${people(auto.sent)}` + (auto.button_text ? ` · кнопка «${auto.button_text}»` : ''))),
        h('div', { class: 'side' },
          h('label', { class: 'switch', title: 'Включить или выключить' }, toggle, h('i')),
          h('button', { class: 'btn btn-small', type: 'button', onclick: () => edit(auto) }, 'Изменить')));
    }))
    : h('div', { class: 'panel-body' }, h('p', { class: 'empty' }, 'Автосообщений пока нет. Например: через день после старта напомнить про урок, который человек ещё не открыл.')));

  view.replaceChildren(
    h('header', { class: 'view-head' },
      h('div', {}, h('h1', {}, 'Автосообщения'), h('p', { class: 'lede' }, 'Бот сам пишет каждому новому человеку через заданное время после первого запуска. Тем, кто пришёл раньше, чем ты добавил сообщение, оно не уходит.')),
      h('button', { class: 'btn btn-primary', type: 'button', onclick: () => edit(null) }, 'Новое автосообщение')),
    list);
}

/* ================= люди ================= */

async function users() {
  const state = { q: '', offset: 0, total: 0 };
  const body = h('tbody', {});
  const count = h('span', { class: 'num muted' });
  const more = h('button', { class: 'btn', type: 'button', hidden: true }, 'Показать ещё');
  const empty = h('p', { class: 'empty', hidden: true });

  const load = async (append) => {
    const data = await api(`users?q=${encodeURIComponent(state.q)}&offset=${state.offset}`);
    state.total = data.total;
    const rows = data.items.map((u) => {
      const joined = new Date(u.created_at * 1000);
      return h('tr', {},
        h('td', {}, u.first_name || '—'),
        h('td', { class: 'code' }, u.username ? '@' + u.username : '—'),
        h('td', { class: 'code' }, u.source || '—'),
        h('td', { class: 'num' }, `${dayFormat.format(joined)}, ${timeFormat.format(joined)}`),
        h('td', { class: 'num' }, num(u.lessons)),
        h('td', { class: u.blocked ? 'is-off' : 'muted' }, u.blocked ? 'заблокировал бота' : 'активен'));
    });
    if (append) body.append(...rows); else body.replaceChildren(...rows);
    state.offset += data.items.length;
    count.textContent = people(state.total);
    more.hidden = state.offset >= state.total;
    empty.hidden = state.total > 0;
    empty.textContent = state.q ? 'Никого не нашлось. Попробуй другое имя или username.' : 'Пока никто не запускал бота.';
  };

  let timer = null;
  const search = h('input', {
    type: 'search', placeholder: 'Имя, @username или код ссылки', 'aria-label': 'Поиск по людям',
    oninput: () => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = search.value.trim(); state.offset = 0; load(false).catch((e) => toast(e.message, true)); }, 300);
    },
  });
  more.addEventListener('click', () => run(more, () => load(true)));
  await load(false);

  view.replaceChildren(
    h('header', { class: 'view-head' },
      h('div', {}, h('h1', {}, 'Люди'), h('p', { class: 'lede' }, 'Все, кто запускал бота: откуда пришли и сколько уроков открыли.')),
      h('a', { class: 'btn', href: '/api/users/export', download: 'users.csv' }, 'Скачать таблицу (CSV)')),
    h('section', { class: 'panel' },
      h('div', { class: 'panel-body toolbar' }, search, count),
      h('div', { class: 'table-wrap' },
        h('table', {},
          h('thead', {}, h('tr', {}, ['Имя', 'Username', 'Пришёл по ссылке', 'Когда', 'Уроков', 'Статус'].map((t) => h('th', {}, t)))),
          body)),
      h('div', { class: 'panel-body' }, empty, more)));
}

/* ================= настройки ================= */

async function settings() {
  const data = await api('settings');
  const reload = () => current === 'settings' && route();

  const ref = h('input', { type: 'text', placeholder: '@username или ссылка на канал', 'aria-label': 'Канал' });
  const addButton = h('button', { class: 'btn btn-primary', type: 'submit' }, 'Подключить канал');
  const channelPanel = h('section', { class: 'panel' },
    h('div', { class: 'panel-head' }, h('span', { class: 'label' }, 'Обязательная подписка')),
    h('div', { class: 'panel-body stack' },
      data.channels.length
        ? h('div', {}, data.channels.map((c) => h('div', { class: 'channel' },
          h('div', { class: 'clip' }, h('strong', {}, c.title), ' ', h('span', { class: 'muted code' }, c.link)),
          h('button', {
            class: 'btn btn-small btn-danger', type: 'button',
            onclick: async (event) => {
              const ok = await confirmDialog('Убрать канал?', `Подписка на «${c.title}» больше не будет нужна для получения уроков.`, 'Убрать', true);
              if (!ok) return;
              await run(event.target, () => api(`channels/${c.chat_id}/delete`, {}));
              reload();
            },
          }, 'Убрать'))))
        : h('p', { class: 'empty' }, 'Сейчас уроки получают все. Подключи канал — и бот будет выдавать уроки только его подписчикам.'),
      h('form', {
        class: 'inline-form',
        onsubmit: (event) => {
          event.preventDefault();
          run(addButton, async () => {
            const result = await api('channels', { ref: ref.value });
            toast(`Канал «${result.title}» подключён`);
            reload();
          });
        },
      }, ref, addButton),
      h('p', { class: 'hint field' }, `Сначала добавь бота${data.bot ? ' @' + data.bot : ''} в канал администратором. Закрытый канал подключается в Telegram: /admin → «Обязательная подписка» → перешли боту пост из канала.`)));

  const welcome = h('textarea', { rows: 3, maxLength: 1500, value: data.welcome });
  const subText = h('textarea', { rows: 3, maxLength: 1500, value: data.sub_text });
  const saveTexts = h('button', {
    class: 'btn btn-primary', type: 'button',
    onclick: () => run(saveTexts, async () => {
      await api('settings', { welcome: welcome.value, sub_text: subText.value });
      toast('Тексты сохранены');
    }),
  }, 'Сохранить тексты');
  const textsPanel = h('section', { class: 'panel' },
    h('div', { class: 'panel-head' }, h('span', { class: 'label' }, 'Тексты бота')),
    h('div', { class: 'panel-body stack' },
      h('label', { class: 'field' }, h('span', {}, 'Приветствие над списком уроков'), welcome),
      h('label', { class: 'field' }, h('span', {}, 'Просьба подписаться на канал'), subText),
      h('div', { class: 'btn-row' }, saveTexts)));

  const protect = h('input', {
    type: 'checkbox', checked: data.protect,
    onchange: () => run(protect, async () => {
      await api('settings', { protect: protect.checked });
      toast(protect.checked ? 'Защита включена' : 'Защита выключена');
    }),
  });
  const protectPanel = h('section', { class: 'panel' },
    h('div', { class: 'panel-head' }, h('span', { class: 'label' }, 'Защита уроков')),
    h('div', { class: 'panel-body stack' },
      h('label', { class: 'switch' }, protect, h('i'), 'Запретить пересылать и сохранять уроки'),
      h('p', { class: 'hint field' }, 'Человек сможет смотреть урок в боте, но не перешлёт его другому и не сохранит файл.')));

  view.replaceChildren(
    h('header', { class: 'view-head' }, h('div', {}, h('h1', {}, 'Настройки'))),
    channelPanel, textsPanel, protectPanel);
}

/* ================= переходы между разделами ================= */

const views = { overview, broadcasts, lessons, autos, users, settings };
let current = '';
let routeId = 0;

async function route() {
  const name = location.hash.slice(1) in views ? location.hash.slice(1) : 'overview';
  const isSwitch = name !== current;
  const id = ++routeId;
  current = name;
  onStatusChange = null;
  for (const link of document.querySelectorAll('#nav a')) {
    if (link.dataset.view === name) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  if (isSwitch) {
    view.replaceChildren(h('p', { class: 'muted' }, 'Загружаю…'));
    window.scrollTo(0, 0);
  }
  try {
    await views[name]();
  } catch (e) {
    if (id !== routeId || !document.body.contains(view)) return;
    view.replaceChildren(
      h('header', { class: 'view-head' }, h('h1', {}, 'Не получилось загрузить')),
      h('section', { class: 'panel' }, h('div', { class: 'panel-body stack' },
        h('p', {}, e.message),
        h('div', { class: 'btn-row' }, h('button', { class: 'btn', type: 'button', onclick: route }, 'Повторить')))));
  }
}

async function start() {
  try {
    await api('status');
  } catch (e) {
    if (document.body.className === 'gate') return;
  }
  $('#shell').hidden = false;
  $('#logout').addEventListener('click', async () => {
    try { await api('logout', {}); } catch (e) { /* выходим в любом случае */ }
    showGate();
  });
  window.addEventListener('hashchange', route);
  pollStatus();
  route();
}

start();
