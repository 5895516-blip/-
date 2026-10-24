const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType } = require('docx');

const [randPath, dataPath, outDir] = process.argv.slice(2);
const R = JSON.parse(fs.readFileSync(randPath, 'utf8'));
const D = dataPath && fs.existsSync(dataPath) ? JSON.parse(fs.readFileSync(dataPath, 'utf8')) : {};

const pad4 = n => String(n).padStart(4, '0');
const num = (x, d = 2) => {
  if (x === null || x === undefined) return '___';
  const r = Math.round(x * 10 ** d) / 10 ** d;
  return (Number.isInteger(r) ? String(r) : r.toFixed(d).replace(/0+$/, '')).replace('.', ',');
};

// Чтение таблицы: последовательность ячеек начиная со стартовой точки
function cells(table, start, byColumn) {
  const out = [];
  if (byColumn) {
    for (let k = 0; k < 7; k++) {
      const c = (start - 1 + k) % 7;
      for (let r = 0; r < 10; r++) out.push({ v: table[r][c], r: r + 1, c: c + 1 });
    }
  } else {
    for (let k = 0; k < 10; k++) {
      const r = (start - 1 + k) % 10;
      for (let c = 0; c < 7; c++) out.push({ v: table[r][c], r: r + 1, c: c + 1 });
    }
  }
  return out;
}

function select(seq, pick, need, max) {
  const steps = [], got = [];
  let i = 0;
  while (got.length < need) {
    const cell = seq[i++];
    const raw = pick(cell.v);
    const n = raw === 0 ? max : raw;
    const rep = got.includes(n);
    if (!rep) got.push(n);
    steps.push({ ...cell, n, raw, rep });
  }
  return { steps, got, next: i };
}

function solve(who, byColumn, pick1, pick2) {
  const { table, start } = R[who];
  const seq = cells(table, start, byColumn);
  const t1 = select(seq, pick1, 10, 100);
  const sample10 = [...t1.got].sort((a, b) => a - b);
  const t2 = select(seq.slice(t1.next), pick2, 3, 10);
  const chosen = t2.got.map(pos => sample10[pos - 1]);
  const vals = (D[who] && D[who].values) || null;
  const v = n => (vals ? Number(vals[String(n)]) : null);
  const sum10 = vals ? sample10.reduce((s, n) => s + v(n), 0) : null;
  const mean10 = vals ? sum10 / 10 : null;
  const sum3 = vals ? chosen.reduce((s, n) => s + v(n), 0) : null;
  const mean3 = vals ? sum3 / 3 : null;
  let means = null;
  if (vals) {
    means = [];
    for (let a = 0; a < 10; a++) for (let b = a + 1; b < 10; b++) for (let c = b + 1; c < 10; c++)
      means.push((v(sample10[a]) + v(sample10[b]) + v(sample10[c])) / 3);
  }
  return {
    table, start, t1, sample10, t2, chosen, v, sum10, mean10, sum3, mean3, means,
    indicator: (D[who] && D[who].indicator) || null,
    sumMeans: means ? means.reduce((s, x) => s + x, 0) : null,
    minMean: means ? Math.min(...means) : null,
    maxMean: means ? Math.max(...means) : null,
  };
}

// ---------- простые строительные блоки ----------
function mk(font, size, spacing, align) {
  const p = (text, opts = {}) => new Paragraph({
    alignment: opts.align || align,
    spacing: { after: opts.after ?? spacing.after, line: spacing.line },
    indent: opts.indent ? { firstLine: opts.indent } : undefined,
    children: [new TextRun({ text, font, size })],
  });
  const table = (rows, widths) => new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map(row => new TableRow({
      children: row.map((t, i) => new TableCell({
        width: { size: widths[i], type: WidthType.DXA },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0, line: 240 },
          children: [new TextRun({ text: String(t), font, size })] })],
      })),
    })),
  });
  return { p, table };
}

function save(children, file) {
  const doc = new Document({ sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1701, right: 850 } } },
    children,
  }] });
  return Packer.toBuffer(doc).then(b => fs.writeFileSync(path.join(outDir, file), b));
}

