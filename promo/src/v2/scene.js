// Промо PRO NEURO v2 (продающая версия), 60 с. Как и в v1, кадр целиком считается из t
// в renderAt(t): без requestAnimationFrame и накоплений. Сценарий — ../../CONCEPT_V2.md.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import qrcode from '/vendor/lib/qrcode.mjs';

const W = 1920, H = 1080, FPS = 30;
const BEAT = 0.46875, BAR = 1.875;
const bar = (n) => (n - 1) * BAR;

// ключевые моменты (по сетке трека)
const T = {
  hook2: bar(2), hook3: bar(3), hook4: bar(4), shatter: bar(4) + BEAT, drop: 7.5,
  count: bar(6), days: bar(7), globe: bar(8), gallery: 15, brk: 22.5, strike: bar(14),
  build: 26.25, warp: bar(16), drop2: 30, chips: bar(19), reviews: 37.5, formats: bar(23),
  dome: 45, end: 52.5, lock: 56.25,
};

// ---------- утилиты ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const prog = (t, a, b) => clamp((t - a) / (b - a));
const eOutCubic = (x) => 1 - Math.pow(1 - x, 3);
const eInOutCubic = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const eOutExpo = (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
const eInCubic = (x) => x * x * x;
const eOutBack = (x, s = 1.7) => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2);
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let r = Math.imul(a ^ (a >>> 15), 1 | a);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}
const v3 = (x, y, z) => new THREE.Vector3(x, y, z);

const GOLD = new THREE.Color('#C9A227');
const CREAM = new THREE.Color('#F9E9B4');
const GOLD_DARK = new THREE.Color('#9C7A22');

// ---------- данные ----------
const [beats, works, manifest] = await Promise.all([
  fetch('/music/beats.json').then((r) => r.json()),
  fetch('/works/works.json').then((r) => r.json()),
  fetch('/works/manifest.json').then((r) => r.json()),
]);
const KICKS = beats.kicks;
function sinceKick(t) {
  let lo = 0, hi = KICKS.length - 1, k = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (KICKS[m] <= t + 1e-6) { k = m; lo = m + 1; } else hi = m - 1; }
  return k < 0 ? 1e9 : t - KICKS[k];
}
const kickEnv = (t) => Math.exp(-sinceKick(t) * 9);

await document.fonts.load('800 100px Unbounded');
await document.fonts.load('600 100px Unbounded');
await document.fonts.load('700 100px Manrope');
await document.fonts.load('600 100px Manrope');

// ---------- рендерер ----------
const canvas = document.getElementById('gl');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.setClearColor(0x070605, 1);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, W / H, 0.05, 400);

const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
composer.setPixelRatio(1);
composer.setSize(W, H);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.8, 0.5, 1.0);
composer.addPass(bloom);
composer.addPass(new OutputPass());
const finalPass = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, uSeed: { value: 0 }, uAb: { value: 0 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform float uSeed, uAb; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + uSeed*7.13) * 43758.5453); }
    void main(){
      vec2 d = (vUv - .5) * uAb;                       // хроматическая аберрация на ударах
      vec3 c = vec3(texture2D(tDiffuse, vUv + d).r, texture2D(tDiffuse, vUv).g, texture2D(tDiffuse, vUv - d).b);
      vec2 q = vUv - .5; q.x *= 1.25;
      c *= mix(1., smoothstep(.95, .25, length(q)), .72);
      c += (h(vUv * vec2(1920., 1080.)) - .5) * .045;
      gl_FragColor = vec4(c, 1.);
    }`,
});
composer.addPass(finalPass);

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,240,200,.55)');
  gr.addColorStop(0.6, 'rgba(201,162,39,.12)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}
const GLOW = glowTexture();

// ---------- 3D-текст: надписи на канве → текстура ----------
function roundRect(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}
function wrap(g, text, maxW) {
  const words = text.split(' '), lines = []; let cur = '';
  for (const w of words) { const s = cur ? cur + ' ' + w : w; if (g.measureText(s).width > maxW && cur) { lines.push(cur); cur = w; } else cur = s; }
  if (cur) lines.push(cur); return lines;
}
// карточка: тёмная панель с золотой рамкой и текстом
function cardTexture({ text, font = '700 84px Unbounded', w = 1400, h = 300, color = '#F9E9B4', pill = false, sub = null }) {
  const c = document.createElement('canvas');
  if (w === 'auto') { const m = c.getContext('2d'); m.font = font; w = Math.ceil(m.measureText(text).width + h * 0.9); }
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  const r = pill ? h / 2 : 36;
  roundRect(g, 6, 6, w - 12, h - 12, r); g.fillStyle = 'rgba(14,12,9,0.88)'; g.fill();
  g.lineWidth = 6; g.strokeStyle = '#C9A227'; g.stroke();
  g.fillStyle = color; g.font = font; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText(text, w / 2, sub ? h * 0.4 : h / 2 + 4);
  if (sub) { g.font = '700 54px Manrope'; g.fillStyle = '#C9A227'; g.fillText(sub, w / 2, h * 0.72); }
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  return { tex, aspect: w / h };
}
function loadImage(src) { return new Promise((ok, fail) => { const im = new Image(); im.onload = () => ok(im); im.onerror = fail; im.src = src; }); }
async function reviewTexture({ avatar, quote, name }) {
  const w = 1600, h = 560, c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d');
  roundRect(g, 6, 6, w - 12, h - 12, 44); g.fillStyle = 'rgba(16,14,10,0.92)'; g.fill();
  g.lineWidth = 6; g.strokeStyle = '#C9A227'; g.stroke();
  const im = await loadImage(avatar);
  g.save(); g.beginPath(); g.arc(200, h / 2, 140, 0, Math.PI * 2); g.clip();
  const s = Math.max(280 / im.width, 280 / im.height);
  g.drawImage(im, 200 - im.width * s / 2, h / 2 - im.height * s / 2, im.width * s, im.height * s); g.restore();
  g.beginPath(); g.arc(200, h / 2, 142, 0, Math.PI * 2); g.lineWidth = 6; g.strokeStyle = '#C9A227'; g.stroke();
  g.fillStyle = '#C9A227'; g.font = '800 150px Unbounded'; g.fillText('“', 400, 170);
  g.font = '700 64px Manrope'; g.fillStyle = '#F9E9B4';
  const lines = wrap(g, quote, w - 500);
  lines.forEach((l, i) => g.fillText(l, 410, 210 + i * 84));
  g.font = '700 48px Manrope'; g.fillStyle = '#C9A227'; g.fillText(name, 410, 210 + lines.length * 84 + 56);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  return { tex, aspect: w / h };
}
// материал для карточек/чипсов: текстура + прозрачность + зачёркивание
function cardMaterial(tex) {
  return new THREE.ShaderMaterial({
    uniforms: { map: { value: tex }, uOpacity: { value: 0 }, uStrike: { value: 0 }, uDim: { value: 1 }, uGold: { value: GOLD.clone() } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }`,
    fragmentShader: `
      uniform sampler2D map; uniform float uOpacity, uStrike, uDim; uniform vec3 uGold; varying vec2 vUv;
      void main(){
        vec4 c = texture2D(map, vUv);
        vec3 col = c.rgb * uDim;
        float x0 = .07, x1 = .07 + .86 * uStrike;
        float s = step(x0, vUv.x) * step(vUv.x, x1) * smoothstep(.06, .035, abs(vUv.y - .5 - (vUv.x - .5) * .08));
        col = mix(col, uGold * 2.6, s * step(.001, uStrike));
        gl_FragColor = vec4(col, max(c.a, s) * uOpacity);
      }`,
    transparent: true, depthWrite: false, side: THREE.DoubleSide,
  });
}
function makeCard(texInfo, height) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(height * texInfo.aspect, height), cardMaterial(texInfo.tex));
  m.visible = false; scene.add(m); return m;
}

// ---------- частицы и варп (как в v1) ----------
const N_P = 4200;
const pGeo = new THREE.BufferGeometry();
{
  const r = rng(7), pos = new Float32Array(N_P * 3), size = new Float32Array(N_P), ph = new Float32Array(N_P);
  for (let i = 0; i < N_P; i++) {
    let x, y;
    do { x = (r() - 0.5) * 70; y = (r() - 0.5) * 44; } while (x * x + y * y < 4);
    pos.set([x, y, -90 + r() * 180], i * 3);
    size[i] = 0.6 + Math.pow(r(), 3) * 3.2; ph[i] = r();
  }
  pGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  pGeo.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
  pGeo.setAttribute('aPhase', new THREE.BufferAttribute(ph, 1));
}
const pMat = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 }, uPulse: { value: 0 }, uOpacity: { value: 1 }, uColor: { value: GOLD.clone() } },
  vertexShader: `
    attribute float aSize; attribute float aPhase; uniform float uTime, uPulse, uOpacity; varying float vA;
    void main(){
      vec3 p = position;
      p.y += sin(uTime * .35 + aPhase * 6.283) * .35; p.x += cos(uTime * .27 + aPhase * 12.) * .3;
      vec4 mv = modelViewMatrix * vec4(p, 1.);
      gl_Position = projectionMatrix * mv;
      gl_PointSize = min(40., aSize * 210. * (1. + .6 * uPulse) / -mv.z);
      vA = (.55 + .45 * sin(uTime * 2.1 + aPhase * 40.)) * uOpacity * smoothstep(.6, 4., -mv.z) * smoothstep(140., 60., -mv.z);
    }`,
  fragmentShader: `uniform vec3 uColor; varying float vA;
    void main(){ float d = length(gl_PointCoord - .5); float a = smoothstep(.5, .0, d); a *= a; gl_FragColor = vec4(uColor * 1.15 * a * vA, 1.); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});
scene.add(new THREE.Points(pGeo, pMat));
const N_W = 1600;
const wGeo = new THREE.BufferGeometry();
{
  const src = pGeo.attributes.position.array, ph = pGeo.attributes.aPhase.array;
  const pos = new Float32Array(N_W * 6), tail = new Float32Array(N_W * 2), wph = new Float32Array(N_W * 2);
  for (let i = 0; i < N_W; i++) {
    const j = i * 2 + 1;
    for (let k = 0; k < 2; k++) { pos.set(src.slice(j * 3, j * 3 + 3), (i * 2 + k) * 3); tail[i * 2 + k] = k; wph[i * 2 + k] = ph[j]; }
  }
  wGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  wGeo.setAttribute('aTail', new THREE.BufferAttribute(tail, 1));
  wGeo.setAttribute('aPhase', new THREE.BufferAttribute(wph, 1));
}
const wMat = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 }, uStretch: { value: 0 }, uOpacity: { value: 0 }, uColor: { value: CREAM.clone() } },
  vertexShader: `
    attribute float aTail; attribute float aPhase; uniform float uTime, uStretch; varying float vA; varying float vT;
    void main(){
      vec3 p = position;
      p.y += sin(uTime * .35 + aPhase * 6.283) * .35; p.x += cos(uTime * .27 + aPhase * 12.) * .3;
      p.z += aTail * uStretch * (.6 + aPhase);
      vec4 mv = modelViewMatrix * vec4(p, 1.);
      gl_Position = projectionMatrix * mv; vT = aTail; vA = smoothstep(.5, 3., -mv.z);
    }`,
  fragmentShader: `uniform vec3 uColor; uniform float uOpacity; varying float vA; varying float vT;
    void main(){ gl_FragColor = vec4(uColor * 2.2 * uOpacity * vA * (1. - vT * .85), 1.); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});
