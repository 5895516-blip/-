# -*- coding: utf-8 -*-
"""Процедурный трек 128 BPM, ля минор, ровно 60 секунд (32 такта).

Структура (такты, с 1):
  1–4    интро: пэд + арпеджио через фильтр, хэты, сбивка, райзер
  5–12   дроп 1: бочка, клэп, бас, пэд, арпеджио
  13–14  брейк: пэд, фильтр
  15–16  билд: снэр-ролл, райзер
  17–28  дроп 2: всё + лид
  29–32  аутро: два такта грува, финальный удар и хвост
"""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
import wave, os, json

SR = 44100
BPM = 128
BEAT = 60 / BPM
BAR = BEAT * 4
BARS = 32
DUR = BAR * BARS  # 60.0 с
N = int(round(DUR * SR))
rng = np.random.default_rng(7)

L = np.zeros(N); R = np.zeros(N)


def mf(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def t_of(bar, beat=0.0):
    """Время начала: bar с 1, beat в долях (0..4)."""
    return (bar - 1) * BAR + beat * BEAT


def add(sig, t0, gain=1.0, pan=0.0, buf=None):
    i0 = int(round(t0 * SR))
    if i0 >= N:
        return
    sig = sig[: N - i0]
    gl = gain * np.cos((pan + 1) * np.pi / 4)
    gr = gain * np.sin((pan + 1) * np.pi / 4)
    if buf is None:
        L[i0:i0 + len(sig)] += sig * gl; R[i0:i0 + len(sig)] += sig * gr
    else:
        buf[0][i0:i0 + len(sig)] += sig * gl; buf[1][i0:i0 + len(sig)] += sig * gr


def lp(x, fc, order=2):
    sos = butter(order, min(fc, SR / 2 * 0.95) / (SR / 2), "low", output="sos")
    return sosfilt(sos, x)


def hp(x, fc, order=2):
    sos = butter(order, fc / (SR / 2), "high", output="sos")
    return sosfilt(sos, x)


def bp(x, lo, hi, order=2):
    sos = butter(order, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos")
    return sosfilt(sos, x)


def env_adsr(n, a, d, s, r_, sustain_len):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r_ * SR)
    s_n = max(0, int(sustain_len * SR) - a_n - d_n)
    e = np.concatenate([
        np.linspace(0, 1, max(a_n, 1)),
        np.linspace(1, s, max(d_n, 1)),
        np.full(s_n, s),
        np.linspace(s, 0, max(r_n, 1)),
    ])
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n]


def saw(freq, n, phase=0.0):
    t = np.arange(n) / SR
    return 2 * ((freq * t + phase) % 1.0) - 1


def tvlp(x, cutoffs):
    """Фильтр с меняющейся частотой среза (простой однополюсный x2)."""
    y = np.zeros_like(x)
    a = 1 - np.exp(-2 * np.pi * np.clip(cutoffs, 20, SR / 2.2) / SR)
    s1 = s2 = 0.0
    for i in range(len(x)):
        s1 += a[i] * (x[i] - s1)
        s2 += a[i] * (s1 - s2)
        y[i] = s2
    return y


# ---------- барабаны ----------
def kick():
    n = int(0.45 * SR); t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.28)
    click = hp(rng.standard_normal(n), 2000) * np.exp(-t / 0.004) * 0.25
    return np.tanh(1.6 * (body + click)) * 0.95


def clap():
    n = int(0.5 * SR); t = np.arange(n) / SR
    noise = bp(rng.standard_normal(n), 900, 5000)
    e = np.zeros(n)
    for k, off in enumerate([0, 0.011, 0.022]):
        i = int(off * SR)
        e[i:] += np.exp(-(t[: n - i]) / 0.008) * (0.8 if k < 2 else 1)
    e += np.exp(-t / 0.13) * 0.55
    return noise * e * 0.6


def snare(len_s=0.25):
    n = int(len_s * SR); t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.4
    noise = bp(rng.standard_normal(n), 1500, 8000) * np.exp(-t / 0.08)
    return (tone + noise) * 0.55


def hat(open_=False):
    n = int((0.3 if open_ else 0.06) * SR); t = np.arange(n) / SR
    noise = hp(rng.standard_normal(n), 7500, 4)
    return noise * np.exp(-t / (0.09 if open_ else 0.015)) * 0.35


