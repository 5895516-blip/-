"""Grey-box previs, scene 2: eyes open inside the dream car, camera pulls back and arcs to a 3/4 interior shot.
Starts on the exact framing scene 1 ends on (match cut), ends on an anamorphic flare whiteout (wipe into scene 3).
9:16, 24 fps, 5 s."""
import sys, os
import numpy as np
from PIL import Image

W, H = int(sys.argv[1]), int(sys.argv[2])
FRAMES = [int(a) for a in sys.argv[3].split(",")] if len(sys.argv) > 3 and sys.argv[3] != "all" else list(range(1, 121))
OUT = sys.argv[4] if len(sys.argv) > 4 else "frames02"
os.makedirs(OUT, exist_ok=True)
FPS = 24.0

def n(v): return v / np.linalg.norm(v)

# ---------------- primitives ----------------
# A primitive is ("box", lo, hi, alb) or ("ell", c, r, alb). Groups carry a bounding sphere so that
# chains of small spheres (wheel rim, arms) are only tested for rays that can actually reach them.
def box(lo, hi, alb): return ("box", np.array(lo, float), np.array(hi, float), np.array(alb, float))
def ell(c, r, alb): return ("ell", np.array(c, float), np.array(r, float), np.array(alb, float))
def cap(a, b, r, alb): return ("cap", np.array(a, float), np.array(b, float), float(r), np.array(alb, float))

def bound(prims):
    pts = []
    for p in prims:
        if p[0] == "box": pts += [p[1], p[2]]
        elif p[0] == "cap": pts += [p[1] - p[3], p[1] + p[3], p[2] - p[3], p[2] + p[3]]
        else: pts += [p[1] - p[2], p[1] + p[2]]
    pts = np.array(pts); c = (pts.min(0) + pts.max(0)) / 2
    return c, np.linalg.norm(pts.max(0) - c) + 1e-3

def ring(pts, r, alb): return [cap(pts[i], pts[(i + 1) % len(pts)], r, alb) for i in range(len(pts))]

SKIN = (0.74, 0.66, 0.60); SHIRT = (0.50, 0.50, 0.53); HAIR = (0.16, 0.14, 0.13)
LEATHER = (0.12, 0.12, 0.13); TRIM = (0.09, 0.09, 0.10); BODY = (0.20, 0.20, 0.22)

# Driver faces +z (windshield). Eyes at EYES2. His local axes: R = his right (-x), U = up, F = facing (+z).
EYES2 = np.array([0.0, 1.00, 0.0])
HEAD2 = EYES2 + np.array([0, 0.005, -0.072])
def lp(r, u, f): return HEAD2 + np.array([-r, u, f])

static = []      # list of groups: (center, radius, [prims])
def group(prims): static.append((*bound(prims), prims))

# head, built with the same proportions as scene 1 so the opening close-up matches
group([ell(lp(0, 0, 0), (0.078, 0.105, 0.085), SKIN),
       ell(lp(0, -0.10, 0.022), (0.058, 0.045, 0.052), SKIN),
       ell(lp(0, -0.04, 0.09), (0.012, 0.024, 0.016), SKIN),
       ell(lp(0, 0.03, 0.005), (0.082, 0.09, 0.07), HAIR)]
      + [ell(lp(sx, 0.019, 0.076), (0.020, 0.004, 0.008), (0.20, 0.17, 0.15)) for sx in (-0.031, 0.031)])
def eyes(open_):
    out = []
    for sx in (-0.031, 0.031):
        if open_:
            out += [ell(lp(sx, -0.005, 0.072), (0.015, 0.007, 0.008), (0.85, 0.85, 0.83)),
                    ell(lp(sx, -0.005, 0.0785), (0.0045, 0.0045, 0.0045), (0.05, 0.04, 0.04))]
        else:
            out += [ell(lp(sx, -0.005, 0.073), (0.017, 0.0035, 0.008), (0.10, 0.08, 0.08))]
    return out

