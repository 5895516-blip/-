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
    wb = Workbook()

    def put(ws, ref, val, fmt=None):
        ws[ref] = val
        if fmt: ws[ref].number_format = fmt

    ws = wb.active; ws.title = 'Задача 1'
    put(ws, 'A1', 'Тальян Антон, вариант 1')
    put(ws, 'A3', 'Задача 1')
    put(ws, 'A4', 'N'); put(ws, 'B4', 100)
    put(ws, 'A5', 'n'); put(ws, 'B5', '=B4*10%')
    for c in range(7): put(ws, f'{L(c+1)}7', c + 1)
    for r in range(10):
        for c in range(7): put(ws, f'{L(c+1)}{8+r}', table[r][c], '0000')
    put(ws, 'A19', 'старт'); put(ws, 'B19', start)
    put(ws, 'A21', 'число'); put(ws, 'B21', 'номер'); put(ws, 'C21', 'повтор'); put(ws, 'D21', 'в выборку')
    first = 22
    for k, (r, c, n, rep) in enumerate(t1):
        row = first + k
        put(ws, f'A{row}', f'={L(c+1)}{8+r}', '0000')
        put(ws, f'B{row}', f'=IF(MOD(A{row},100)=0,100,MOD(A{row},100))')
        put(ws, f'C{row}', f'=IF(COUNTIF(B${first-1}:B{row-1},B{row})>0,"повтор","")')
        put(ws, f'D{row}', f'=IF(C{row}="",B{row},"")')
    last = first + len(t1) - 1
    s = last + 2
    put(ws, f'A{s}', 'выборка')
    for k in range(10): put(ws, f'{L(k+2)}{s}', f'=SMALL($D${first}:$D${last},{k+1})')
    ws.column_dimensions['A'].width = 12

    ws2 = wb.create_sheet('Задача 2'); ws = ws2
    put(ws, 'A1', 'Задача 2')
    put(ws, 'A2', 'колонка 14 - ' + (D.get(who, {}).get('indicator') or ''))
    put(ws, 'A4', 'предприятие'); put(ws, 'A5', 'значение')
    for k in range(10):
        put(ws, f'{L(k+2)}4', f"='Задача 1'!{L(k+2)}{s}")
        put(ws, f'{L(k+2)}5', vals[str(sorted(got1)[k])] if vals else None)
    E = '$B$4:$K$4'; V = '$B$5:$K$5'
    put(ws, 'A7', 'сумма'); put(ws, 'B7', '=SUM(B5:K5)')
    put(ws, 'A8', 'Хср'); put(ws, 'B8', '=B7/10', '0.000')
    put(ws, 'A9', 'сочетаний'); put(ws, 'B9', '=COMBIN(10,3)')
    h = 11
    for i, t in enumerate(['число', 'цифра', '№ п/п', 'предприятие', 'значение']): put(ws, f'{L(i+1)}{h}', t)
    for k, (r, c, n, rep) in enumerate(t2):
        row = h + 1 + k
        put(ws, f'A{row}', f"='Задача 1'!{L(c+1)}{8+r}", '0000')
        put(ws, f'B{row}', f'=MOD(A{row},10)')
        put(ws, f'C{row}', f'=IF(B{row}=0,10,B{row})')
        put(ws, f'D{row}', f'=INDEX({E},C{row})')
        put(ws, f'E{row}', f'=INDEX({V},C{row})')
    m = h + 5
    put(ws, f'A{m}', 'хср'); put(ws, f'B{m}', f'=SUM(E{h+1}:E{h+3})/3', '0.000')
    put(ws, f'A{m+1}', 'хср - Хср'); put(ws, f'B{m+1}', f'=B{m}-B8', '0.000')
    put(ws, f'A{m+3}', 'M(хср)'); put(ws, f'B{m+3}', '=AVERAGE(N2:N121)', '0.000')
    put(ws, f'A{m+4}', f'=IF(COUNT(B5:K5)<10,"впиши значения из приложения 1",IF(ABS(B{m+3}-B8)<0.000001,"M(хср) = Хср, оценка несмещенная","не равны"))')
    put(ws, 'M1', 'выборки'); put(ws, 'N1', 'средняя')
    for k, (i, j, q) in enumerate(combos):
        row = 2 + k
        put(ws, f'M{row}', f'=INDEX({E},{i})&", "&INDEX({E},{j})&", "&INDEX({E},{q})')
        put(ws, f'N{row}', f'=(INDEX({V},{i})+INDEX({V},{j})+INDEX({V},{q}))/3', '0.000')
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['M'].width = 14
    fit(wb); wb.save(f'{out_dir}/Тальян первый вариант.xlsx')

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
    put('A1', 'Фамилия на В - колонка 2 табл. 1 приложения 1 (численность ППП, чел.)')
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