// ---------- Антон Тальян ----------
function anton() {
  const S = solve('anton', true, x => x % 100, x => x % 10);
  const { p, table } = mk('Times New Roman', 28, { after: 0, line: 360 }, AlignmentType.LEFT);
  const blank = () => p('');
  const out = [];
  out.push(p('Вариант 1'), p('Тальян Антон'), blank());

  out.push(p('Задача 1'), blank());
  out.push(p('Обследуются предприятия. Необходимо, используя таблицу случайных чисел (4-разрядный набор чисел), методом прямой реализации (простая случайная выборка без возвращения) провести 10% отбор предприятий из 100 предприятий.'), blank());
  out.push(p('Решение:'));
  out.push(p('Всего N = 100 предприятий, отбор 10%, значит объем выборки n = 100 · 0,1 = 10 предприятий.'));
  out.push(p('Выборка бесповторная, поэтому если номер повторяется, его пропускаем.'));
  out.push(p('Для отбора использую таблицу случайных четырехзначных чисел. Номера предприятий от 1 до 100, поэтому из каждого числа беру две последние цифры (00 считаю как 100).'), blank());
  out.push(p('Таблица случайных чисел'));
  out.push(table([[ '', 1, 2, 3, 4, 5, 6, 7 ], ...S.table.map((r, i) => [i + 1, ...r.map(pad4)])],
    [700, 1150, 1150, 1150, 1150, 1150, 1150, 1150]));
  out.push(blank());
  const lastCol = S.t1.steps[S.t1.steps.length - 1].c;
  out.push(p(`Начальную точку выбрал случайно из чисел от 1 до 7, выпало ${S.start}. Начинаю с ${S.start}-го столбца и читаю числа сверху вниз` +
    (lastCol !== S.start ? `, когда столбец закончился, перешел на ${lastCol}-й столбец.` : '.')), blank());
  out.push(table([['Случайное число', 'Две последние цифры', 'Результат'],
    ...S.t1.steps.map(s => [pad4(s.v), String(s.n % 100).padStart(2, '0'), s.rep ? 'повтор, пропускаю' : `предприятие № ${s.n}`])],
    [2800, 2800, 3700]));
  out.push(blank());
  out.push(p(`Ответ: в выборку попали предприятия № ${S.sample10.join(', ')}.`), blank());

  out.push(p('Задача 2'), blank());
  out.push(p('По данным приложения 1 следует методом случайного бесповторного отбора сформировать выборку 3 предприятий по одному из показателей работы. Рассчитать количество сочетаний отбора, рассчитать среднее по выборке и проверить его на несмещенность по сравнению с отобранными в задаче 1 предприятиями.'), blank());
  out.push(p('Решение:'));
  out.push(p(`Фамилия начинается на букву Т, поэтому беру колонку 14 табл. 1 приложения 1 (${S.indicator || '___'}).`));
  out.push(p('Генеральная совокупность – 10 предприятий, которые отобраны в задаче 1 (N = 10). Из них нужно отобрать n = 3 предприятия.'), blank());
  out.push(p('Значения показателя:'));
  out.push(table([['№ по порядку', '№ предприятия', 'Значение'],
    ...S.sample10.map((n, i) => [i + 1, n, num(S.v(n))]), ['', 'Сумма', num(S.sum10)]], [2400, 2900, 2900]));
  out.push(blank());
  out.push(p(`Средняя по 10 предприятиям: Хср = ${num(S.sum10)} / 10 = ${num(S.mean10)}`), blank());
  out.push(p('Количество сочетаний (сколько разных выборок по 3 предприятия можно составить из 10):'));
  out.push(p('C = N! / (n! · (N – n)!) = 10! / (3! · 7!) = (10 · 9 · 8) / (1 · 2 · 3) = 720 / 6 = 120'), blank());
  const st = S.t2.steps[0];
  out.push(p(`Отбор 3 предприятий: продолжаю читать таблицу случайных чисел с того места, где остановился (${st.c} столбец, ${st.r} строка). Беру последнюю цифру числа – это номер по порядку в таблице выше (0 = 10):`));
  S.t2.steps.forEach(s => out.push(p(s.rep ? `${pad4(s.v)} – ${s.n} – повтор, пропускаю` :
    `${pad4(s.v)} – ${s.raw === 0 ? '0 (= 10)' : s.n} – предприятие № ${S.sample10[s.n - 1]}`)));
  out.push(p(`Выборка: предприятия № ${S.chosen.join(', ')}.`), blank());
  out.push(p(`Средняя по выборке: хср = (${S.chosen.map(n => num(S.v(n))).join(' + ')}) / 3 = ${num(S.sum3)} / 3 = ${num(S.mean3)}`), blank());
  out.push(p('Проверка на несмещенность.'));
  out.push(p('Выборочная средняя несмещенная, если среднее из средних всех возможных выборок равно средней по генеральной совокупности: M(хср) = Хср.'));
  out.push(p('Каждое предприятие попадает в C(9; 2) = (9 · 8) / 2 = 36 выборок из 120. Поэтому сумма средних всех 120 выборок:'));
  out.push(p(`36 · Σx / 3 = 12 · Σx = 12 · ${num(S.sum10)} = ${num(S.sumMeans)}`));
  out.push(p(`M(хср) = ${num(S.sumMeans)} / 120 = ${num(S.sumMeans === null ? null : S.sumMeans / 120)}`));
  out.push(p(`Хср = ${num(S.mean10)}, M(хср) = Хср, значит средняя по выборке – несмещенная оценка.`), blank());
  out.push(p(`Наша выборка отличается от генеральной средней на ${num(S.mean3)} – ${num(S.mean10)} = ${num(S.mean3 === null ? null : S.mean3 - S.mean10)}` +
    (S.means ? ` (средние разных выборок колеблются от ${num(S.minMean)} до ${num(S.maxMean)}).` : '.') +
    ' Это случайная ошибка выборки, она есть из-за того, что взяли только 3 предприятия из 10. В среднем по всем 120 выборкам ошибка равна нулю, т.е. систематической ошибки нет.'));
  return save(out, 'Тальян_Антон_Вариант_1.docx');
}