def crash():
    n = int(2.6 * SR); t = np.arange(n) / SR
    noise = hp(rng.standard_normal(n), 4000, 2)
    return noise * np.exp(-t / 0.7) * 0.35


def impact():
    n = int(2.5 * SR); t = np.arange(n) / SR
    f = 30 + 60 * np.exp(-t / 0.15)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.9)
    return np.tanh(sub * 1.5) * 0.9


def riser(len_s):
    n = int(len_s * SR); t = np.arange(n) / SR
    x = t / len_s
    noise = rng.standard_normal(n)
    y = tvlp(noise, 300 + 9000 * x ** 2.2)
    tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * x ** 2) / SR) * 0.15
    return (y * 1.4 + tone) * x ** 1.6 * 0.5


def downsweep(len_s=1.8):
    n = int(len_s * SR); t = np.arange(n) / SR
    x = t / len_s
    y = tvlp(rng.standard_normal(n), 9000 * (1 - x) ** 2 + 200)
    return y * (1 - x) ** 1.5 * 0.5


# ---------- гармония ----------
CHORDS = [  # Am F C G — MIDI
    [57, 60, 64, 69],
    [53, 57, 60, 65],
    [55, 60, 64, 67],
    [55, 59, 62, 67],
]
ROOTS = [45 - 12, 41 - 12, 48 - 12, 43 - 12]  # A1 F1 C2 G1


def chord_of(bar):
    return (bar - 1) % 4


def supersaw(m, n, voices=7, detune=0.18):
    f = mf(m)
    out = np.zeros(n)
    for v in range(voices):
        d = (v - (voices - 1) / 2) / ((voices - 1) / 2) * detune
        out += saw(f * 2 ** (d / 12), n, rng.random())
    return out / voices


# буферы под сайдчейн
pad = [np.zeros(N), np.zeros(N)]
bass = [np.zeros(N), np.zeros(N)]
arp = [np.zeros(N), np.zeros(N)]
lead = [np.zeros(N), np.zeros(N)]
drums = [np.zeros(N), np.zeros(N)]
fx = [np.zeros(N), np.zeros(N)]

KICK, CLAP, HAT_C, HAT_O = kick(), clap(), hat(), hat(True)
kick_times = []


def section(bar):
    if bar <= 4: return "intro"
    if bar <= 12: return "drop1"
    if bar <= 14: return "break"
    if bar <= 16: return "build"
    if bar <= 28: return "drop2"
    return "outro"


