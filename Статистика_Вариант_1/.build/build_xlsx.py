import json, sys, itertools
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side, Alignment
from openpyxl.utils import get_column_letter as L

rand_path, out_dir = sys.argv[1], sys.argv[2]
data_path = sys.argv[3] if len(sys.argv) > 3 else None
R = json.load(open(rand_path))
D = json.load(open(data_path)) if data_path else {}

def cells(table, start, by_column):
    out = []
    if by_column:
        for k in range(7):
            c = (start - 1 + k) % 7
            for r in range(10):
                out.append((r, c))
    else:
        for k in range(10):
            r = (start - 1 + k) % 10
            for c in range(7):
                out.append((r, c))
    return out

def select(table, seq, pick, need, mx):
    steps, got, i = [], [], 0
    while len(got) < need:
        r, c = seq[i]; i += 1
        raw = pick(table[r][c]); n = mx if raw == 0 else raw
        rep = n in got
        if not rep: got.append(n)
        steps.append((r, c, n, rep))
    return steps, got, i

thin = Side(style='thin')
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)

def fit(wb):
    for ws in wb.worksheets:
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0

def styler(ws, font):
    def put(ref, val, box=False, fmt=None, center=None):
        c = ws[ref]; c.value = val; c.font = font
        if box: c.border = BOX
        if center or (center is None and box): c.alignment = CENTER
        if fmt: c.number_format = fmt
        return c
    return put

combos = list(itertools.combinations(range(1, 11), 3))