# body in the grey home T-shirt, hands on the wheel at ten and two
WC = np.array([0.0, 0.70, 0.40]); WR = 0.18
WY = np.array([0, np.cos(np.radians(20)), -np.sin(np.radians(20))])   # wheel top leans toward the driver
def wpt(deg): return WC + WR * (np.cos(np.radians(deg)) * np.array([1.0, 0, 0]) + np.sin(np.radians(deg)) * WY)
group([ell(lp(0, -0.17, -0.02), (0.055, 0.08, 0.055), SKIN),
       ell(lp(0, -0.29, -0.07), (0.22, 0.07, 0.09), SHIRT),
       ell(EYES2 + (0, -0.445, -0.132), (0.21, 0.28, 0.13), SHIRT)])
for side in (-1, 1):
    sh = np.array([0.19 * side, 0.74, -0.10]); el = np.array([0.25 * side, 0.58, 0.13]); hd = wpt(90 - 60 * side)
    mid = sh + (el - sh) * 0.45
    group([cap(sh, mid, 0.047, SHIRT), cap(mid, el, 0.040, SKIN), cap(el, hd, 0.034, SKIN), ell(hd, (0.045, 0.040, 0.042), SKIN)])
group(ring([wpt(a) for a in range(0, 360, 10)], 0.018, TRIM)
      + [ell(WC, (0.065, 0.065, 0.035), TRIM), cap(WC, (0, 0.62, 0.62), 0.035, TRIM),
         cap(wpt(200), WC, 0.014, TRIM), cap(wpt(340), WC, 0.014, TRIM), cap(wpt(270), WC, 0.014, TRIM)])

# cabin of a low GT coupe (driver on the left side of the car = +x is his door)
group([box((-1.30, 0.05, -0.80), (0.50, 0.12, 0.95), BODY),                      # floor
       box((-1.30, 1.24, -0.70), (0.50, 1.30, 0.80), (0.30, 0.30, 0.31)),        # roof / headliner
       box((0.42, 0.12, -0.70), (0.50, 0.76, 0.90), BODY),                       # driver door
       box((-1.38, 0.12, -0.70), (-1.30, 0.76, 0.90), BODY),                     # passenger door
       box((0.36, 0.76, 0.74), (0.46, 1.24, 0.86), BODY),                        # A-pillar driver
       box((-1.34, 0.76, 0.74), (-1.24, 1.24, 0.86), BODY),                      # A-pillar passenger
       box((0.36, 0.76, -0.62), (0.48, 1.24, -0.48), BODY),                      # B-pillar driver
       box((-1.36, 0.76, -0.62), (-1.24, 1.24, -0.48), BODY),                    # B-pillar passenger
       box((-1.30, 0.12, -0.80), (0.50, 0.86, -0.72), BODY),                     # rear bulkhead (glass above)
       box((-1.30, 1.10, 0.80), (0.50, 1.24, 0.88), BODY)])                      # windshield header
group([box((-1.30, 0.55, 0.55), (0.42, 0.76, 0.95), TRIM),                        # dashboard
       box((-0.22, 0.76, 0.52), (0.22, 0.82, 0.70), TRIM),                        # instrument hood
       box((-0.44, 0.12, -0.25), (-0.26, 0.52, 0.58), TRIM),                      # centre console
       box((-0.37, 0.62, 0.505), (-0.30, 0.76, 0.515), (0.05, 0.05, 0.06)),       # PHONE in vent holder (out of frame here)
       box((-0.355, 0.60, 0.515), (-0.315, 0.63, 0.55), TRIM)])
for x0 in (0.0, -0.80):                                                          # driver + passenger bucket seats
    group([box((x0 - 0.27, 0.22, -0.32), (x0 + 0.27, 0.40, 0.25), LEATHER),
           box((x0 - 0.27, 0.40, -0.34), (x0 + 0.27, 1.00, -0.20), LEATHER),
           box((x0 - 0.33, 0.30, -0.34), (x0 - 0.25, 0.92, -0.10), LEATHER),
           box((x0 + 0.25, 0.30, -0.34), (x0 + 0.33, 0.92, -0.10), LEATHER),
           box((x0 - 0.13, 1.04, -0.30), (x0 + 0.13, 1.22, -0.19), LEATHER),
           box((x0 - 0.04, 1.00, -0.26), (x0 + 0.04, 1.04, -0.23), TRIM)])

