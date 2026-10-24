"""Grey-box previs, scene 1: night bedroom, slow dolly push-in to eyes. 9:16, 24 fps, 5 s."""
import sys, os
import numpy as np
from PIL import Image

W, H = int(sys.argv[1]), int(sys.argv[2])
FRAMES = [int(a) for a in sys.argv[3].split(",")] if len(sys.argv) > 3 and sys.argv[3] != "all" else list(range(1, 121))
OUT = sys.argv[4] if len(sys.argv) > 4 else "frames"
os.makedirs(OUT, exist_ok=True)

def n(v): return v / np.linalg.norm(v)

# ---------------- scene ----------------
# x right, y up, z toward the camera. Left wall x=-1.6 holds the window, bed runs along it.
boxes, ellips = [], []
def box(lo, hi, alb): boxes.append((np.array(lo, float), np.array(hi, float), np.array(alb, float)))
def ell(c, r, alb): ellips.append((np.array(c, float), np.array(r, float), np.array(alb, float)))

wall = (0.55, 0.55, 0.57); floor = (0.42, 0.40, 0.38)
box((-3, -0.1, -3), (3, 0, 3), floor)                     # floor
box((-3, 2.6, -3), (3, 2.7, 3), wall)                     # ceiling
box((-3, 0, -1.6), (3, 2.6, -1.5), wall)                  # back wall (behind headboard)
box((2.0, 0, -3), (2.1, 2.6, 3), wall)                    # right wall
box((-3, 0, 2.6), (3, 2.6, 2.7), wall)                    # wall behind camera
# left wall with window opening z[-1.35,-0.15] y[0.95,2.2]
box((-1.7, 0, -3), (-1.6, 0.95, 3), wall)
box((-1.7, 2.2, -3), (-1.6, 2.6, 3), wall)
box((-1.7, 0.95, -3), (-1.6, 2.2, -1.35), wall)
box((-1.7, 0.95, -0.15), (-1.6, 2.2, 3), wall)
box((-1.6, 0.90, -1.42), (-1.42, 0.95, -0.08), (0.75, 0.75, 0.75))   # windowsill
box((-1.62, 1.55, -1.35), (-1.58, 1.58, -0.15), (0.6, 0.6, 0.6))     # window frame bar
box((-1.62, 0.95, -0.77), (-1.58, 2.2, -0.73), (0.6, 0.6, 0.6))      # window mullion
box((-1.58, 0.95, -1.55), (-1.50, 2.35, -1.33), (0.35, 0.36, 0.42))  # curtain left
box((-1.58, 0.95, -0.17), (-1.50, 2.35, 0.10), (0.35, 0.36, 0.42))   # curtain right
box((-1.55, 0.95, -0.66), (-1.47, 0.962, -0.585), (0.08, 0.08, 0.09))  # PHONE on sill (screen down/off)

# bed: head toward -z, along left wall
box((-1.50, 0.0, -1.45), (-0.10, 0.32, 1.00), (0.30, 0.30, 0.32))   # frame
box((-1.48, 0.32, -1.43), (-0.12, 0.55, 0.98), (0.70, 0.70, 0.70))  # mattress
box((-1.52, 0.0, -1.50), (-0.08, 1.05, -1.42), (0.28, 0.28, 0.30))  # headboard
ell((-0.85, 0.62, -1.15), (0.36, 0.08, 0.20), (0.82, 0.82, 0.84))   # pillow
ell((-0.85, 0.63, -0.15), (0.50, 0.14, 0.95), (0.62, 0.64, 0.68))   # blanket over body
ell((-0.85, 0.65, -0.62), (0.26, 0.10, 0.16), (0.62, 0.64, 0.68))   # shoulders under blanket
# head: lying on back, crown toward -z, face up
HEAD = np.array([-0.85, 0.735, -0.98])
ell(HEAD, (0.078, 0.085, 0.105), (0.74, 0.66, 0.60))               # skull/face
ell(HEAD + (0, 0.03, 0.115), (0.045, 0.040, 0.030), (0.74, 0.66, 0.60))  # chin/jaw
ell(HEAD + (0, 0.090, 0.040), (0.012, 0.016, 0.024), (0.74, 0.66, 0.60)) # nose
EYES = HEAD + np.array([0, 0.072, 0.005])
for sx in (-0.031, 0.031):
    ell(EYES + (sx, 0.001, 0), (0.017, 0.008, 0.0035), (0.10, 0.08, 0.08))   # closed eyelid line
    ell(EYES + (sx, 0.004, -0.024), (0.020, 0.008, 0.004), (0.20, 0.17, 0.15))  # eyebrow