# ================= Тальян Антон =================
def anton():
    who = 'anton'; table, start = R[who]['table'], R[who]['start']
    seq = cells(table, start, True)
    t1, got1, nxt = select(table, seq, lambda x: x % 100, 10, 100)
    t2, got2, _ = select(table, seq[nxt:], lambda x: x % 10, 3, 10)
    assert not any(s[3] for s in t2)
    vals = D.get(who, {}).get('values')
    f = Font(name='Times New Roman', size=12)
    wb = Workbook()

    ws = wb.active; ws.title = 'Задача 1'; put = styler(ws, f)
    put('A1', 'Вариант 1. Тальян Антон')
    put('A2', 'Задача 1. Отбор 10% предприятий из 100 методом прямой реализации (простая случайная выборка без возвращения)')
    put('A4', 'N ='); put('B4', 100)
    put('A5', 'доля отбора'); put('B5', 0.1, fmt='0%')
    put('A6', 'n ='); put('B6', '=B4*B5')
    put('A8', 'Таблица случайных чисел')
    put('A9', '', box=True)
    for c in range(7): put(f'{L(c+2)}9', c + 1, box=True)
    for r in range(10):
        put(f'A{10+r}', r + 1, box=True)
        for c in range(7): put(f'{L(c+2)}{10+r}', table[r][c], box=True, fmt='0000')
    put('A21', 'Начальный столбец (выбран случайно от 1 до 7):'); put('G21', start)
    put('A22', 'Читаем столбец сверху вниз, когда он кончается - следующий столбец. Берем две последние цифры числа (00 = 100), повторы пропускаем.')
    hdr = ['№ шага', 'Случайное число', 'Две последние цифры', 'Результат', 'В выборку']
    for i, h in enumerate(hdr): put(f'{L(i+1)}24', h, box=True)
    first = 25
    for k, (r, c, n, rep) in enumerate(t1):
        row = first + k
        put(f'A{row}', k + 1, box=True)
        put(f'B{row}', f'={L(c+2)}{10+r}', box=True, fmt='0000')
        put(f'C{row}', f'=IF(MOD(B{row},100)=0,100,MOD(B{row},100))', box=True)
        put(f'D{row}', f'=IF(COUNTIF(C${first-1}:C{row-1},C{row})>0,"повтор, пропуск","отобрано")', box=True)
        put(f'E{row}', f'=IF(D{row}="отобрано",C{row},"")', box=True)
    last = first + len(t1) - 1
    s0 = last + 2
    put(f'A{s0}', 'Выборка (по возрастанию):')
    put(f'A{s0+1}', '№ п/п', box=True); put(f'B{s0+1}', '№ предприятия', box=True)
    for k in range(10):
        put(f'A{s0+2+k}', k + 1, box=True)
        put(f'B{s0+2+k}', f'=SMALL($E${first}:$E${last},A{s0+2+k})', box=True)
    put(f'A{s0+13}', 'Отобрано предприятий:'); put(f'C{s0+13}', f'=COUNT(B{s0+2}:B{s0+11})')
    put(f'A{s0+14}', 'Доля отбора:'); put(f'C{s0+14}', f'=C{s0+13}/B4', fmt='0%')
    ws.column_dimensions['A'].width = 13
    for col in 'BCDE': ws.column_dimensions[col].width = 16
    for col in 'FGH': ws.column_dimensions[col].width = 9
    sorted_ref = lambda k: f"='Задача 1'!B{s0+2+k}"

    ws = wb.create_sheet('Задача 2'); put = styler(ws, f)
    put('A1', 'Задача 2')
    put('A2', 'Фамилия на букву Т - колонка 14 табл. 1 приложения 1')
    put('A3', 'Генеральная совокупность - 10 предприятий из задачи 1 (N = 10), отбираем n = 3 без повторения')
    for i, h in enumerate(['№ п/п', '№ предприятия', 'Значение (колонка 14)']): put(f'{L(i+1)}5', h, box=True)
    for k in range(10):
        put(f'A{6+k}', k + 1, box=True)
        put(f'B{6+k}', sorted_ref(k), box=True)
        n = sorted(got1)[k]
        put(f'C{6+k}', vals[str(n)] if vals else None, box=True)
    put('D6', '<- значения из приложения 1')
    put('B16', 'Сумма', box=True); put('C16', '=SUM(C6:C15)', box=True)
    put('B17', 'Хср', box=True); put('C17', '=C16/10', box=True, fmt='0.00')
    put('A19', 'Количество сочетаний C(10;3) ='); put('E19', '=COMBIN(10,3)')
    put('A20', 'то же через факториалы 10!/(3!*7!) ='); put('E20', '=FACT(10)/(FACT(3)*FACT(7))')
    r0, c0 = t2[0][0], t2[0][1]
    put('A22', f'Отбор 3 предприятий: продолжаем таблицу случайных чисел ({c0+1} столбец, {r0+1} строка), последняя цифра = № п/п (0 = 10)')
    for i, h in enumerate(['Случайное число', 'Последняя цифра', '№ п/п', '№ предприятия', 'Значение']): put(f'{L(i+1)}23', h, box=True)
    for k, (r, c, n, rep) in enumerate(t2):
        row = 24 + k
        put(f'A{row}', f"='Задача 1'!{L(c+2)}{10+r}", box=True, fmt='0000')
        put(f'B{row}', f'=MOD(A{row},10)', box=True)
        put(f'C{row}', f'=IF(B{row}=0,10,B{row})', box=True)
        put(f'D{row}', f'=INDEX($B$6:$B$15,C{row})', box=True)
        put(f'E{row}', f'=INDEX($C$6:$C$15,C{row})', box=True)
    put('D27', 'Сумма', box=True); put('E27', '=SUM(E24:E26)', box=True)
    put('D28', 'хср', box=True); put('E28', '=E27/3', box=True, fmt='0.00')
    put('D29', 'хср - Хср', box=True); put('E29', '=E28-C17', box=True, fmt='0.00')
    put('A31', 'Проверка на несмещенность (все 120 выборок в столбцах H:M)')
    put('A32', 'Среднее из 120 выборочных средних M(хср) ='); put('E32', '=AVERAGE(M3:M122)', fmt='0.00')
    put('A33', 'Генеральная средняя Хср ='); put('E33', '=C17', fmt='0.00')
    put('A34', 'Каждое предприятие входит в C(9;2) ='); put('E34', '=COMBIN(9,2)')
    put('A35', 'Средние выборок: от'); put('C35', '=MIN(M3:M122)', fmt='0.00'); put('D35', 'до', center=True); put('E35', '=MAX(M3:M122)', fmt='0.00')
    put('A36', 'Вывод:')
    put('B36', '=IF(COUNT(C6:C15)<10,"нужно вписать значения из приложения 1",IF(ABS(E32-E33)<0.000001,"M(хср) = Хср, значит выборочная средняя - несмещенная оценка","не совпадает"))')
    put('H1', 'Все возможные выборки по 3 предприятия из 10')
    for i, h in enumerate(['№', '№ п/п 1', '№ п/п 2', '№ п/п 3', 'Предприятия', 'Средняя']): put(f'{L(8+i)}2', h, box=True)
    for k, (i, j, m) in enumerate(combos):
        row = 3 + k
        put(f'H{row}', k + 1, box=True); put(f'I{row}', i, box=True); put(f'J{row}', j, box=True); put(f'K{row}', m, box=True)
        put(f'L{row}', f'=INDEX($B$6:$B$15,I{row})&", "&INDEX($B$6:$B$15,J{row})&", "&INDEX($B$6:$B$15,K{row})', box=True)
        put(f'M{row}', f'=(INDEX($C$6:$C$15,I{row})+INDEX($C$6:$C$15,J{row})+INDEX($C$6:$C$15,K{row}))/3', box=True, fmt='0.00')
    for col, w in zip('ABCDEFGHIJKLM', [16, 16, 16, 16, 12, 4, 4, 6, 9, 9, 9, 16, 10]):
        ws.column_dimensions[col].width = w
    fit(wb); wb.save(f'{out_dir}/Тальян_Антон_Вариант_1.xlsx')