// ---------- Максим Вершков ----------
function maxim() {
  const S = solve('maxim', false, x => Math.floor(x / 100), x => Math.floor(x / 1000));
  const { p, table } = mk('Calibri', 24, { after: 120, line: 276 }, AlignmentType.JUSTIFIED);
  const out = [];
  out.push(p('Вершков Максим, вариант 1', { align: AlignmentType.RIGHT, after: 240 }));

  out.push(p('Задача 1.'));
  out.push(p('Всего 100 предприятий, нужно отобрать 10%, т.е. 100 · 10 / 100 = 10 предприятий.'));
  out.push(p('Метод прямой реализации – это простая случайная выборка без возвращения: одно и то же предприятие не может попасть в выборку два раза.'));
  out.push(p('Для отбора взял таблицу случайных чисел (четырехзначные числа):'));
  out.push(table([[ 'строка', 1, 2, 3, 4, 5, 6, 7 ], ...S.table.map((r, i) => [i + 1, ...r.map(pad4)])],
    [900, 1100, 1100, 1100, 1100, 1100, 1100, 1100]));
  out.push(p('', { after: 0 }));
  out.push(p(`Начальную точку выбрал случайно от 1 до 7 – получилось ${S.start}. Начинаю с ${S.start}-й строки и читаю числа слева направо. Из каждого числа беру первые две цифры – это номер предприятия (если 00, то это 100).`));
  const rows = {};
  S.t1.steps.forEach(s => (rows[s.r] = rows[s.r] || []).push(`${pad4(s.v)} – ${s.rep ? 'повтор' : s.n}`));
  Object.keys(rows).sort((a, b) => ((a - S.start + 10) % 10) - ((b - S.start + 10) % 10))
    .forEach(r => out.push(p(`${r} строка: ${rows[r].join(', ')}`, { after: 0 })));
  out.push(p('', { after: 0 }));
  const reps = S.t1.steps.filter(s => s.rep).length;
  out.push(p(reps ? `Повторы пропускал, набрал 10 номеров.` : 'Повторов не было, сразу набрал 10 номеров.'));
  out.push(p(`Выборка (по возрастанию): ${S.sample10.join(', ')}.`, { after: 240 }));

  out.push(p('Задача 2.'));
  out.push(p(`Фамилия Вершков – буква В, по таблице это колонка 2 табл. 1 приложения 1 (${S.indicator || '___'}). Из 10 предприятий задачи 1 нужно случайно без повторения отобрать 3.`));
  out.push(p('Количество сочетаний:'));
  out.push(p('C = 10! / (3! · 7!) = 3628800 / (6 · 5040) = 120 вариантов выборки.'));
  out.push(p('Значения показателя по предприятиям из задачи 1:'));
  out.push(table([['№', ...S.sample10], ['x', ...S.sample10.map(n => num(S.v(n)))]],
    [900, ...Array(10).fill(840)]));
  out.push(p('', { after: 0 }));
  out.push(p(`Σx = ${num(S.sum10)}, средняя по 10 предприятиям x̄ген = ${num(S.sum10)} / 10 = ${num(S.mean10)}.`));
  const st = S.t2.steps[0];
  out.push(p(`Для выбора трех предприятий продолжил ту же таблицу (${st.r} строка, ${st.c} число) и брал первую цифру – это порядковый номер в списке (0 → 10):`));
  out.push(p(S.t2.steps.map(s => `${pad4(s.v)} → ${s.raw === 0 ? '0 → 10' : s.n}${s.rep ? ' (повтор)' : ` → № ${S.sample10[s.n - 1]}`}`).join('; ') + '.'));
  out.push(p(`В выборку попали предприятия № ${S.chosen.join(', ')}.`));
  out.push(p(`x̄выб = (${S.chosen.map(n => num(S.v(n))).join(' + ')}) / 3 = ${num(S.mean3)}.`));
  out.push(p('Проверка на несмещенность: оценка несмещенная, если ее математическое ожидание (среднее по всем возможным выборкам) равно генеральной средней.'));
  out.push(p(`Всего 120 выборок, каждое предприятие входит в C(9,2) = 36 из них. Среднее из всех выборочных средних = (36 / 3 · Σx) / 120 = Σx / 10 = ${num(S.sum10)} / 10 = ${num(S.sumMeans === null ? null : S.sumMeans / 120)}, это равно x̄ген = ${num(S.mean10)}. Значит выборочная средняя несмещенная.`));
  out.push(p(`Наша выборка отличается от генеральной средней на ${num(S.mean3 === null ? null : S.mean3 - S.mean10)}` +
    (S.means ? ` (у всех 120 выборок средняя от ${num(S.minMean)} до ${num(S.maxMean)})` : '') +
    ' – это случайная ошибка из-за маленькой выборки, а не систематическая.'));
  return save(out, 'Вершков_Максим_Вариант_1.docx');
}

Promise.all([anton(), maxim()]).then(() => console.log('done'));