# ---------------- lights ----------------
# scene 1's moon key re-expressed in the upright head's own axes, so the opening close-up is lit like scene 1's last frame
L_KEY = n(np.array([-0.872, -0.105, 0.48]))
KEY = np.array([0.62, 0.74, 1.00]) * 0.85
L_BAND = n(np.array([-0.50, 0.05, 0.86]))        # passing street lights, low through the windshield from frame-left
L_DASH = n(np.array([0.0, -0.45, 0.9]))          # instrument glow from below-front
DASH = np.array([0.55, 0.65, 0.80]) * 0.16
AMB = np.array([0.05, 0.055, 0.07])
BAND_S, BAND_V, BAND_W, BAND_T0 = 1.8, 2.4, 0.22, 0.20   # first (amber) band crosses the face at ~0.55 s
BAND_COLS = [np.array([1.0, 0.62, 0.28]) * 1.6, np.array([0.95, 0.25, 0.75]) * 1.3, np.array([0.25, 0.80, 1.0]) * 1.3]
CITY_V = 14.0                                    # m/s, how fast the street slides past the windows

def bands(p, t):
    ph = (p[..., 2] + BAND_V * (t - BAND_T0)) / BAND_S
    k = np.floor(ph).astype(int); fr = ph - k
    w = np.exp(-((fr - 0.5) * BAND_S) ** 2 / (2 * BAND_W ** 2))
    col = np.zeros(p.shape);
    for i, c in enumerate(BAND_COLS):
        col += (np.mod(k, 3) == i)[..., None] * c
    return col * w[..., None]