const warp = new THREE.LineSegments(wGeo, wMat); scene.add(warp);

// ---------- нейросфера (как в v1, старт сборки — от места разлёта осколков) ----------
const sphere = new THREE.Group(); scene.add(sphere);
const R_SPHERE = 2.3;
const nodes = [], edges = [];
{
  const g = new THREE.IcosahedronGeometry(R_SPHERE, 2);
  const p = g.attributes.position.array, map = new Map(), idx = [];
  for (let i = 0; i < p.length / 3; i++) {
    const key = [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]].map((v) => v.toFixed(4)).join(',');
    if (!map.has(key)) { map.set(key, nodes.length); nodes.push(v3(p[i * 3], p[i * 3 + 1], p[i * 3 + 2])); }
    idx.push(map.get(key));
  }
  const seen = new Set();
  for (let f = 0; f < idx.length; f += 3) {
    for (const [a, b] of [[idx[f], idx[f + 1]], [idx[f + 1], idx[f + 2]], [idx[f + 2], idx[f]]]) {
      const k = a < b ? `${a}_${b}` : `${b}_${a}`;
      if (!seen.has(k)) { seen.add(k); edges.push([a, b]); }
    }
  }
}
const nodeStart = [], nodeDelay = [];
{
  const r = rng(11);
  for (let i = 0; i < nodes.length; i++) {
    nodeStart.push(v3((r() - 0.5) * 9, (r() - 0.5) * 5, (r() - 0.5) * 4 + 1));
    nodeDelay.push(r() * 0.62);
  }
}
const sU = { uAsm: { value: 1 }, uOpen: { value: 0 }, uPulse: { value: 0 }, uI: { value: 1 }, uTime: { value: 0 } };
const SPHERE_VERT = `
  attribute vec3 aStart; attribute float aDelay;
  uniform float uAsm, uOpen, uPulse, uTime;
  float local(float d){ float x = clamp((uAsm - d) / .38, 0., 1.); return 1. - pow(1. - x, 3.); }
  vec3 place(vec3 target, vec3 start, float d){
    float k = local(d);
    float n = sin(dot(target, vec3(3.1, 1.7, 2.3)) + uTime * 1.3) * .05;
    return mix(start, target * (1. + uOpen * .32 + uPulse * .06 + n), k);
  }`;
const nodeGeo = new THREE.BufferGeometry();
{
  const pos = new Float32Array(nodes.length * 3), st = new Float32Array(nodes.length * 3), dl = new Float32Array(nodes.length);
  nodes.forEach((n, i) => { pos.set([n.x, n.y, n.z], i * 3); st.set([nodeStart[i].x, nodeStart[i].y, nodeStart[i].z], i * 3); dl[i] = nodeDelay[i]; });
  nodeGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  nodeGeo.setAttribute('aStart', new THREE.BufferAttribute(st, 3));
  nodeGeo.setAttribute('aDelay', new THREE.BufferAttribute(dl, 1));
}
const nodeMat = new THREE.ShaderMaterial({
  uniforms: { ...sU, uColor: { value: CREAM.clone() } },
  vertexShader: SPHERE_VERT + `
    varying float vA;
    void main(){
      vec4 mv = modelViewMatrix * vec4(place(position, aStart, aDelay), 1.); gl_Position = projectionMatrix * mv;
      gl_PointSize = min(36., 620. * (1. + uPulse * .6) / -mv.z);
      vA = .35 + .65 * local(aDelay);
    }`,
  fragmentShader: `uniform vec3 uColor; uniform float uI; varying float vA;
    void main(){ float d = length(gl_PointCoord - .5); float core = smoothstep(.16, .0, d); float halo = smoothstep(.5, .0, d);
      gl_FragColor = vec4(uColor * uI * vA * (core * 2.4 + halo * halo * .3), 1.); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});
sphere.add(new THREE.Points(nodeGeo, nodeMat));
const edgeGeo = new THREE.BufferGeometry();
{
  const E = edges.length, pos = new Float32Array(E * 6), st = new Float32Array(E * 6), dl = new Float32Array(E * 2), od = new Float32Array(E * 2);
  edges.forEach(([a, b], i) => {
    for (const [k, v, o] of [[0, a, b], [1, b, a]]) {
      const n = nodes[v], s = nodeStart[v];
      pos.set([n.x, n.y, n.z], (i * 2 + k) * 3); st.set([s.x, s.y, s.z], (i * 2 + k) * 3);
      dl[i * 2 + k] = nodeDelay[v]; od[i * 2 + k] = nodeDelay[o];
    }
  });
  edgeGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  edgeGeo.setAttribute('aStart', new THREE.BufferAttribute(st, 3));
  edgeGeo.setAttribute('aDelay', new THREE.BufferAttribute(dl, 1));
  edgeGeo.setAttribute('aOther', new THREE.BufferAttribute(od, 1));
}
const edgeMat = new THREE.ShaderMaterial({
  uniforms: { ...sU, uColor: { value: GOLD.clone() } },
  vertexShader: SPHERE_VERT + `
    attribute float aOther; varying float vA;
    void main(){
      vec4 mv = modelViewMatrix * vec4(place(position, aStart, aDelay), 1.); gl_Position = projectionMatrix * mv;
      vA = min(local(aDelay), local(aOther)); vA *= vA;
    }`,
  fragmentShader: `uniform vec3 uColor; uniform float uI; varying float vA;
    void main(){ gl_FragColor = vec4(uColor * uI * vA * 1.35, 1.); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});
sphere.add(new THREE.LineSegments(edgeGeo, edgeMat));
for (const k of Object.keys(sU)) { nodeMat.uniforms[k] = sU[k]; edgeMat.uniforms[k] = sU[k]; }
const inner = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.15, 0)),
  new THREE.LineBasicMaterial({ color: CREAM.clone().multiplyScalar(1.6), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
sphere.add(inner);
const core = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: GOLD.clone().multiplyScalar(2.2), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
core.scale.setScalar(5.5); sphere.add(core);

const RING_T = [T.drop, T.drop2, T.dome, T.lock];
const rings = RING_T.map(() => {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.96, 1, 128), new THREE.MeshBasicMaterial({
    color: CREAM.clone().multiplyScalar(2.5), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
  }));
  scene.add(m); return m;
});

// ---------- работы: текстуры, кадры видео ----------
const loader = new THREE.TextureLoader();
const textures = {};
for (const w of works.works) {
  const m = manifest[w.slug]; if (!m) continue;
  const tex = await loader.loadAsync('/' + m.still);
  tex.colorSpace = THREE.SRGBColorSpace; tex.minFilter = THREE.LinearFilter; tex.generateMipmaps = false;
  textures[w.slug] = { tex, frames: m.frames, count: m.count || 0, cur: -1 };
}
const bitmapCache = new Map();
async function videoFrame(slug, local) {
  const e = textures[slug]; if (!e || !e.count) return;
  const i = Math.max(0, Math.floor(local * FPS + 1e-6)) % e.count;
  if (i === e.cur) return;
  const url = `/${e.frames}/${String(i + 1).padStart(4, '0')}.jpg`;
  let bmp = bitmapCache.get(url);
  if (!bmp) {
    bmp = await createImageBitmap(await (await fetch(url)).blob(), { imageOrientation: 'flipY' });
    bitmapCache.set(url, bmp);
    if (bitmapCache.size > 500) { const [k, v] = bitmapCache.entries().next().value; v.close(); bitmapCache.delete(k); }
  }
  if (!e.isVideo) { e.tex.dispose(); e.tex = new THREE.Texture(); e.tex.colorSpace = THREE.SRGBColorSpace; e.tex.minFilter = THREE.LinearFilter; e.tex.generateMipmaps = false; e.tex.flipY = false; e.isVideo = true; }
  e.tex.image = bmp; e.tex.needsUpdate = true; e.cur = i;
}