for bar in range(1, BARS + 1):
    sec = section(bar)
    c = chord_of(bar)
    # --- пэд ---
    if sec in ("intro", "drop1", "break", "build", "drop2") or bar in (29, 30, 31):
        n = int(BAR * SR) + int(0.6 * SR)
        hold = BAR if bar != 31 else BAR * 2
        n = int(hold * SR) + int(0.6 * SR)
        sig = sum(supersaw(m, n) for m in CHORDS[c]) / 3
        e = env_adsr(n, 0.05, 0.3, 0.8, 0.6, hold)
        if sec == "intro":
            cut = 600 + 1800 * (bar - 1) / 4
        elif sec == "break":
            cut = 1100
        elif sec == "build":
            cut = 1400 + 1600 * (bar - 15) / 2
        else:
            cut = 4200
        sig = lp(sig, cut, 2) * e
        pg = 0.32 if sec in ("drop1", "drop2") or bar in (29, 30) else 0.75
        add(sig, t_of(bar), pg, -0.25, pad); add(sig, t_of(bar) + 0.012, pg, 0.25, pad)

    # --- бочка ---
    if sec in ("drop1", "drop2") or bar in (29, 30):
        for b in range(4):
            add(KICK, t_of(bar, b), 1.0, 0, drums); kick_times.append(t_of(bar, b))
    if sec == "build" and bar == 15:
        for b in range(4):
            add(KICK, t_of(bar, b), 0.7, 0, drums); kick_times.append(t_of(bar, b))

    # --- клэп / хэты ---
    if sec in ("drop1", "drop2") or bar in (29, 30):
        for b in (1, 3):
            add(CLAP, t_of(bar, b), 0.75, 0.05, drums)
        for e8 in range(8):
            if e8 % 2 == 1:
                add(HAT_O, t_of(bar, e8 / 2), 0.55, 0.2, drums)
            else:
                add(HAT_C, t_of(bar, e8 / 2), 0.45, -0.2, drums)
        if sec == "drop2":
            for s16 in range(16):
                if s16 % 2 == 1:
                    add(HAT_C, t_of(bar, s16 / 4), 0.22, 0.35, drums)
    if sec == "intro" and bar >= 3:
        for e8 in range(8):
            add(HAT_C, t_of(bar, e8 / 2), 0.3 + 0.05 * e8 / 8, -0.2, drums)

    # --- бас (оффбит восьмыми + гул) ---
    if sec in ("drop1", "drop2") or bar in (29, 30):
        root = ROOTS[c]
        for b in range(4):
            for off, oct_ in ((0.5, 0), (0.75, 12 if b % 2 else 0)):
                n = int(BEAT * 0.25 * SR * 1.3)
                s = saw(mf(root + 12 + oct_), n) * 0.6 + np.sin(2 * np.pi * mf(root) * np.arange(n) / SR) * 0.8
                e = env_adsr(n, 0.003, 0.08, 0.5, 0.03, BEAT * 0.22)
                add(lp(s, 900) * e, t_of(bar, b + off), 0.55, 0, bass)
        n = int(BAR * SR)
        sub = np.sin(2 * np.pi * mf(root) * np.arange(n) / SR) * env_adsr(n, 0.01, 0.1, 0.9, 0.05, BAR - 0.05)
        add(sub, t_of(bar), 0.35, 0, bass)

    # --- арпеджио 16-ми ---
    if sec != "outro" or bar <= 30:
        notes = CHORDS[c] + [CHORDS[c][1] + 12, CHORDS[c][2] + 12]
        pattern = [0, 2, 4, 3, 1, 2, 5, 3, 0, 4, 2, 5, 1, 3, 4, 2]
        if sec == "intro":
            cut = 700 + 2500 * ((bar - 1) * 16) / 64
        elif sec == "break":
            cut = 1500
        elif sec == "build":
            cut = 1500 + 3000 * (bar - 15) / 2
        else:
            cut = 5000
        for s16 in range(16):
            m = notes[pattern[s16]] + 12
            n = int(BEAT * 0.5 * SR)
            s = saw(mf(m), n) * 0.5 + saw(mf(m) * 1.005, n) * 0.5
            e = np.exp(-np.arange(n) / SR / 0.07)
            g = 0.22 if sec in ("drop1", "drop2") else 0.42
            add(lp(s, cut) * e, t_of(bar, s16 / 4), g, 0.4 if s16 % 2 else -0.4, arp)

    # --- лид во втором дропе ---
    if sec == "drop2":
        # мотив на 4 такта: (доля, длина в долях, нота)
        motif = {
            0: [(0, 1.5, 76), (1.5, 0.5, 74), (2, 1, 72), (3, 1, 74)],
            1: [(0, 1.5, 72), (1.5, 0.5, 69), (2, 2, 69)],
            2: [(0, 1, 76), (1, 0.5, 79), (1.5, 1.5, 76), (3, 1, 74)],
            3: [(0, 1.5, 74), (1.5, 0.5, 72), (2, 1, 71), (3, 1, 74)],
        }[(bar - 17) % 4]
        for (b, ln, m) in motif:
            n = int((ln * BEAT + 0.3) * SR)
            t = np.arange(n) / SR
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1)
            ph = np.cumsum(mf(m) * vib) / SR
            s = (2 * (ph % 1) - 1) * 0.5 + (2 * ((ph * 1.007) % 1) - 1) * 0.5
            s += np.sin(2 * np.pi * ph * 0.5) * 0.3
            e = env_adsr(n, 0.01, 0.15, 0.7, 0.25, ln * BEAT * 0.95)
            add(lp(s, 3800) * e, t_of(bar, b), 0.2, 0.0, lead)

# --- сбивки и эффекты ---
for bar in (4, 16):
    # снэр-ролл
    steps = 16 if bar == 4 else 32
    base_bar = bar if bar == 4 else 15
    span = BAR if bar == 4 else 2 * BAR
    for k in range(steps):
        tt = t_of(base_bar) + k * span / steps
        add(snare(), tt, 0.25 + 0.5 * k / steps, 0, drums)