ell(HEAD + (0, 0.005, -0.03), (0.082, 0.07, 0.09), (0.16, 0.14, 0.13))   # hair
box((-1.25, 1.35, -1.50), (-0.35, 1.95, -1.47), (0.22, 0.22, 0.24))   # car poster frame above bed
box((-1.20, 1.40, -1.47), (-0.40, 1.90, -1.465), (0.40, 0.40, 0.44))  # poster
box((0.70, 1.55, -1.50), (1.60, 1.58, -1.30), (0.35, 0.35, 0.35))    # wall shelf
# nightstand + lamp (off), right of bed head
box((-0.05, 0.0, -1.45), (0.45, 0.55, -1.0), (0.32, 0.30, 0.28))
box((0.12, 0.55, -1.30), (0.28, 0.60, -1.14), (0.5, 0.5, 0.5))
box((0.18, 0.60, -1.24), (0.22, 0.95, -1.20), (0.5, 0.5, 0.5))
box((0.08, 0.95, -1.34), (0.32, 1.12, -1.10), (0.7, 0.7, 0.7))
# chair with clothes, far right
box((1.2, 0.0, -0.4), (1.7, 0.45, 0.1), (0.30, 0.30, 0.30))
box((1.6, 0.45, -0.4), (1.7, 1.05, 0.1), (0.30, 0.30, 0.30))

# directional "city/moon light" entering through the window
L = n(np.array([-1.0, 0.55, 0.12]))
KEY = np.array([0.62, 0.74, 1.00]) * 1.0
AMB = np.array([0.10, 0.11, 0.15])

def city(d, o):
    """Procedural night skyline seen through the window (rays leaving at x<-1.6)."""
    t = (-14.0 - o[..., 0]) / np.minimum(d[..., 0], -1e-6)
    py = o[..., 1] + t * d[..., 1]; pz = o[..., 2] + t * d[..., 2]
    sky = np.stack([0.05 + 0.02 * np.clip(py / 20, 0, 1), 0.07 + 0.03 * np.clip(py / 20, 0, 1), 0.16 + 0.05 * np.clip(py / 20, 0, 1)], -1)
    bw = 3.2
    bi = np.floor(pz / bw)
    hgt = 4 + 14 * (np.abs(np.sin(bi * 12.9898) * 43758.5453) % 1)
    inb = (py < hgt) & ((pz / bw) % 1 > 0.08)
    wx = (pz * 2.2) % 1 > 0.45; wy = (py * 2.0) % 1 > 0.5
    lit = (np.abs(np.sin(np.floor(pz * 2.2) * 7.1 + np.floor(py * 2.0) * 3.7) * 9137.3) % 1) > 0.62
    col = np.where(inb[..., None], np.array([0.03, 0.035, 0.05]), sky)
    win = inb & wx & wy & lit
    col = np.where(win[..., None], np.array([1.0, 0.72, 0.38]) * 0.9, col)
    return col

def trace(o, d):
    shp = d.shape[:-1]
    tbest = np.full(shp, np.inf); nrm = np.zeros(shp + (3,)); alb = np.zeros(shp + (3,))
    inv = 1.0 / np.where(np.abs(d) < 1e-9, 1e-9, d)
    for lo, hi, a in boxes:
        t1 = (lo - o) * inv; t2 = (hi - o) * inv
        tmin = np.minimum(t1, t2); tmax = np.maximum(t1, t2)
        tn = tmin.max(-1); tf = tmax.min(-1)
        hit = (tf >= np.maximum(tn, 1e-4)) & (tn > 1e-4) & (tn < tbest)
        if hit.any():
            tbest = np.where(hit, tn, tbest)
            ax = tmin.argmax(-1)
            nn = np.zeros(shp + (3,)); np.put_along_axis(nn, ax[..., None], 1.0, -1)
            nn = nn * -np.sign(d)
            nrm = np.where(hit[..., None], nn, nrm); alb = np.where(hit[..., None], a, alb)
    for c, r, a in ellips:
        oc = (o - c) / r; dd = d / r
        A = (dd * dd).sum(-1); B = 2 * (oc * dd).sum(-1); C = (oc * oc).sum(-1) - 1
        disc = B * B - 4 * A * C
        ok = disc > 0
        sq = np.sqrt(np.where(ok, disc, 0))
        t = (-B - sq) / (2 * A)
        hit = ok & (t > 1e-4) & (t < tbest)
        if hit.any():
            tbest = np.where(hit, t, tbest)
            p = o + d * t[..., None]
            nn = (p - c) / (r * r); nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
            nrm = np.where(hit[..., None], nn, nrm); alb = np.where(hit[..., None], a, alb)
    return tbest, nrm, alb