// ---------- экран с работой: формат задаётся uHalf, можно менять на лету ----------
const SW = 3.2, SH = 1.8, MARGIN = 0.22;
const screenFrag = `
  uniform sampler2D map; uniform vec2 uImg, uHalf, uOuter, uPan; uniform float uZoom, uOpacity, uBright, uGlow; uniform vec3 uGold;
  varying vec2 vUv;
  float sdBox(vec2 p, vec2 b, float r){ vec2 q = abs(p) - b + r; return length(max(q, 0.)) + min(max(q.x, q.y), 0.) - r; }
  void main(){
    vec2 q = (vUv - .5) * uOuter;
    float d = sdBox(q, uHalf, .07);
    float inside = smoothstep(.006, -.006, d);
    vec3 col; float a = inside;
    if (gl_FrontFacing) {
      vec2 cuv = q / (2. * uHalf) + .5;
      float ca = uHalf.x / uHalf.y, ia = uImg.x / uImg.y;
      if (ia > ca) cuv.x = (cuv.x - .5) * ca / ia + .5; else cuv.y = (cuv.y - .5) * ia / ca + .5;
      cuv = (cuv - .5) / uZoom + .5 + uPan;
      col = texture2D(map, cuv).rgb * uBright * inside;
    } else {
      col = mix(vec3(.02), uGold * .25, smoothstep(1.6, 0., length(q))) * inside;
    }
    float line = exp(-abs(d) * 70.) * (.55 + uGlow);
    float halo = exp(-max(d, 0.) * 9.) * step(0., d) * .45 * uGlow;
    col += uGold * (line * 2.4 + halo);
    a = max(a, clamp(line + halo, 0., 1.));
    gl_FragColor = vec4(col, a * uOpacity);
  }`;
class Screen {
  constructor(slug, parent = scene) {
    this.mat = new THREE.ShaderMaterial({
      uniforms: {
        map: { value: null }, uImg: { value: new THREE.Vector2(16, 9) }, uHalf: { value: new THREE.Vector2(SW / 2, SH / 2) },
        uOuter: { value: new THREE.Vector2(SW + 2 * MARGIN, SH + 2 * MARGIN) }, uZoom: { value: 1.03 }, uPan: { value: new THREE.Vector2() },
        uOpacity: { value: 1 }, uBright: { value: 1 }, uGlow: { value: 0 }, uGold: { value: GOLD.clone() },
      },
      vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
      fragmentShader: screenFrag, transparent: true, depthWrite: false, side: THREE.DoubleSide,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), this.mat);
    this.mesh.visible = false; parent.add(this.mesh);
    this.slug = slug; this.local = 0; this.setFormat(SW, SH);
  }
  setFormat(w, h) {
    this.mat.uniforms.uHalf.value.set(w / 2, h / 2);
    this.mat.uniforms.uOuter.value.set(w + 2 * MARGIN, h + 2 * MARGIN);
    this.fw = w + 2 * MARGIN; this.fh = h + 2 * MARGIN;
  }
  // положение + масштаб; плоскость единичная, поэтому размер формата учитывается здесь
  place(pos, rot, scale = 1) {
    this.mesh.position.copy(pos); this.mesh.rotation.set(rot.x || 0, rot.y || 0, rot.z || 0);
    this.mesh.scale.set(this.fw * scale, this.fh * scale, 1);
  }
  update(t, { visible = true, opacity = 1, bright = 1, glow = 0, local = t } = {}) {
    this.local = local;
    this.mesh.visible = visible && opacity > 0.001;
    if (!this.mesh.visible) return;
    const e = textures[this.slug], img = e.tex.image;
    this.mat.uniforms.map.value = e.tex;
    this.mat.uniforms.uImg.value.set(img.width || 16, img.height || 9);
    const s = this.slug.length * 1.37 + this.slug.charCodeAt(0) * 0.11;
    const still = !e.count;
    this.mat.uniforms.uZoom.value = still ? 1.1 + 0.05 * Math.sin(t * 0.33 + s) : 1.03 + 0.015 * Math.sin(t * 0.33 + s);
    const pan = still ? 1 : 0.4;
    this.mat.uniforms.uPan.value.set(pan * 0.025 * Math.sin(t * 0.27 + s * 2.0), pan * 0.02 * Math.cos(t * 0.22 + s));
    this.mat.uniforms.uOpacity.value = opacity;
    this.mat.uniforms.uBright.value = bright;
    this.mat.uniforms.uGlow.value = glow;
  }
}
const allScreens = [];
const mkScreen = (slug, parent) => { const s = new Screen(slug, parent); allScreens.push(s); return s; };

// ---------- 1. крючок: призма из трёх работ + разлёт на осколки ----------
const HOOK = ['mclaren', 'promo', 'spider'];
const hookRoot = new THREE.Group(); scene.add(hookRoot);
const prism = new THREE.Group(); hookRoot.add(prism);
const prismFaces = HOOK.map((slug, k) => {
  const holder = new THREE.Group(); holder.rotation.x = -k * Math.PI / 2; prism.add(holder);
  const s = mkScreen(slug, holder); s.place(v3(0, 0, SH / 2), {}, 1); return s;
});
// осколки: сетка плиток одной геометрией, разлёт считает вершинный шейдер
const TX = 24, TY = 14;
const tileGeo = new THREE.BufferGeometry();
{
  const r = rng(5), n = TX * TY;
  const pos = new Float32Array(n * 4 * 3), uv = new Float32Array(n * 4 * 2), ctr = new Float32Array(n * 4 * 2), rnd = new Float32Array(n * 4 * 3), idx = [];
  const tw = SW / TX, th = SH / TY;
  for (let j = 0; j < TY; j++) for (let i = 0; i < TX; i++) {
    const k = j * TX + i, cx = -SW / 2 + (i + 0.5) * tw, cy = -SH / 2 + (j + 0.5) * th, rr = [r(), r(), r()];
    [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([sx, sy], v) => {
      const o = k * 4 + v;
      pos.set([sx * tw / 2, sy * th / 2, 0], o * 3);
      uv.set([(cx + sx * tw / 2) / SW + 0.5, (cy + sy * th / 2) / SH + 0.5], o * 2);
      ctr.set([cx, cy], o * 2); rnd.set(rr, o * 3);
    });
    idx.push(k * 4, k * 4 + 1, k * 4 + 2, k * 4, k * 4 + 2, k * 4 + 3);
  }
  tileGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  tileGeo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  tileGeo.setAttribute('aCenter', new THREE.BufferAttribute(ctr, 2));
  tileGeo.setAttribute('aRnd', new THREE.BufferAttribute(rnd, 3));
  tileGeo.setIndex(idx);
}
const tileMat = new THREE.ShaderMaterial({
  uniforms: { map: { value: null }, uImg: { value: new THREE.Vector2(16, 9) }, uK: { value: 0 }, uGold: { value: CREAM.clone() } },
  vertexShader: `
    attribute vec2 aCenter; attribute vec3 aRnd; uniform float uK; varying vec2 vUv; varying float vF;
    mat3 rot(vec3 a, float g){ a = normalize(a); float s = sin(g), c = cos(g), o = 1. - c;
      return mat3(o*a.x*a.x + c, o*a.x*a.y + a.z*s, o*a.z*a.x - a.y*s,
                  o*a.x*a.y - a.z*s, o*a.y*a.y + c, o*a.y*a.z + a.x*s,
                  o*a.z*a.x + a.y*s, o*a.y*a.z - a.x*s, o*a.z*a.z + c); }
    void main(){
      vUv = uv;
      float k = max(0., uK - length(aCenter) * .06);            // волна от центра
      vec3 dir = normalize(vec3(aCenter * .7, 1.2) + (aRnd - .5) * 1.4);
      float sp = (2.5 + aRnd.x * 5.5) * (1. - exp(-k * 2.4));
      vec3 lp = rot(aRnd - .5 + vec3(.01), k * (3. + aRnd.y * 9.)) * position * (1. - smoothstep(.55, 1.25, k));
      vec3 p = vec3(aCenter, 0.) + lp + dir * sp;
      vF = smoothstep(.15, .9, k);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.);
    }`,
  fragmentShader: `
    uniform sampler2D map; uniform vec2 uImg; uniform vec3 uGold; varying vec2 vUv; varying float vF;
    void main(){
      vec2 cuv = vUv; float ca = 16. / 9., ia = uImg.x / uImg.y;
      if (ia > ca) cuv.x = (cuv.x - .5) * ca / ia + .5; else cuv.y = (cuv.y - .5) * ia / ca + .5;
      cuv = (cuv - .5) / 1.03 + .5;
      vec3 c = texture2D(map, cuv).rgb;
      gl_FragColor = vec4(mix(c, uGold * 1.25, vF), (1. - smoothstep(.55, 1.15, vF * 1.3)));
    }`,
  transparent: true, depthWrite: false, side: THREE.DoubleSide,
});
const tiles = new THREE.Mesh(tileGeo, tileMat); tiles.position.z = SH / 2; tiles.visible = false; hookRoot.add(tiles);