add(riser(BAR * 2), t_of(3), 0.9, 0, fx)
add(riser(BAR * 2), t_of(15), 1.0, 0, fx)
add(riser(BAR), t_of(12), 0.5, 0, fx)
for b in (5, 17):
    add(impact(), t_of(b), 1.0, 0, fx); add(crash(), t_of(b), 0.9, 0.1, fx)
add(crash(), t_of(9), 0.5, -0.1, fx); add(crash(), t_of(21), 0.5, -0.1, fx)
add(crash(), t_of(25), 0.6, 0.1, fx)
add(downsweep(), t_of(13), 0.7, 0, fx)
add(impact(), t_of(13), 0.6, 0, fx)
add(impact(), t_of(31), 1.0, 0, fx); add(crash(), t_of(31), 1.0, 0, fx)
add(KICK, t_of(31), 1.0, 0, drums)
add(CLAP, t_of(31), 0.6, 0, drums)
# брейк — «вдох»: бочка на последнюю долю 12-го такта отсутствует, ставим реверс-нойз
add(riser(BEAT * 2)[::-1][::-1], t_of(12, 2), 0.3, 0, fx)

# ---------- сайдчейн ----------
side = np.ones(N)
tt = np.arange(N) / SR
for k in kick_times:
    i0 = int(k * SR); i1 = min(N, i0 + int(BEAT * SR))
    x = tt[i0:i1] - k
    side[i0:i1] = np.minimum(side[i0:i1], 1 - 0.75 * np.exp(-x / 0.09))


def reverb(sig, wet=0.25, decay=1.6):
    n = int(decay * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR / (decay / 5))
    ir = lp(ir, 6000)
    ir /= np.sqrt(np.sum(ir ** 2))
    return sig + wet * fftconvolve(sig, ir)[: len(sig)]


def delay(sig, t=BEAT * 0.75, fb=0.35, mix=0.3):
    d = int(t * SR)
    out = sig.copy()
    tap = sig.copy()
    for _ in range(5):
        tap = np.concatenate([np.zeros(d), tap[:-d]]) * fb
        out += tap * mix / fb * fb
    return out


mixL = np.zeros(N); mixR = np.zeros(N)
for (bufL, bufR), g, sc, rv in (
    (pad, 1.0, True, 0.35),
    (bass, 1.0, True, 0.0),
    (arp, 1.0, True, 0.25),
    (lead, 1.0, True, 0.3),
    (drums, 1.0, False, 0.08),
    (fx, 1.0, False, 0.2),
):
    a, b = bufL * g, bufR * g
    if rv:
        a, b = reverb(a, rv), reverb(b, rv)
    if sc:
        a, b = a * side, b * side
    mixL += a; mixR += b

# лиду — дилэй пинг-понг
dl = delay(lead[0], mix=0.25) - lead[0]
dr = delay(lead[1], t=BEAT * 0.5, mix=0.25) - lead[1]
mixL += dr * side * 0.6; mixR += dl * side * 0.6

# мастер: лёгкий хайпасс, мягкий клип, нормализация, фейд в конце
mixL, mixR = hp(mixL, 28), hp(mixR, 28)
peak = max(np.abs(mixL).max(), np.abs(mixR).max())
mixL, mixR = mixL / peak * 1.6, mixR / peak * 1.6
mixL, mixR = np.tanh(mixL), np.tanh(mixR)
fade = np.ones(N); fn = int(1.2 * SR); fade[-fn:] = np.linspace(1, 0, fn) ** 2
mixL *= fade; mixR *= fade
peak = max(np.abs(mixL).max(), np.abs(mixR).max())
mixL, mixR = mixL / peak * 0.93, mixR / peak * 0.93

out = os.path.join(os.path.dirname(__file__), "track.wav")
pcm = (np.stack([mixL, mixR], 1) * 32767).astype("<i2")
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
json.dump({"bpm": BPM, "bars": BARS, "duration": DUR, "kicks": kick_times},
          open(os.path.join(os.path.dirname(__file__), "beats.json"), "w"))
print("ok", out, DUR)