# ================= Вершков Максим =================
def maxim():
    who = 'maxim'; table, start = R[who]['table'], R[who]['start']
    seq = cells(table, start, False)
    t1, got1, nxt = select(table, seq, lambda x: x // 100, 10, 100)
    t2, got2, _ = select(table, seq[nxt:], lambda x: x // 1000, 3, 10)
    assert not any(s[3] for s in t2)
    vals = D.get(who, {}).get('values')
    f = Font(name='Calibri', size=11)
    wb = Workbook()

    ws = wb.active; ws.title = 'Задача1'; put = styler(ws, f)
    put('A1', 'Вершков Максим, вариант 1')
    put('A2', 'Всего предприятий'); put('D2', 100)
    put('A3', 'Отбираем 10%'); put('D3', '=D2*10%')
    put('A5', 'строка', box=True)
    for c in range(7): put(f'{L(c+2)}5', c + 1, box=True)
    for r in range(10):
        put(f'A{6+r}', r + 1, box=True)
        for c in range(7): put(f'{L(c+2)}{6+r}', table[r][c], box=True, fmt='0000')
    put('A17', 'Старт (строка, случайно от 1 до 7)'); put('E17', start)
    put('A18', 'Читаю строку слева направо, беру первые две цифры числа (00 = 100)')
    for i, h in enumerate(['Число', 'Первые 2 цифры', 'Повтор?', 'Номер']): put(f'{L(i+1)}20', h, box=True)
    first = 21
    for k, (r, c, n, rep) in enumerate(t1):
        row = first + k
        put(f'A{row}', f'={L(c+2)}{6+r}', box=True, fmt='0000')
        put(f'B{row}', f'=IF(INT(A{row}/100)=0,100,INT(A{row}/100))', box=True)
        put(f'C{row}', f'=IF(COUNTIF(B${first-1}:B{row-1},B{row})>0,"да","нет")', box=True)
        put(f'D{row}', f'=IF(C{row}="нет",B{row},"")', box=True)
    last = first + len(t1) - 1
    put(f'A{last+2}', 'Выборка по возрастанию:')
    for k in range(10):
        put(f'{L(k+2)}{last+3}', f'=SMALL($D${first}:$D${last},{k+1})', box=True)
    srow = last + 3
    ws.column_dimensions['A'].width = 12
    for col in 'BCDEFGHIJK': ws.column_dimensions[col].width = 9

    ws = wb.create_sheet('Задача2'); put = styler(ws, f)
    put('A1', 'Фамилия на В - колонка 2 табл. 1 приложения 1')
    put('A2', 'Из 10 предприятий задачи 1 случайно без повторения выбираем 3')
    put('A4', 'Количество сочетаний'); put('D4', '=COMBIN(10,3)')
    put('A6', '№', box=True); put('A7', 'x', box=True)
    for k in range(10):
        put(f'{L(k+2)}6', f'=Задача1!{L(k+2)}{srow}', box=True)
        put(f'{L(k+2)}7', vals[str(sorted(got1)[k])] if vals else None, box=True)
    put('L6', 'Σx', box=True); put('L7', '=SUM(B7:K7)', box=True)
    put('A8', '(x - значения колонки 2 из приложения 1)')
    put('A10', 'x̄ген = Σx / 10'); put('D10', '=L7/10', fmt='0.00')
    r0, c0 = t2[0][0], t2[0][1]
    put('A12', f'Выбор трех: дальше по той же таблице ({r0+1} строка, {c0+1} число), первая цифра = порядковый номер (0 -> 10)')
    for i, h in enumerate(['Число', 'Первая цифра', 'Порядк. №', '№ предпр.', 'x']): put(f'{L(i+1)}13', h, box=True)
    for k, (r, c, n, rep) in enumerate(t2):
        row = 14 + k
        put(f'A{row}', f'=Задача1!{L(c+2)}{6+r}', box=True, fmt='0000')
        put(f'B{row}', f'=INT(A{row}/1000)', box=True)
        put(f'C{row}', f'=IF(B{row}=0,10,B{row})', box=True)
        put(f'D{row}', f'=INDEX($B$6:$K$6,C{row})', box=True)
        put(f'E{row}', f'=INDEX($B$7:$K$7,C{row})', box=True)
    put('A18', 'x̄выб = '); put('D18', '=SUM(E14:E16)/3', fmt='0.00')
    put('A19', 'отклонение x̄выб - x̄ген'); put('D19', '=D18-D10', fmt='0.00')
    put('A21', 'Несмещенность (перебор всех 120 выборок на листе Выборки)')
    put('A22', 'среднее всех выборочных средних'); put('D22', '=AVERAGE(Выборки!F2:F121)', fmt='0.00')
    put('A23', 'x̄ген'); put('D23', '=D10', fmt='0.00')
    put('A24', '=IF(COUNT(B7:K7)<10,"впиши значения x из приложения 1",IF(ABS(D22-D23)<0.000001,"Совпадает, значит выборочная средняя несмещенная","Не совпадает"))')
    ws.column_dimensions['A'].width = 12
    for col in 'BCDEFGHIJKL': ws.column_dimensions[col].width = 9

    ws = wb.create_sheet('Выборки'); put = styler(ws, f)
    for i, h in enumerate(['№', 'Предприятия', 'x1', 'x2', 'x3', 'Средняя']): put(f'{L(i+1)}1', h, box=True)
    for k, (i, j, m) in enumerate(combos):
        row = 2 + k
        put(f'A{row}', k + 1, box=True)
        put(f'B{row}', f'=INDEX(Задача2!$B$6:$K$6,{i})&"-"&INDEX(Задача2!$B$6:$K$6,{j})&"-"&INDEX(Задача2!$B$6:$K$6,{m})', box=True)
        put(f'C{row}', f'=INDEX(Задача2!$B$7:$K$7,{i})', box=True)
        put(f'D{row}', f'=INDEX(Задача2!$B$7:$K$7,{j})', box=True)
        put(f'E{row}', f'=INDEX(Задача2!$B$7:$K$7,{m})', box=True)
        put(f'F{row}', f'=(C{row}+D{row}+E{row})/3', box=True, fmt='0.00')
    put('H1', 'min'); put('I1', '=MIN(F2:F121)', fmt='0.00')
    put('H2', 'max'); put('I2', '=MAX(F2:F121)', fmt='0.00')
    ws.column_dimensions['B'].width = 14
    fit(wb); wb.save(f'{out_dir}/Вершков_Максим_Вариант_1.xlsx')

anton(); maxim(); print('ok')