// ---------- 2. объёмный логотип: слои по глубине + блик ----------
const logoTex = await loader.loadAsync('/vendor/logo.png'); logoTex.colorSpace = THREE.SRGBColorSpace;
const LOGO_W = 7.2, LOGO_H = LOGO_W * 725 / 2170, LAYERS = 16;
const logo3d = new THREE.Group(); scene.add(logo3d);
const logoU = { uSheen: { value: -1 }, uOpacity: { value: 0 } };
for (let i = LAYERS - 1; i >= 0; i--) {
  const front = i === 0;
  const m = new THREE.ShaderMaterial({
    uniforms: { map: { value: logoTex }, uSheen: logoU.uSheen, uOpacity: logoU.uOpacity, uDepth: { value: i / LAYERS },
      uGold: { value: GOLD.clone() }, uDark: { value: GOLD_DARK.clone() }, uFront: { value: front ? 1 : 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }`,
    fragmentShader: `
      uniform sampler2D map; uniform float uSheen, uOpacity, uDepth, uFront; uniform vec3 uGold, uDark; varying vec2 vUv;
      void main(){
        vec4 c = texture2D(map, vUv);
        if (c.a < .35) discard;
        vec3 col;
        if (uFront > .5) {
          float s = smoothstep(.14, 0., abs(vUv.x - vUv.y * .35 - uSheen));
          col = c.rgb * .82 + vec3(1., .93, .75) * s * s * .55;
        } else col = mix(uGold * .8, uDark * .25, uDepth);
        gl_FragColor = vec4(col, uOpacity);
      }`,
    transparent: true, depthWrite: true,
  });
  const p = new THREE.Mesh(new THREE.PlaneGeometry(LOGO_W, LOGO_H), m);
  p.position.z = -i * 0.018; logo3d.add(p);
}
logo3d.visible = false;

// ---------- 3. глобус из точек суши + дуги в страны клиентов ----------
const globe = new THREE.Group(); scene.add(globe);
const globeSpin = new THREE.Group(); globe.add(globeSpin);
const G_R = 2.6;
const ll2v = (lat, lon, r = G_R) => {
  const a = THREE.MathUtils.degToRad(lat), b = THREE.MathUtils.degToRad(lon);
  return v3(r * Math.cos(a) * Math.sin(b), r * Math.sin(a), r * Math.cos(a) * Math.cos(b));
};
{
  const im = await loadImage('/vendor/lib/earth_mask.jpg');
  const c = document.createElement('canvas'); c.width = 1024; c.height = 512;
  const g = c.getContext('2d'); g.drawImage(im, 0, 0, 1024, 512);
  const px = g.getImageData(0, 0, 1024, 512).data;
  const pts = [], N = 16000, gold = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2, rr = Math.sqrt(1 - y * y), th = gold * i;
    const lat = Math.asin(y) * 180 / Math.PI, lon = ((Math.atan2(Math.cos(th) * rr, Math.sin(th) * rr) * 180 / Math.PI) + 540) % 360 - 180;
    const u = Math.floor((lon + 180) / 360 * 1023), v = Math.floor((90 - lat) / 180 * 511);
    if (px[(v * 1024 + u) * 4] < 110) pts.push(ll2v(lat, lon));      // на маске океан светлый, суша тёмная
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.ShaderMaterial({
    uniforms: { uOpacity: { value: 0 } },
    vertexShader: `uniform float uOpacity; varying float vA;
      void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.); gl_Position = projectionMatrix * mv;
        vec3 n = normalize(normalMatrix * position); vA = uOpacity * (.25 + .75 * smoothstep(-.1, .6, n.z));
        gl_PointSize = 70. / -mv.z; }`,
    fragmentShader: `varying float vA; void main(){ float d = length(gl_PointCoord - .5); if (d > .5) discard;
      gl_FragColor = vec4(vec3(1., .82, .38) * 1.25 * vA * smoothstep(.5, .1, d), 1.); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  globeSpin.add(new THREE.Points(geo, mat)); globe.userData.pointsMat = mat;
  // параллели и меридианы
  const lines = [];
  for (let lat = -60; lat <= 60; lat += 30) for (let lon = -180; lon < 180; lon += 4) lines.push(ll2v(lat, lon, G_R * 0.995), ll2v(lat, lon + 4, G_R * 0.995));
  for (let lon = -180; lon < 180; lon += 30) for (let lat = -88; lat < 88; lat += 4) lines.push(ll2v(lat, lon, G_R * 0.995), ll2v(lat + 4, lon, G_R * 0.995));
  const lm = new THREE.LineBasicMaterial({ color: GOLD_DARK, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  globeSpin.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(lines), lm)); globe.userData.lineMat = lm;
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: GOLD_DARK.clone().multiplyScalar(1.3), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  halo.scale.setScalar(G_R * 3.4); globe.add(halo); globe.userData.halo = halo;
}
const HOME = [55.75, 37.6];   // Москва
const COUNTRIES = [            // страны из блока «География проектов» на сайте
  ['Казахстан', 51.1, 71.4], ['ОАЭ', 25.2, 55.3], ['Германия', 52.5, 13.4],
  ['Сербия', 44.8, 20.5], ['Испания', 40.4, -3.7], ['США', 40.7, -74.0],
];
const arcs = COUNTRIES.map(([name, lat, lon]) => {
  const a = ll2v(...HOME), b = ll2v(lat, lon);
  const mid = a.clone().add(b).multiplyScalar(0.5);
  const lift = 1 + 0.25 + a.distanceTo(b) * 0.12;
  const ctrl = mid.normalize().multiplyScalar(G_R * lift);
  const curve = new THREE.QuadraticBezierCurve3(a, ctrl, b);
  const P = curve.getPoints(80);
  const geo = new THREE.BufferGeometry().setFromPoints(P);
  geo.setAttribute('aP', new THREE.BufferAttribute(new Float32Array(P.map((_, i) => i / 80)), 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uProg: { value: 0 }, uOpacity: { value: 0 }, uColor: { value: CREAM.clone() } },
    vertexShader: `attribute float aP; varying float vP; void main(){ vP = aP; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
    fragmentShader: `uniform float uProg, uOpacity; uniform vec3 uColor; varying float vP;
      void main(){ if (vP > uProg) discard; gl_FragColor = vec4(uColor * 2.6 * uOpacity * (.35 + .65 * smoothstep(uProg - .35, uProg, vP)), 1.); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const line = new THREE.Line(geo, mat); globeSpin.add(line);
  const dot = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: CREAM.clone().multiplyScalar(3), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  dot.scale.setScalar(0.5); globeSpin.add(dot);
  return { name, curve, mat, dot, end: b };
});
globe.visible = false;

// ---------- 4. спираль работ ----------
const GALLERY = works.carousel_v2 || [
  { slug: 'bubbleli', caption: 'Рекламные ролики товаров' },
  { slug: 'cartoon', caption: 'Создание мультфильмов' },
  { slug: 'yakimal', caption: 'Промо-ролики для компаний' },
  { slug: 'grill', caption: 'Короткие визуальные ролики' },
];
const HELIX_FILL = ['valentine', 'snezhok', 'aikido', 'imed', 'mramori', 'tesla', 'lanterns', 'clothes'];
// featured стоят на позициях 0, 2, 4, 6; между ними — остальные работы
const HELIX_SLUGS = [];
for (let i = 0; i < 12; i++) HELIX_SLUGS.push(i % 2 === 0 && i / 2 < 4 ? GALLERY[i / 2].slug : HELIX_FILL[(i - 1) % HELIX_FILL.length] || HELIX_FILL[0]);
const helix = HELIX_SLUGS.map((s) => mkScreen(s));
const H_R = 7.2, H_STEP = Math.PI / 3, H_RISE = 1.15;

// ---------- 5. «обычный продакшн»: карточки, которые зачёркиваем ----------
const PAIN = ['Съёмочная группа', 'Аренда площадки', 'Актёры', 'Месяцы ожидания'];
const painCards = PAIN.map((txt) => makeCard(cardTexture({ text: txt, w: 1300, h: 260, font: '700 84px Unbounded' }), 0.8));

// ---------- 6. процесс: золотая трасса через 4 этапа ----------
const STEPS = ['Идея и сценарий', 'Кадры', 'Голос и музыка', 'Монтаж и правки'];
const stepPos = [v3(-4.8, -0.7, 0), v3(-1.6, 0.7, -0.6), v3(1.6, -0.7, -0.6), v3(4.8, 0.7, 0)];
const pathCurve = new THREE.CatmullRomCurve3([v3(-9, -2.2, 1), ...stepPos, v3(9, 2, 1)], false, 'catmullrom', 0.5);
const TUBE_SEG = 600;
const tube = new THREE.Mesh(new THREE.TubeGeometry(pathCurve, TUBE_SEG, 0.035, 8, false),
  new THREE.MeshBasicMaterial({ color: GOLD.clone().multiplyScalar(2.6), transparent: true, opacity: 1, depthWrite: false }));
tube.visible = false; scene.add(tube);
const stepT = stepPos.map((p) => {   // параметр кривой у каждого узла
  let best = 0, bd = 1e9;
  for (let i = 0; i <= 1000; i++) { const d = pathCurve.getPoint(i / 1000).distanceTo(p); if (d < bd) { bd = d; best = i / 1000; } }
  return best;
});
const stepNodes = stepPos.map((p) => {
  const g = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: CREAM.clone().multiplyScalar(3), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  g.position.copy(p); g.scale.setScalar(1.4); g.visible = false; scene.add(g); return g;
});
const stepCards = STEPS.map((s, i) => makeCard(cardTexture({ text: s, sub: `этап 0${i + 1}`, w: 1200, h: 300, font: '700 88px Unbounded' }), 1.2));
const head = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: CREAM.clone().multiplyScalar(3.5), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
head.scale.setScalar(1.1); scene.add(head);

// ---------- 7. «всё включено»: чипсы вокруг сферы ----------
const INCL = ['Сценарий', 'Нейроозвучка', 'Музыка', 'Саунд-дизайн', 'Липсинк', 'Субтитры', 'Интеграция бренда'];
const chips = INCL.map((s) => makeCard(cardTexture({ text: s, pill: true, w: 'auto', h: 170, font: '700 76px Manrope' }), 1.12));
const billboards = [];   // повернуть к камере после того, как камера выставлена в этом кадре

// ---------- 8. отзывы с сайта ----------
const REVIEWS = [
  { avatar: '/vendor/site/viktoria-pavlova.png', quote: '…результат оказался даже лучше первоначальной идеи.', name: 'Виктория Павлова' },
  { avatar: '/vendor/site/ilya-lebedev.png', quote: 'Результат получился именно таким, каким мы его представляли.', name: 'Илья Лебедев, Екатеринбург' },
];
const reviewCards = [];
for (const r of REVIEWS) reviewCards.push(makeCard(await reviewTexture(r), 3.5));

// ---------- 9. форматы ----------
const fmtMain = mkScreen('bubbleli');
const fmtTrio = [mkScreen('grill'), mkScreen('mramori'), mkScreen('valentine')];

// ---------- 10. купол экранов ----------
const DOME_SLUGS = works.wall;
const dome = [];
{
  const rows = [[-24, 11], [0, 13], [24, 11]];
  let n = 0;
  for (const [el, cnt] of rows) for (let i = 0; i < cnt; i++) {
    const az = (i - (cnt - 1) / 2) * (Math.PI * 2 / 15) * (el === 0 ? 1 : 1.1);
    dome.push({ s: mkScreen(DOME_SLUGS[n % DOME_SLUGS.length]), el: THREE.MathUtils.degToRad(el), az, i: n });
    n++;
  }
}

// ---------- оверлей ----------
const overlay = document.getElementById('overlay');
const flashEl = document.getElementById('flash');
const blackEl = document.getElementById('black');
function el(html, cls, style = {}) { const e = document.createElement('div'); e.className = cls; e.innerHTML = html; Object.assign(e.style, style); overlay.appendChild(e); return e; }
const px = (v) => `${v}px`;
function show(e, t, tIn, tOut, o = {}) {
  const dIn = o.dIn ?? 0.4, dOut = o.dOut ?? 0.28, dy = o.dy ?? 46;
  const a = eOutExpo(prog(t, tIn, tIn + dIn)), b = eInCubic(prog(t, tOut - dOut, tOut));
  const op = a * (1 - b) * (o.max ?? 1);
  e.style.opacity = op.toFixed(3);
  if (op <= 0) { e.style.visibility = 'hidden'; return 0; }
  e.style.visibility = 'visible';
  const y = (1 - a) * dy - b * (o.dyOut ?? 24);
  const s = lerp(o.s0 ?? 0.94, 1, a) * (1 + (o.punch ?? 0));
  const blur = (1 - a) * (o.blur ?? 14) + b * 10;
  e.style.transform = `${o.pre || ''} translate(${((o.dx ?? 0) * (1 - a)).toFixed(1)}px, ${y.toFixed(2)}px) scale(${s.toFixed(4)})`;
  e.style.filter = blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : '';
  return op;
}
const shadeOn = (e, t, a, b, max = 0.9) => show(e, t, a, b, { dIn: 0.25, dOut: 0.25, dy: 0, s0: 1, blur: 0, max });
const ML = 150;

// крючок
const shBottom = el('', 'shade-bottom');
const hookTxt = ['Ни одной камеры', 'Ни одного актёра', 'Ни одной локации'].map((s) =>
  el(s, 't', { left: px(ML), top: px(830), fontSize: px(112), fontWeight: 800 }));
const hookKicker = el('Работы студии PRO NEURO', 'kicker t', { left: px(ML + 4), top: px(780), textShadow: 'none' });
const reveal1 = el('Это всё —', 't center', { top: px(395), fontSize: px(86), fontWeight: 600 });
const reveal2 = el('нейросети', 't center gold', { top: px(500), fontSize: px(170), fontWeight: 800 });
// логотип и цифры
const logoSub = el('ИИ-видео под ключ — от идеи до финального кадра', 't m center', { top: px(745), fontSize: px(48), fontWeight: 700 });
const shLeft = el('', 'shade-left');
const cKick = el('С 2022 года', 'kicker t', { left: px(ML + 4), top: px(300), textShadow: 'none' });
const cNum = el('0', 't gold', { left: px(ML - 10), top: px(340), fontSize: px(250), fontWeight: 800, lineHeight: 1 });
const cSub = el('реализованных проектов', 't m', { left: px(ML), top: px(640), fontSize: px(58) });
const dKick = el('Сроки', 'kicker t', { left: px(ML + 4), top: px(300), textShadow: 'none' });
const dNum = el('≈ 4 дня', 't gold', { left: px(ML - 8), top: px(340), fontSize: px(200), fontWeight: 800, lineHeight: 1 });
const dSub = el('рабочих — на ролик до минуты', 't m', { left: px(ML), top: px(600), fontSize: px(58) });
const gKick = el('География проектов', 'kicker t', { left: px(ML + 4), top: px(330), textShadow: 'none' });
const gT1 = el('Клиенты', 't', { left: px(ML), top: px(380), fontSize: px(120), fontWeight: 800 });
const gT2 = el('по всему миру', 't gold', { left: px(ML), top: px(530), fontSize: px(96), fontWeight: 800 });
const gTags = COUNTRIES.map(([n], i) => el(n, 'tag', { left: px(ML + (i % 3) * 265), top: px(690 + Math.floor(i / 3) * 80) }));
// галерея
const shTop = el('', 'shade-top');
const galTitle = el('Наши работы', 't', { left: px(ML), top: px(84), fontSize: px(64), fontWeight: 700 });
const galCaps = GALLERY.map((g, i) => [
  el(g.caption, 't center', { top: px(900), fontSize: px(56), fontWeight: 700 }),
  el(`0${i + 1} / 04`, 't m center gold', { top: px(982), fontSize: px(30), fontWeight: 700, letterSpacing: '6px' }),
]);
// боль → решение
const painTitle = el('Обычный продакшн — это:', 't center', { top: px(150), fontSize: px(70), fontWeight: 700 });
const shCenter = el('', 'shade');
const idea1 = el('А нужна', 't center', { top: px(380), fontSize: px(100), fontWeight: 600 });
const idea2 = el('только идея', 't center gold', { top: px(510), fontSize: px(160), fontWeight: 800 });
// процесс
const procTitle = el('Под ключ — 4 этапа', 't', { left: px(ML), top: px(96), fontSize: px(68), fontWeight: 700 });
const procFoot = el('Каждый этап согласуем с вами — правки дешёвые, сроки предсказуемые', 't m center', { top: px(950), fontSize: px(40), fontWeight: 700 });
// всё включено
const inclT1 = el('Всё включено', 't center', { top: px(70), fontSize: px(86), fontWeight: 800 });
const inclT2 = el('без доплат', 't center gold', { top: px(178), fontSize: px(64), fontWeight: 800 });
// отзывы
const revTitle = el('Что говорят клиенты', 't', { left: px(ML), top: px(96), fontSize: px(68), fontWeight: 700 });
// форматы
const fmtTitle = el('Под любую площадку', 't center', { top: px(80), fontSize: px(80), fontWeight: 800 });
const fmtLbl = el('16:9', 't m center gold', { top: px(935), fontSize: px(50), fontWeight: 800, letterSpacing: '4px' });
const FMT_NAMES = ['Горизонтально', 'Вертикально', 'Квадрат'];
const fmtTrioLbl = FMT_NAMES.map((n) => el(n, 't m', { top: px(930), fontSize: px(40), fontWeight: 700, textAlign: 'center', width: px(500) }));
// купол
const domeT1 = el('Ваш ролик', 't center', { top: px(400), fontSize: px(170), fontWeight: 800 });
const domeT2a = el('может быть', 't center', { top: px(330), fontSize: px(140), fontWeight: 800 });
const domeT2b = el('следующим', 't center gold', { top: px(510), fontSize: px(160), fontWeight: 800 });
// финал: оффер, QR, контакты
const offerKick = el('Первый проект', 'kicker t', { left: px(ML + 4), top: px(470), textShadow: 'none' });
const offerNum = el('−10%', 't gold', { left: px(ML - 12), top: px(500), fontSize: px(220), fontWeight: 800, lineHeight: 1 });
const offerCode = el('промокод&nbsp;<span style="color:#C9A227">NEURO10</span>', 'promo-box', { left: px(ML), top: px(760) });
const qrWrap = el('', 'qr', { left: px(1920 - ML - 316), top: px(450) });
{
  const q = qrcode(0, 'M'); q.addData('https://neuroprovideo.ru'); q.make();
  const img = document.createElement('img'); img.src = q.createDataURL(8, 4); qrWrap.appendChild(img);
}
const qrCap = el('Расчёт стоимости<br>за 1 минуту', 't m', { left: px(1920 - ML - 316 - 430), top: px(540), fontSize: px(48), fontWeight: 700, textAlign: 'right', width: px(420), whiteSpace: 'normal', lineHeight: 1.25 });
const contacts = el('<span><b>☎</b> +7 968 589-55-16</span><span><b>TG</b> @proneurovideo</span><span><b>WA</b> +7 968 589-55-16</span><span><b>●</b> neuroprovideo.ru</span>', 'contact', { top: px(960), fontSize: px(38), gap: '52px' });

// ---------- вспышки и аберрация ----------
function flashAt(t) {
  let f = 0;
  for (const [t0, peak, dec] of [[T.shatter, 0.5, 0.35], [T.drop, 0.85, 0.55], [T.drop2, 1.0, 0.7], [T.lock, 0.9, 0.7], [37.5, 0.22, 0.3], [T.dome, 0.4, 0.35]]) {
    if (t >= t0) f = Math.max(f, peak * Math.exp(-(t - t0) / (dec * 0.45)));
    else f = Math.max(f, peak * 0.9 * eInCubic(prog(t, t0 - 0.12, t0)));
  }
  return f;
}
const HITS = [T.hook2, T.hook3, T.shatter, T.drop, T.gallery, T.brk, T.drop2, T.reviews, T.formats, T.dome, T.lock];
function aberr(t) { let a = 0; for (const h of HITS) if (t >= h) a = Math.max(a, Math.exp(-(t - h) * 7)); return a; }

function sphereSpin(t) {
  const build = prog(t, T.build, T.drop2);
  return t * 0.22 + 3.2 * build * build * build + 1.2 * eOutCubic(prog(t, 7.5, 9));
}

// ================= кадр =================
async function renderAt(t) {
  const kick = kickEnv(t);
  pMat.uniforms.uTime.value = t; wMat.uniforms.uTime.value = t; sU.uTime.value = t;
  pMat.uniforms.uPulse.value = kick; sU.uPulse.value = kick;

  let camPos = v3(0, 0, 12), look = v3(0, 0, 0), fov = 50;
  let sphereI = 1, sphereScale = 1, spherePos = v3(0, 0, 0), pOpacity = 1, warpAmt = 0, bloomStr = 0.75 + kick * 0.3;
  for (const s of allScreens) s.mesh.visible = false;
  hookRoot.visible = false; tiles.visible = false; logo3d.visible = false; globe.visible = false; tube.visible = false;
  head.material.opacity = 0;
  for (const c of [...painCards, ...stepCards, ...chips, ...reviewCards]) c.visible = false;
  stepNodes.forEach((n) => { n.visible = false; });

  // ---- 1. крючок 0–7.5
  if (t < T.drop) {
    hookRoot.visible = true;
    const step = t < T.hook2 ? 0 : t < T.hook3 ? 1 : 2;
    const ts = [0, T.hook2, T.hook3][step];
    const flip = step === 0 ? 1 : eOutBack(clamp((t - ts) / 0.5), 1.25);
    prism.rotation.x = (step - 1 + flip) * Math.PI / 2;
    const pull = step === 0 ? 0 : Math.sin(Math.PI * clamp((t - ts) / 0.55)) * 1.0;
    const back = eOutCubic(prog(t, T.hook4, T.hook4 + 0.6));
    camPos = v3(0.25 * Math.sin(t * 0.9), 0.15 * Math.cos(t * 0.7), 3.05 + pull - 0.18 * ((t - ts) / BAR) + back * 6.5 + 1.5 * prog(t, T.shatter, T.drop));
    hookRoot.rotation.set(0.05 * Math.sin(t * 0.8) + back * 0.12, 0.08 * Math.sin(t * 0.6) - back * 0.35, 0);
    fov = 50;
    prismFaces.forEach((s, k) => s.update(t, { visible: t < T.shatter, bright: 1, glow: 0.4 + kick, local: k === 0 ? t : t - [0, T.hook2, T.hook3][k] + 0.25 }));
    if (t >= T.shatter) {
      tiles.visible = true;
      const e = textures[HOOK[2]];
      tileMat.uniforms.map.value = e.tex; tileMat.uniforms.uImg.value.set(e.tex.image.width || 16, e.tex.image.height || 9);
      tileMat.uniforms.uK.value = (t - T.shatter) * 1.25;
    }
    sU.uAsm.value = prog(t, T.shatter + 0.15, 7.35);
    sU.uOpen.value = 0;
    sphereI = t < T.shatter ? 0 : 0.6 + 0.6 * prog(t, 6.6, 7.4);
    pOpacity = 0.35 + 0.65 * prog(t, 0, 2);
    bloomStr = 0.6 + 0.6 * prog(t, 6.2, 7.5);
  } else {
    sU.uAsm.value = 1;
    sU.uOpen.value = t < T.drop2 ? eOutBack(prog(t, 7.5, 8.4), 2.2) : 1;
  }

  // ---- 2. логотип 7.5–9.4
  if (t >= T.drop && t < T.count + 0.4) {
    logo3d.visible = true;
    const k = eOutBack(prog(t, T.drop, T.drop + 0.8), 1.3);
    const out = eInCubic(prog(t, T.count - 0.15, T.count + 0.35));
    logo3d.position.set(-out * 9, 0.45 + out * 0.5, 2.2 - out * 4);
    logo3d.rotation.set(0.08 * Math.sin(t * 1.2), lerp(-1.35, 0, k) + 0.12 * Math.sin(t * 0.9) - out * 0.9, 0);
    logo3d.scale.setScalar(1.4 * (1 + kick * 0.02));
    logoU.uOpacity.value = prog(t, T.drop, T.drop + 0.12) * (1 - out);
    logoU.uSheen.value = lerp(-0.6, 1.6, prog(t, 7.9, 8.9));
    camPos = v3(0, 0, 12); sphereI = 0.18; spherePos = v3(0, 0, -3);
  }
  // ---- 3. цифры и глобус 9.4–15: текст слева, сфера/глобус справа
  if (t >= T.count && t < T.gallery) {
    const g = eOutCubic(prog(t, T.count, T.count + 0.8)), k = prog(t, T.count, T.gallery);
    camPos = v3(lerp(0, -5.6, g) - 0.4 * k, lerp(0.2, -0.2, k), lerp(12, 12.6, k));
    look = v3(lerp(0, -5.5, g) - 0.4 * k, 0, 0);
    sphereScale = lerp(1, 0.84, g);
    const toGlobe = eInOutCubic(prog(t, T.globe - 0.25, T.globe + 0.3));
    sphereI = 1 - toGlobe; sphereScale *= 1 - 0.6 * toGlobe;
    if (toGlobe > 0) {
      globe.visible = true;
      const gs = eOutBack(prog(t, T.globe - 0.25, T.globe + 0.45), 1.2);
      globe.scale.setScalar(Math.max(0.001, gs)); globe.position.set(-1.2, 0, 0);
      globe.rotation.set(THREE.MathUtils.degToRad(38), 0, 0.12);
      globeSpin.rotation.y = -THREE.MathUtils.degToRad(32) + (t - T.globe) * 0.09;
      const go = clamp(toGlobe * 1.3);
      globe.userData.pointsMat.uniforms.uOpacity.value = go;
      globe.userData.lineMat.opacity = 0.32 * go;
      globe.userData.halo.material.opacity = 0.32 * go;
      arcs.forEach((a, i) => {
        const t0 = T.globe + Math.floor(i / 2) * BEAT + (i % 2) * 0.12;
        const p = eOutCubic(prog(t, t0, t0 + 0.4));
        a.mat.uniforms.uProg.value = p; a.mat.uniforms.uOpacity.value = go * (p > 0 ? 1 : 0);
        a.dot.position.copy(a.curve.getPoint(Math.max(0.001, p)));
        a.dot.material.opacity = p > 0 ? go * (0.6 + 0.4 * Math.exp(-(t - t0 - 0.4) * 3)) : 0;
      });
    }
  }
  // ---- 4. спираль работ 15–24.3
  const inGal = t >= T.gallery && t < 24.6;
  if (inGal) {
    const k = prog(t, T.gallery, T.brk);
    camPos = v3(0, lerp(0.9, 0.5, k), 15.6);
    look = v3(0, 0.05, 0);
    if (t >= T.brk) { const d = eInOutCubic(prog(t, T.brk, T.build)); camPos = v3(0, lerp(0.5, 0.3, d), lerp(15.6, 11.5, d)); }
    sphereScale = 0.6; sphereI = 0.55;
    const step = clamp(Math.floor((t - T.gallery) / BAR), 0, 3), inBar = t - T.gallery - step * BAR;
    const mv = step === 0 ? eOutCubic(clamp((t - T.gallery) / 0.9)) : eOutBack(clamp(inBar / 0.45), 1.25);
    const pos = lerp(step === 0 ? -2.5 : (step - 1) * 2, step * 2, mv);
    helix.forEach((s, i) => {
      const rel = i - pos;
      const a = rel * H_STEP;
      const target = step * 2;
      const feat = i === target ? eOutCubic(clamp(inBar / 0.4)) : (i === target - 2 && inBar < 0.35 ? 1 - eOutCubic(inBar / 0.35) : 0);
      const r = H_R + feat * 3.2;
      let p = v3(Math.sin(a) * r, -rel * H_RISE + 0.35 + feat * 0.25, Math.cos(a) * r);
      let rotY = a, op = 1;
      const inK = eOutCubic(clamp((t - T.gallery - Math.abs(rel) * 0.04) / 0.8));
      p.y -= (1 - inK) * 12; rotY += (1 - inK) * 1.5; op = inK;
      if (t >= T.brk) {
        const o = eInCubic(prog(t, T.brk + (i % 4) * 0.04, 23.35));
        p = p.add(v3((Math.sin(a) + (i % 2 ? 0.6 : -0.6)) * 14 * o, (i % 2 ? 1 : -1) * 6 * o, -12 * o)); rotY += o * (i % 2 ? 2 : -2); op *= 1 - o;
      }
      const front = Math.cos(a) > 0 ? 1 : 0.5;
      s.setFormat(SW, SH);
      s.place(p, { y: rotY }, 0.95 + feat * 0.36 + kick * 0.012 * feat);
      const local = i % 2 === 0 && i / 2 < 4 ? t - (T.gallery + (i / 2) * BAR) : t - T.gallery;
      s.update(t, { opacity: op * (Math.abs(rel) < 4.5 ? 1 : 0), bright: (0.5 + 0.5 * feat) * front, glow: feat * (0.8 + kick), local });
    });
  }
  // ---- 5. боль 22.5–26.25 и решение 26.25–30
  if (t >= T.brk && t < T.drop2) {
    if (t < T.build) { const d = eInOutCubic(prog(t, T.brk, T.build)); camPos = v3(0, lerp(0.5, 0.3, d), lerp(15.6, 11.5, d)); look = v3(0, 0, 0); }
    else {
      const w = prog(t, T.warp, T.drop2);
      camPos = v3(0, 0.3, lerp(11.5, 8.0, eInOutCubic(prog(t, T.build, T.warp))) - 3.4 * eInCubic(w));
      warpAmt = eInCubic(w); fov = 50 + 26 * eInCubic(w);
      bloomStr = 0.75 + 0.8 * w + kick * 0.3;
    }
    sphereScale = lerp(0.6, 1, eInOutCubic(prog(t, T.brk, T.build)));
    sphereI = t < T.build ? 0.35 : 0.8 + 0.8 * prog(t, T.build, T.drop2);
    const POS = [v3(-2.15, 0.5, -5.5), v3(2.15, 0.5, -5.5), v3(-2.15, -0.62, -5.5), v3(2.15, -0.62, -5.5)];   // относительно камеры
    painCards.forEach((c, i) => {
      const tIn = T.brk + 0.15 + i * BEAT * 0.8, tS = T.strike + i * BEAT;
      const a = eOutBack(prog(t, tIn, tIn + 0.5), 1.4);
      const fall = eInCubic(prog(t, tS + 0.22, tS + 0.7));
      if (a <= 0 || fall >= 1) return;
      c.visible = true;
      c.position.copy(POS[i]).add(camPos).add(v3(0, -fall * 3.2 + 0.04 * Math.sin(t * 1.3 + i), -(1 - a) * 6 - fall * 1.5));
      c.rotation.set(-0.08 + fall * 1.4, (i % 2 ? -0.12 : 0.12) * (1 - fall), (i % 2 ? -1 : 1) * fall * 0.4);
      c.scale.setScalar(Math.max(0.01, a));
      c.material.uniforms.uOpacity.value = clamp(a) * (1 - fall);
      c.material.uniforms.uStrike.value = eOutCubic(prog(t, tS, tS + 0.22));
      c.material.uniforms.uDim.value = 1 - 0.45 * prog(t, tS, tS + 0.3);
    });
  }
  // ---- 6. процесс 30–33.75
  if (t >= T.drop2 && t < T.chips + 0.3) {
    const k = prog(t, T.drop2, T.chips);
    camPos = v3(lerp(-0.9, 0.9, k), 0.4, 10.2); look = v3(lerp(-0.7, 0.7, k), 0, 0);
    sphereI = 0; pOpacity = 0.7;
    const out = eInCubic(prog(t, T.chips - 0.1, T.chips + 0.3));
    tube.visible = true;
    const tp = lerp(0.04, 1, eInOutCubic(prog(t, T.drop2, T.chips - 0.2)));
    const cnt = Math.floor(tp * TUBE_SEG) * 8 * 6;
    tube.geometry.setDrawRange(0, cnt);
    tube.material.opacity = 1 - out;
    head.position.copy(pathCurve.getPoint(tp)); head.material.opacity = (1 - out) * (0.8 + 0.4 * kick);
    stepPos.forEach((p, i) => {
      const reached = tp >= stepT[i];
      const tr = reached ? t - (T.drop2 + (stepT[i] - 0.04) / 0.96 * 0) : 0;
      const on = reached ? 1 : 0;
      const n = stepNodes[i]; n.visible = on > 0; n.material.opacity = on * (1 - out) * (0.8 + 0.5 * kick); n.scale.setScalar(1.2 + kick * 0.4);
      const c = stepCards[i];
      if (!reached) return;
      // момент достижения узла: где tp пересёк stepT[i]
      const tHit = T.drop2 + (T.chips - 0.2 - T.drop2) * invInOut((stepT[i] - 0.04) / 0.96);
      const a = eOutBack(prog(t, tHit, tHit + 0.45), 1.5);
      c.visible = true; void tr;
      c.position.copy(p).add(v3(0, (i % 2 ? 1 : -1) * 1.15, 0.3));
      c.rotation.set(0, (look.x - p.x) * 0.04, 0);
      c.scale.setScalar(Math.max(0.01, a));
      c.material.uniforms.uOpacity.value = clamp(a) * (1 - out);
    });
  }
  // ---- 7. всё включено 33.75–37.5
  if (t >= T.chips && t < T.reviews + 0.3) {
    camPos = v3(0, 0.6, 9.6); look = v3(0, 0.75, 0);
    const out = eInCubic(prog(t, T.reviews - 0.1, T.reviews + 0.3));
    sphereScale = 0.66 * (1 + 0.06 * eOutBack(prog(t, T.chips, T.chips + 0.5))); sphereI = 1 - out; spherePos = v3(0, -0.2, 0);
    chips.forEach((c, i) => {
      const tIn = T.chips + 0.2 + i * 0.36;
      const a = eOutBack(prog(t, tIn, tIn + 0.45), 1.6);
      if (a <= 0) return;
      const ang = i * (Math.PI * 2 / INCL.length) + (t - T.chips) * 0.55;
      const r = lerp(0.5, 4.1, eOutCubic(prog(t, tIn, tIn + 0.5)));
      const p = v3(Math.cos(ang) * r * 1.3, Math.sin(ang) * r * 0.4 - 0.45, Math.sin(ang) * r * 0.6);
      c.visible = true; c.position.copy(p); billboards.push(c);
      c.scale.setScalar(Math.max(0.01, a) * (1 + kick * 0.03));
      const depth = clamp((p.z + 3) / 6);
      c.material.uniforms.uOpacity.value = clamp(a) * (1 - out) * (0.55 + 0.45 * depth);
      c.material.uniforms.uDim.value = 0.6 + 0.4 * depth;
    });
  }
  // ---- 8. отзывы 37.5–41.25
  if (t >= T.reviews && t < T.formats + 0.3) {
    camPos = v3(0, 0, 8.3); look = v3(0, 0.1, 0);
    sphereI = 0.25; spherePos = v3(5.5, 2.2, -10); pOpacity = 0.7;
    const out = eInCubic(prog(t, T.formats - 0.1, T.formats + 0.3));
    reviewCards.forEach((c, i) => {
      const tIn = T.reviews + i * BAR + 0.05;
      const a = eOutExpo(prog(t, tIn, tIn + 0.6));
      if (a <= 0) return;
      const pushed = i === 0 ? eInOutCubic(prog(t, bar(22), bar(22) + 0.5)) : 0;
      c.visible = true;
      c.position.set(lerp(11, i === 0 ? -0.3 : 0.4, a) - pushed * 1.0, (i === 0 ? -0.1 : -0.72) + pushed * 1.8, -pushed * 2.6 + 0.05 * Math.sin(t * 1.1 + i));
      c.rotation.set(0.04, lerp(-0.9, i === 0 ? 0.1 : -0.1, a) + pushed * 0.15, i === 0 ? 0.02 : -0.02);
      c.material.uniforms.uOpacity.value = clamp(a) * (1 - out);
      c.material.uniforms.uDim.value = 1 - 0.45 * pushed;
    });
  }
  // ---- 9. форматы 41.25–45
  if (t >= T.formats && t < T.dome + 0.2) {
    camPos = v3(0, 0, 9.5); look = v3(0, 0, 0); sphereI = 0;
    const m1 = eInOutCubic(prog(t, T.formats + 2 * BEAT - 0.2, T.formats + 2 * BEAT + 0.25));
    const m2 = eInOutCubic(prog(t, T.formats + 4 * BEAT - 0.2, T.formats + 4 * BEAT + 0.25));
    const trio = eOutBack(prog(t, T.formats + 6 * BEAT, T.formats + 6 * BEAT + 0.5), 1.2);
    const out = eInCubic(prog(t, T.dome - 0.25, T.dome + 0.1));
    if (trio < 0.02) {
      let w = SW, h = SH;
      if (m2 > 0) { w = lerp(1.25, 2.3, m2); h = lerp(2.22, 2.3, m2); } else { w = lerp(SW, 1.25, m1); h = lerp(SH, 2.22, m1); }
      const spin = (m1 + m2) * Math.PI * 2;
      fmtMain.setFormat(w, h);
      fmtMain.place(v3(0, -0.1, 0), { y: spin + 0.12 * Math.sin(t * 0.9) }, 2.0 * Math.max(0.01, eOutBack(prog(t, T.formats, T.formats + 0.5), 1.3)));
      fmtMain.update(t, { glow: 0.6 + kick, local: t - T.formats });
    } else {
      const F = [[SW, SH, -4.9], [1.25, 2.22, 0], [2.0, 2.0, 4.6]];
      fmtTrio.forEach((s, i) => {
        const [w, h, x] = F[i];
        s.setFormat(w, h);
        s.place(v3(lerp(0, x, trio), 0.05, -out * 8), { y: (x > 0 ? -0.18 : x < -1 ? 0.18 : 0) * trio }, 1.5);
        s.update(t, { opacity: clamp(trio * 2) * (1 - out), glow: 0.5 + kick, local: t - T.formats });
      });
    }
  }
  // ---- 10. купол 45–54
  const inDome = t >= T.dome && t < 54.6;
  if (inDome) {
    const k = prog(t, T.dome, T.end);
    const yaw = lerp(-0.42, 0.42, eInOutCubic(k)), pitch = 0.08 * Math.sin(k * Math.PI * 2);
    camPos = v3(0, 0, 0); look = v3(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
    fov = 62; sphereI = 0; pOpacity = 0.5;
    const beatIdx = Math.floor((t - T.dome) / BEAT), sinceBeat = (t - T.dome) - beatIdx * BEAT, hk = Math.exp(-sinceBeat * 3.2);
    // подсветка: случайный экран рядом с направлением взгляда
    let hi = -1;
    if (t < T.end) {
      const r = rng(2000 + beatIdx), cand = [];
      dome.forEach((d, j) => { const dir = v3(Math.sin(d.az) * Math.cos(d.el), Math.sin(d.el), -Math.cos(d.az) * Math.cos(d.el)); if (dir.dot(look) > 0.86) cand.push(j); });
      hi = cand.length ? cand[Math.floor(r() * cand.length)] : -1;
    }
    dome.forEach((d, j) => {
      const inK = eOutExpo(clamp((t - T.dome - ((j * 7) % 15) * 0.025) / 0.6));
      const outK = eInCubic(prog(t, T.end + ((j * 4) % 15) * 0.03, 54.4));
      const R = lerp(40, 10, inK) + outK * 30 - (j === hi ? 0.8 * hk : 0) - kick * 0.15;
      const p = v3(Math.sin(d.az) * Math.cos(d.el) * R, Math.sin(d.el) * R, -Math.cos(d.az) * Math.cos(d.el) * R);
      d.s.setFormat(SW, SH);
      d.s.mesh.position.copy(p); d.s.mesh.lookAt(0, 0, 0);
      d.s.mesh.scale.set(d.s.fw * 1.25, d.s.fh * 1.25, 1);
      d.s.update(t, { opacity: inK * (1 - outK), bright: j === hi ? 1 : 0.36 + 0.16 * kick, glow: j === hi ? 0.6 + 1.2 * hk : 0.05 + 0.25 * kick, local: t - T.dome + j * 0.37 });
    });
  }
  // ---- 11. финал 52.5–60
  if (t >= T.end) {
    const k = eInOutCubic(prog(t, T.end, 54.2));
    const lookDome = v3(Math.sin(0.42), 0, -Math.cos(0.42));
    camPos = v3(0, 0, 0).lerp(v3(0, 0, 12.5 + 1.2 * prog(t, 54.2, 60)), k);
    look = lookDome.clone().lerp(v3(0, 0, 0), k);
    fov = lerp(62, 50, k);
    logo3d.visible = true;
    const a = eOutBack(prog(t, 53.2, 54.2), 1.3), lock = eOutCubic(prog(t, T.lock, T.lock + 0.6));
    logo3d.position.set(0, 2.55, 0); logo3d.rotation.set(0.06 * Math.sin(t * 1.1) * (1 - lock), lerp(1.4, 0, a) + 0.1 * Math.sin(t * 0.8) * (1 - lock), 0);
    logo3d.scale.setScalar(1.12 * (1 + 0.06 * (t >= T.lock ? 1 - lock : 0)));
    logoU.uOpacity.value = prog(t, 53.2, 53.4);
    logoU.uSheen.value = t < T.lock ? lerp(-0.6, 1.6, prog(t, 53.6, 54.6)) : lerp(-0.6, 1.6, prog(t, T.lock, T.lock + 0.8));
    spherePos = v3(0, 2.6, -7); sphereScale = 1.25; sphereI = 0.22 * prog(t, 53.4, 54.4); pOpacity = 0.55;
  }

  // ---- общая сцена
  camera.position.copy(camPos); camera.fov = fov; camera.updateProjectionMatrix(); camera.lookAt(look);
  camera.updateMatrixWorld();
  for (const b of billboards.splice(0)) b.quaternion.copy(camera.quaternion);
  sphere.position.copy(spherePos); sphere.scale.setScalar(Math.max(0.001, sphereScale));
  sphere.rotation.set(0.35 + 0.15 * Math.sin(t * 0.21), sphereSpin(t), 0.1 * Math.sin(t * 0.17));
  sU.uI.value = sphereI * (1 + kick * 0.35); sphere.visible = sphereI > 0.001;
  inner.material.opacity = 0.7 * clamp(sU.uAsm.value * 1.4 - 0.4) * Math.min(1, sphereI);
  inner.rotation.set(-t * 0.5, -t * 0.7, 0);
  core.material.opacity = (0.22 + 0.3 * kick) * clamp(sU.uAsm.value * 1.5 - 0.5) * Math.min(1, sphereI);
  pMat.uniforms.uOpacity.value = pOpacity * (1 - 0.6 * warpAmt);
  wMat.uniforms.uOpacity.value = warpAmt; wMat.uniforms.uStretch.value = 26 * warpAmt; warp.visible = warpAmt > 0.001;
  RING_T.forEach((t0, i) => {
    const r = rings[i], k = prog(t, t0, t0 + 1.1);
    r.visible = t >= t0 && k < 1 && t0 !== T.dome;
    if (!r.visible) return;
    r.position.copy(sphere.position); r.scale.setScalar(lerp(2.0, 16, eOutCubic(k)) * Math.max(0.5, sphereScale));
    r.material.opacity = (1 - k) * (1 - k); r.lookAt(camera.position);
  });

  // ---- кадры видео
  const vis = new Map(allScreens.filter((s) => s.mesh.visible).map((s) => [s.slug, s.local]));
  if (t >= T.shatter && t < T.drop) vis.set(HOOK[2], t - T.hook3 + 0.25);
  await Promise.all([...vis].map(([slug, local]) => videoFrame(slug, local)));
  for (const s of allScreens) if (s.mesh.visible) s.mat.uniforms.map.value = textures[s.slug].tex;
  if (tiles.visible) tileMat.uniforms.map.value = textures[HOOK[2]].tex;

  // ---- оверлей
  shadeOn(shBottom, t, 0, T.hook4 + 0.3, 0.95);
  show(hookKicker, t, 0.1, T.hook4 + 0.2, { dIn: 0.4, dy: 20 });
  hookTxt.forEach((e, i) => { const a = [0.12, T.hook2 + 0.08, T.hook3 + 0.08][i]; show(e, t, a, i === 2 ? T.hook4 + 0.2 : a + BAR - 0.12, { dIn: 0.3, dOut: 0.14, dx: -50, dy: 0, punch: kick * 0.02 }); });
  show(reveal1, t, T.shatter + 0.1, 7.38, { dIn: 0.5, dy: 30 });
  show(reveal2, t, T.shatter + 0.35, 7.38, { dIn: 0.5, dy: 30, s0: 1.2 });
  show(logoSub, t, 7.85, T.count - 0.05, { dIn: 0.45 });

  if (t >= T.count && t < T.gallery) shadeOn(shLeft, t, T.count, T.gallery - 0.05, 0.9); else if (t < T.gallery) shLeft.style.opacity = 0;
  show(cKick, t, T.count, T.days, { dIn: 0.3, dy: 20 });
  const cn = show(cNum, t, T.count, T.days, { dIn: 0.25, punch: kick * 0.03, s0: 0.85 });
  if (cn > 0) cNum.textContent = `${Math.round(800 * eOutCubic(prog(t, T.count, T.count + 1.2)))}+`;
  show(cSub, t, T.count + 0.2, T.days, { dIn: 0.4 });
  show(dKick, t, T.days, T.globe, { dIn: 0.3, dy: 20 });
  show(dNum, t, T.days, T.globe, { dIn: 0.3, punch: kick * 0.03, s0: 0.8 });
  show(dSub, t, T.days + 0.22, T.globe, { dIn: 0.4 });
  show(gKick, t, T.globe, T.gallery - 0.02, { dIn: 0.3, dy: 20 });
  show(gT1, t, T.globe + 0.05, T.gallery - 0.02, { dIn: 0.35 });
  show(gT2, t, T.globe + 0.2, T.gallery - 0.02, { dIn: 0.35 });
  arcs.forEach((a, i) => {
    const e = gTags[i];
    const t0 = T.globe + Math.floor(i / 2) * BEAT + (i % 2) * 0.12 + 0.3;
    if (!globe.visible || t < t0 || t > T.gallery) { e.style.opacity = 0; return; }
    show(e, t, t0, T.gallery - 0.02, { dIn: 0.25, dy: 14, s0: 0.7, blur: 6 });
  });

  if (inGal && t < T.brk) shadeOn(shTop, t, T.gallery, T.brk - 0.05, 0.8); else if (t < 45) shTop.style.opacity = 0;
  show(galTitle, t, T.gallery, T.brk - 0.08, { dIn: 0.5 });
  galCaps.forEach(([c, n], i) => {
    const a = T.gallery + i * BAR, b = i === 3 ? T.brk - 0.08 : a + BAR;
    show(c, t, a + 0.2, b, { dIn: 0.4, dOut: 0.16 }); show(n, t, a + 0.3, b, { dIn: 0.4, dOut: 0.16 });
  });
  show(painTitle, t, T.brk + 0.05, T.build - 0.05, { dIn: 0.5 });
  if (t >= T.build - 0.1 && t < T.drop2) shadeOn(shCenter, t, T.build, 28.6, 0.85); else if (t < 45) shCenter.style.opacity = 0;
  show(idea1, t, T.build + 0.05, 28.6, { dIn: 0.6, dy: 30 });
  show(idea2, t, T.build + 0.5, 28.6, { dIn: 0.6, dy: 30, punch: kick * 0.03, s0: 1.15 });
  show(procTitle, t, T.drop2 + 0.1, T.chips - 0.05, { dIn: 0.45 });
  show(procFoot, t, T.drop2 + 1.4, T.chips - 0.05, { dIn: 0.5 });
  show(inclT1, t, T.chips + 0.02, T.reviews - 0.05, { dIn: 0.4, s0: 1.1 });
  show(inclT2, t, T.chips + 0.2, T.reviews - 0.05, { dIn: 0.4, s0: 1.1, punch: kick * 0.03 });
  show(revTitle, t, T.reviews + 0.05, T.formats - 0.05, { dIn: 0.45 });
  show(fmtTitle, t, T.formats + 0.05, T.dome - 0.05, { dIn: 0.45 });
  const fmtStage = t < T.formats + 2 * BEAT ? 0 : t < T.formats + 4 * BEAT ? 1 : 2;
  fmtLbl.textContent = ['16:9', '9:16', '1:1'][fmtStage];
  show(fmtLbl, t, T.formats + 0.15, T.formats + 6 * BEAT, { dIn: 0.3, dOut: 0.15, punch: kick * 0.05 });
  fmtTrioLbl.forEach((e, i) => {
    const x = [-4.9, 0, 4.6][i];
    const sp = v3(x, 0, 0).project(camera);
    e.style.left = px((sp.x * 0.5 + 0.5) * W - 250);
    show(e, t, T.formats + 6 * BEAT + 0.2 + i * 0.08, T.dome - 0.05, { dIn: 0.35, dy: 20 });
  });
  if (t >= T.dome && t < T.end) shadeOn(shCenter, t, T.dome, T.end - 0.05, 0.9);
  show(domeT1, t, T.dome, 48.75, { dIn: 0.35, punch: kick * 0.03, s0: 1.15 });
  show(domeT2a, t, 48.75, T.end - 0.05, { dIn: 0.35, s0: 1.15 });
  show(domeT2b, t, 48.75 + BEAT, T.end - 0.05, { dIn: 0.35, s0: 1.15, punch: kick * 0.03 });

  show(offerKick, t, 54.0, 61, { dIn: 0.4, dy: 20 });
  show(offerNum, t, 54.1, 61, { dIn: 0.4, s0: 0.7, punch: t >= T.lock ? 0.08 * Math.exp(-(t - T.lock) * 4) + kick * 0.02 : 0 });
  show(offerCode, t, 54.5, 61, { dIn: 0.4 });
  show(qrWrap, t, 54.7, 61, { dIn: 0.45, s0: 0.8 });
  show(qrCap, t, 54.9, 61, { dIn: 0.45 });
  show(contacts, t, 55.3, 61, { dIn: 0.5, dy: 30 });

  flashEl.style.opacity = flashAt(t).toFixed(3);
  blackEl.style.opacity = eInOutCubic(prog(t, 59.4, 60)).toFixed(3);
  bloom.strength = bloomStr;
  finalPass.uniforms.uSeed.value = Math.round(t * FPS) % 997;
  finalPass.uniforms.uAb.value = 0.012 * aberr(t);
  composer.render();
}
// обратная к eInOutCubic (для момента прохода узла трассы)
function invInOut(y) { let lo = 0, hi = 1; for (let i = 0; i < 30; i++) { const m = (lo + hi) / 2; if (eInOutCubic(m) < y) lo = m; else hi = m; } return (lo + hi) / 2; }

window.renderAt = renderAt;
await document.fonts.ready;
await Promise.all([...document.images].map((im) => im.decode().catch(() => {})));
window.sceneReady = true;