def city(d, o, t):
    """Street outside: building rows at x=+-9 sliding backward, dashed lane line on the road, dark sky."""
    col = np.zeros(d.shape) + np.array([0.04, 0.05, 0.10]) * (0.6 + 0.4 * np.clip(d[..., 1] * 2 + 0.5, 0, 1))[..., None]
    side = np.sign(d[..., 0]); side = np.where(side == 0, 1, side)
    tb = (9.0 * side - o[..., 0]) / np.where(np.abs(d[..., 0]) < 1e-6, 1e-6 * side, d[..., 0])
    py = o[..., 1] + tb * d[..., 1]; pz = o[..., 2] + tb * d[..., 2] + CITY_V * t
    bi = np.floor(pz / 7.0); hgt = 6 + 16 * (np.abs(np.sin(bi * 12.9898 + side * 3.1) * 43758.5453) % 1)
    inb = (tb > 0) & (py > -1) & (py < hgt) & ((pz / 7.0) % 1 > 0.06)
    lit = (np.abs(np.sin(np.floor(pz * 1.6) * 7.1 + np.floor(py * 1.4) * 3.7 + side) * 9137.3) % 1) > 0.55
    win = inb & ((pz * 1.6) % 1 > 0.4) & ((py * 1.4) % 1 > 0.45) & lit
    neon = inb & (np.abs(py - 3.2) < 0.35) & ((pz / 7.0) % 1 > 0.25) & ((pz / 7.0) % 1 < 0.75) & ((bi % 3) == 0)
    col = np.where(inb[..., None], np.array([0.03, 0.03, 0.045]), col)
    col = np.where(win[..., None], np.array([1.0, 0.72, 0.40]) * 0.8, col)
    col = np.where(neon[..., None], np.where(((bi // 3) % 2 == 0)[..., None], np.array([1.0, 0.2, 0.75]), np.array([0.2, 0.85, 1.0])), col)
    # road (y=0) hit before the buildings
    tg = -o[..., 1] / np.where(d[..., 1] < -1e-6, d[..., 1], -1e-6)
    road = (d[..., 1] < -1e-6) & ((tg < tb) | (tb <= 0))
    gx = o[..., 0] + tg * d[..., 0]; gz = o[..., 2] + tg * d[..., 2] + CITY_V * t
    dash = road & (np.abs(gx - 1.9) < 0.07) & ((gz % 6.0) < 3.0)
    col = np.where(road[..., None], np.array([0.035, 0.035, 0.04]), col)
    col = np.where(dash[..., None], np.array([0.55, 0.55, 0.5]), col)
    return col

# ---------------- tracing ----------------
def hit_prims(prims, o, d, inv, tbest, nrm, alb):
    for p in prims:
        if p[0] == "box":
            _, lo, hi, a = p
            t1 = (lo - o) * inv; t2 = (hi - o) * inv
            tmin = np.minimum(t1, t2); tmax = np.maximum(t1, t2)
            tn = tmin.max(-1); tf = tmax.min(-1)
            hit = (tf >= np.maximum(tn, 1e-4)) & (tn > 1e-4) & (tn < tbest)
            if hit.any():
                tbest[hit] = tn[hit]
                ax = tmin[hit].argmax(-1)
                nn = np.zeros((hit.sum(), 3)); nn[np.arange(len(ax)), ax] = 1.0
                nrm[hit] = nn * -np.sign(d[hit]); alb[hit] = a
        elif p[0] == "cap":
            _, pa, pb, r, a = p
            ba = pb - pa; oa = o - pa
            baba = ba @ ba; bard = d @ ba; baoa = oa @ ba; rdoa = (d * oa).sum(-1); oaoa = (oa * oa).sum(-1)
            qa = np.maximum(baba - bard * bard, 1e-12); qb = baba * rdoa - baoa * bard; qc = baba * oaoa - baoa * baoa - r * r * baba
            h = qb * qb - qa * qc
            t = (-qb - np.sqrt(np.maximum(h, 0))) / qa
            y = baoa + t * bard
            body = (h >= 0) & (y > 0) & (y < baba)
            oc = np.where((y <= 0)[:, None], oa, o - pb)
            cb = (d * oc).sum(-1); ccap = (oc * oc).sum(-1) - r * r; hc = cb * cb - ccap
            tc = -cb - np.sqrt(np.maximum(hc, 0))
            t = np.where(body, t, np.where((h >= 0) & (hc > 0), tc, np.inf))
            hit = np.isfinite(t) & (t > 1e-4) & (t < tbest)
            if hit.any():
                tbest[hit] = t[hit]
                pp = o[hit] + d[hit] * t[hit][:, None]
                hh = np.clip(((pp - pa) @ ba) / baba, 0, 1)
                nn = pp - pa - hh[:, None] * ba; nrm[hit] = nn / np.linalg.norm(nn, axis=-1, keepdims=True); alb[hit] = a
        else:
            _, c, r, a = p
            oc = (o - c) / r; dd = d / r
            A = (dd * dd).sum(-1); B = 2 * (oc * dd).sum(-1); C = (oc * oc).sum(-1) - 1
            disc = B * B - 4 * A * C
            ok = disc > 0
            t = (-B - np.sqrt(np.where(ok, disc, 0))) / (2 * A)
            hit = ok & (t > 1e-4) & (t < tbest)
            if hit.any():
                tbest[hit] = t[hit]
                pp = o[hit] + d[hit] * t[hit][:, None]
                nn = (pp - c) / (r * r); nrm[hit] = nn / np.linalg.norm(nn, axis=-1, keepdims=True); alb[hit] = a

def trace(groups, o, d):
    m = d.shape[0]
    tbest = np.full(m, np.inf); nrm = np.zeros((m, 3)); alb = np.zeros((m, 3))
    inv = 1.0 / np.where(np.abs(d) < 1e-9, 1e-9, d)
    for c, rad, prims in groups:
        oc = o - c; b = (oc * d).sum(-1); cc = (oc * oc).sum(-1) - rad * rad
        disc = b * b - cc
        sel = (disc > 0) & ((-b + np.sqrt(np.maximum(disc, 0))) > 1e-4)
        if not sel.any(): continue
        idx = np.nonzero(sel)[0]
        tb, nb, ab = tbest[idx], nrm[idx], alb[idx]
        hit_prims(prims, o[idx], d[idx], inv[idx], tb, nb, ab)
        tbest[idx], nrm[idx], alb[idx] = tb, nb, ab
    return tbest, nrm, alb

def shadow(groups, p, nrm, L, need):
    lit = np.zeros(len(p), bool)
    if need.any():
        so = p[need] + nrm[need] * 2e-3
        ts, _, _ = trace(groups, so, np.broadcast_to(L, so.shape).copy())
        lit[need] = ~np.isfinite(ts)
    return lit

def shade(groups, o, d, t):
    tt, nrm, alb = trace(groups, o, d)
    miss = ~np.isfinite(tt)
    p = o + d * np.where(miss, 0, tt)[:, None]
    nk = np.clip((nrm * L_KEY).sum(-1), 0, 1); nb = np.clip((nrm * L_BAND).sum(-1), 0, 1)
    nd = np.clip((nrm * L_DASH).sum(-1), 0, 1)
    lk = np.ones(len(p), bool)                       # soft city glow: unshadowed fill-key
    bcol = bands(p, t)
    lb = shadow(groups, p, nrm, L_BAND, (nb > 0) & ~miss & (bcol.max(-1) > 0.02))
    col = alb * (AMB + KEY * (nk * lk)[:, None] + bcol * (nb * lb)[:, None] + DASH * nd[:, None])
    return np.where(miss[:, None], city(d, o, t), col)

# ---------------- camera ----------------
SW, SH = 20.25, 36.0
# opening = scene 1's landing, rebuilt around an upright face: same 0.306 m distance, same 11° offset toward the chin, 58 mm
P_A = EYES2 + np.array([0, -0.055, 0.30]); T_A = EYES2 + np.array([0, 0.006, 0]); F_A = 58.0
# landing = 3/4 interior from the passenger side of the windshield, eye level, head + shoulders + hands on the wheel
AZ_B, DIST_B, H_B = np.radians(35), 0.75, -0.05
T_B = EYES2 + np.array([0, -0.11, -0.04]); F_B = 32.0
def ease(x): return x * x * x * (x * (6 * x - 15) + 10)
def cam(f):
    s = ease(np.clip((f - 20) / 66.0, 0, 1))           # 1-20 locked (match + eyes open), 20-86 pull back, then hold
    az = AZ_B * s; dist = 0.306 + (DIST_B - 0.306) * s
    p = EYES2 + np.array([-np.sin(az) * dist, -0.055 + (H_B + 0.055) * s, np.cos(az) * dist])
    if s == 0: p = P_A.copy()
    tgt = T_A + (T_B - T_A) * s
    foc = F_A + (F_B - F_A) * s
    # road vibration fades in once we are in the moving car (none on the matching frames)
    amp = np.clip((f - 24) / 30.0, 0, 1)
    tt = f / FPS
    p = p + amp * np.array([0.0012 * np.sin(23 * tt), 0.0018 * np.sin(31 * tt + 1.3) + 0.0008 * np.sin(57 * tt), 0.0])
    return p, tgt, foc

FLARE0 = 104                                           # passing streetlight flare, peaks at frame 116 (cut point)

ys, xs = np.mgrid[0:H, 0:W]
SAMPLES = ((-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25))
for f in FRAMES:
    t = (f - 1) / FPS
    groups = static + [(*bound(e := eyes(f >= 16)), e)]
    p, tgt, foc = cam(f)
    fw = n(tgt - p); rt = n(np.cross(fw, [0, 1, 0])); up = np.cross(rt, fw)
    acc = np.zeros((H * W, 3))
    for jx, jy in SAMPLES:
        nx = (xs + 0.5 + jx) / W * 2 - 1; ny = 1 - (ys + 0.5 + jy) / H * 2
        d = fw * foc + rt * (nx[..., None] * SW / 2) + up * (ny[..., None] * SH / 2)
        d = (d / np.linalg.norm(d, axis=-1, keepdims=True)).reshape(-1, 3)
        acc += shade(groups, np.broadcast_to(p, d.shape).copy(), d, t)
    img = (acc / len(SAMPLES)).reshape(H, W, 3)
    if f >= FLARE0:
        # a streetlight passes over the car: its anamorphic streak crosses the frame and peaks at frame 116
        # (the cut point); the full white flash is added in the edit, not baked into the shot
        a = (f - FLARE0) / (116 - FLARE0)
        k = np.clip(a, 0, 1) ** 1.5 if f <= 116 else 1.0 - 0.18 * (f - 116)
        yc = (0.22 + 0.10 * min(a, 1.2)) * H
        line = np.exp(-((ys - yc) / (0.006 * H)) ** 2)
        glow = np.exp(-((ys - yc) / (0.07 * H)) ** 2) * np.exp(-((xs - (0.85 - 0.25 * a) * W) / (0.35 * W)) ** 2)
        img = img + (line * 1.4 + glow * 0.9)[..., None] * np.array([0.75, 0.88, 1.0]) * k
    img = np.clip(img, 0, 1) ** (1 / 2.2)
    Image.fromarray((img * 255).astype(np.uint8)).save(f"{OUT}/f{f:04d}.png")
    print(f, flush=True)