def shade(o, d):
    t, nrm, alb = trace(o, d)
    miss = ~np.isfinite(t)
    tt = np.where(miss, 0, t)
    p = o + d * tt[..., None]
    ndl = np.clip((nrm * L).sum(-1), 0, 1)
    so = p + nrm * 2e-3
    need = (ndl > 0) & ~miss                      # shadow rays only where the window light could land
    lit = np.zeros(ndl.shape, bool)
    if need.any():
        ts, _, _ = trace(so[need], np.broadcast_to(L, so[need].shape))
        lit[need] = ~np.isfinite(ts)
    # light only reaches through the window: shadow rays that escape must leave via x<-1.6 (walls block the rest)
    col = alb * (AMB + KEY * (ndl * lit)[..., None]) + alb * 0.08 * (0.5 + 0.5 * nrm[..., 1:2])
    col = np.where(miss[..., None], city(d, o), col)
    return col

# ---------------- camera ----------------
SW, SH = 20.25, 36.0   # vertical full-frame crop (mm)
P0 = np.array([0.45, 1.30, 1.50]); T0 = np.array([-0.95, 0.92, -0.95]); F0 = 30.0
P1 = EYES + np.array([0.0, 0.30, 0.055]); T1 = EYES + np.array([0, 0, -0.006]); F1 = 58.0
PM = np.array([-0.20, 1.50, 0.45])  # bezier control: stays high mid-move, then settles overhead

def ease(x): return x * x * x * (x * (6 * x - 15) + 10)   # smootherstep: soft start, soft landing
def cam(f):
    # 1-12 barely creeping (trim handle), 12-100 push-in, 100-120 settle on the eyes
    s = 0.015 * np.clip((f - 1) / 11.0, 0, 1) + 0.975 * ease(np.clip((f - 12) / 88.0, 0, 1)) + 0.010 * ease(np.clip((f - 100) / 20.0, 0, 1))
    p = (1 - s) ** 2 * P0 + 2 * (1 - s) * s * PM + s ** 2 * P1
    tgt = T0 + (T1 - T0) * min(1.0, s ** 0.75)
    foc = F0 + (F1 - F0) * s
    return p, tgt, foc

ys, xs = np.mgrid[0:H, 0:W]
nx = (xs + 0.5) / W * 2 - 1; ny = 1 - (ys + 0.5) / H * 2
for f in FRAMES:
    p, tgt, foc = cam(f)
    fw = n(tgt - p); rt = n(np.cross(fw, [0, 1, 0])); up = np.cross(rt, fw)
    d = fw * foc + rt[None, None, :] * (nx[..., None] * SW / 2) + up[None, None, :] * (ny[..., None] * SH / 2)
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    o = np.broadcast_to(p, d.shape)
    # 2x2 supersampling for clean edges
    acc = np.zeros((H, W, 3))
    for jx, jy in ((-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25)):
        dj = fw * foc + rt * 0 + rt[None, None, :] * ((nx[..., None] + jx * 2 / W) * SW / 2) + up[None, None, :] * ((ny[..., None] - jy * 2 / H) * SH / 2)
        dj = dj / np.linalg.norm(dj, axis=-1, keepdims=True)
        acc += shade(o, dj)
    img = np.clip(acc / 4, 0, 1) ** (1 / 2.2)
    Image.fromarray((img * 255).astype(np.uint8)).save(f"{OUT}/f{f:04d}.png")
    print(f, flush=True)
