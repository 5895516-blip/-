#!/usr/bin/env python3
"""Звуковой слой для промо v2: свисты, удары, щелчки точно на событиях монтажа.

Без numpy — чистый Python, 44.1 кГц стерео. Итог: music/sfx_v2.wav и music/mix_v2.wav
(трек + sfx через лимитер, если есть ffmpeg). Времена событий — по сетке трека (такт 1.875 с).
"""
import math
import os
import random
import struct
import subprocess
import wave

SR = 44100
DUR = 60.0
N = int(SR * DUR)
BEAT, BAR = 0.46875, 1.875
bar = lambda n: (n - 1) * BAR
HERE = os.path.dirname(os.path.abspath(__file__))

L = [0.0] * N
R = [0.0] * N
rnd = random.Random(17)


def put(t0, samples, gain=1.0, pan=0.0):
    """samples — список (l, r) или моно-значений; pan от -1 до 1."""
    i0 = int(t0 * SR)
    gl, gr = gain * math.sqrt((1 - pan) / 2), gain * math.sqrt((1 + pan) / 2)
    for k, v in enumerate(samples):
        i = i0 + k
        if 0 <= i < N:
            if isinstance(v, tuple):
                L[i] += v[0] * gain; R[i] += v[1] * gain
            else:
                L[i] += v * gl; R[i] += v * gr


def whoosh(dur=0.5, f0=300, f1=5000, peak=0.7, pan_from=-0.6, pan_to=0.6):
    """Шум через сдвигаемый полосовой фильтр, нарастание до peak·dur, потом спад."""
    n = int(dur * SR); out = []; lp1 = lp2 = 0.0
    for k in range(n):
        x = k / n
        env = (x / peak) ** 2 if x < peak else math.exp(-(x - peak) / (1 - peak) * 4.5)
        fc = f0 * (f1 / f0) ** (math.sin(math.pi * min(1, x / (peak * 1.6))) )
        a1 = 1 - math.exp(-2 * math.pi * fc / SR)
        a2 = 1 - math.exp(-2 * math.pi * fc * 0.35 / SR)
        s = rnd.uniform(-1, 1)
        lp1 += a1 * (s - lp1); lp2 += a2 * (lp1 - lp2)
        v = (lp1 - lp2) * env * 1.6
        p = pan_from + (pan_to - pan_from) * x
        out.append((v * math.sqrt((1 - p) / 2), v * math.sqrt((1 + p) / 2)))
    return out


def boom(dur=0.9, f0=95, f1=36):
    n = int(dur * SR); out = []; ph = 0.0
    for k in range(n):
        x = k / SR
        f = f1 + (f0 - f1) * math.exp(-x * 9)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-x * 4.2) + rnd.uniform(-1, 1) * math.exp(-x * 60) * 0.25)
    return out


def slash(dur=0.22):
    """Резкий «вжик» зачёркивания + глухой удар."""
    n = int(dur * SR); out = []; lp = 0.0; ph = 0.0
    for k in range(n):
        x = k / SR
        s = rnd.uniform(-1, 1); lp += 0.25 * (s - lp)
        hi = (s - lp) * math.exp(-x * 22) * 0.9
        ph += 2 * math.pi * (120 * math.exp(-x * 14) + 50) / SR
        out.append(hi + math.sin(ph) * math.exp(-x * 16) * 0.8)
    return out


def pop(f0=1100, f1=320, dur=0.09):
    n = int(dur * SR); out = []; ph = 0.0
    for k in range(n):
        x = k / SR
        ph += 2 * math.pi * (f1 + (f0 - f1) * math.exp(-x * 45)) / SR
        out.append(math.sin(ph) * math.exp(-x * 38))
    return out


def ping(f=1760, dur=0.45):
    n = int(dur * SR)
    return [(math.sin(2 * math.pi * f * k / SR) * 0.6 + math.sin(2 * math.pi * f * 1.5 * k / SR) * 0.3) * math.exp(-k / SR * 9)
            for k in range(n)]


def W(t_peak, dur=0.5, gain=0.35, **kw):
    """Свист, у которого пик приходится на t_peak (на склейку)."""
    peak = kw.pop('peak', 0.7)
    put(t_peak - dur * peak, whoosh(dur, peak=peak, **kw), gain)


# --- крючок: повороты призмы, отъезд, разлёт
W(bar(2), 0.42, 0.42); W(bar(3), 0.42, 0.42, pan_from=0.6, pan_to=-0.6)
W(bar(4) + 0.3, 0.7, 0.32, f0=200, f1=2500, peak=0.5)
put(bar(4) + BEAT, slash(0.35), 0.5); put(bar(4) + BEAT, boom(0.8, 120, 40), 0.55)
put(7.5, boom(1.2), 0.6)
# --- цифры, глобус
for tt in (bar(6), bar(7)):
    W(tt, 0.35, 0.18)
W(bar(8), 0.5, 0.25, f0=150, f1=1800)
for i in range(6):
    put(bar(8) + (i // 2) * BEAT + (i % 2) * 0.12 + 0.4, ping(1568 if i % 2 else 1760), 0.1, pan=0.4)
# --- спираль работ
W(15.0 + 0.3, 0.8, 0.35, f0=150, f1=3000, peak=0.45)
for k in (1, 2, 3):
    W(15 + k * BAR + 0.12, 0.45, 0.33, pan_from=-0.7 if k % 2 else 0.7, pan_to=0.7 if k % 2 else -0.7)
W(22.5 + 0.25, 0.7, 0.32, f0=400, f1=6000, peak=0.35)
# --- зачёркивания
for i in range(4):
    put(bar(14) + i * BEAT, slash(), 0.42, pan=(-0.4, 0.4, -0.4, 0.4)[i])
# --- дроп 2 и дальше
put(30.0, boom(1.2, 110, 34), 0.55)
for i in range(7):
    put(bar(19) + 0.2 + i * 0.36, pop(), 0.5, pan=math.cos(i * 2 * math.pi / 7) * 0.7)
W(37.5 + 0.1, 0.55, 0.3, pan_from=0.8, pan_to=-0.2); W(bar(22) + 0.1, 0.55, 0.3, pan_from=0.8, pan_to=-0.2)
W(bar(23) + 0.1, 0.45, 0.25)
for k in (2, 4):
    W(bar(23) + k * BEAT + 0.02, 0.4, 0.3, f0=600, f1=7000)
W(bar(23) + 6 * BEAT + 0.15, 0.5, 0.3)
W(45.0, 0.9, 0.42, f0=120, f1=2600, peak=0.8); put(45.0, boom(1.0, 100, 38), 0.45)
W(52.5 + 0.4, 0.9, 0.35, f0=2500, f1=200, peak=0.3)
W(53.6, 0.6, 0.25)
put(56.25, boom(1.4, 90, 32), 0.55)


def write(path, ch):
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        frames = bytearray()
        for l, r in zip(*ch):
            frames += struct.pack('<hh', max(-32767, min(32767, int(l * 32767))), max(-32767, min(32767, int(r * 32767))))
        w.writeframes(bytes(frames))


sfx = os.path.join(HERE, 'sfx_v2.wav')
write(sfx, (L, R))
mix = os.path.join(HERE, 'mix_v2.wav')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(HERE, 'track.wav'), '-i', sfx, '-filter_complex',
                '[1]volume=1.35[s];[0][s]amix=inputs=2:normalize=0,alimiter=limit=0.93:level=false', '-ar', '44100', mix], check=True)
print('ok', sfx, mix)
