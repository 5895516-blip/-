// Промо PRO NEURO, 60 с. Всё состояние кадра считается из времени t в renderAt(t):
// без requestAnimationFrame и без накоплений, поэтому кадры можно рендерить в любом порядке.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const W = 1920, H = 1080, FPS = 30;
const BEAT = 0.46875, BAR = 1.875;
const bar = (n) => (n - 1) * BAR;           // начало такта n (с 1)

// ---------- утилиты ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const prog = (t, a, b) => clamp((t - a) / (b - a));
const sstep = (x) => x * x * (3 - 2 * x);
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

// ---------- рендерер ----------
const canvas = document.getElementById('gl');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.setClearColor(0x070605, 1);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 400);

const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 });
const composer = new EffectComposer(renderer, rt);
composer.setPixelRatio(1);
composer.setSize(W, H);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.8, 0.5, 1.0);
composer.addPass(bloom);
composer.addPass(new OutputPass());
const finalPass = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, uSeed: { value: 0 }, uVig: { value: 1 }, uGrain: { value: 0.045 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform float uSeed, uVig, uGrain; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + uSeed*7.13) * 43758.5453); }
    void main(){
      vec3 c = texture2D(tDiffuse, vUv).rgb;
      vec2 q = vUv - .5; q.x *= 1.25;
      float v = smoothstep(.95, .25, length(q));
      c *= mix(1., v, .72 * uVig);
      c += (h(vUv * vec2(1920., 1080.)) - .5) * uGrain;
      gl_FragColor = vec4(c, 1.);
    }`,
});
composer.addPass(finalPass);

// ---------- мягкая текстура-точка ----------
function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,240,200,.55)');
  gr.addColorStop(0.6, 'rgba(201,162,39,.12)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}
const GLOW = glowTexture();

// ---------- фон: дымка за сферой ----------
const haze = new THREE.Mesh(new THREE.PlaneGeometry(60, 34), new THREE.MeshBasicMaterial({
  map: GLOW, color: GOLD_DARK, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false,
}));
haze.position.z = -25; scene.add(haze);

// ---------- частицы ----------
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
  uniforms: { uTime: { value: 0 }, uPulse: { value: 0 }, uOpacity: { value: 1 }, uColor: { value: GOLD.clone() }, uI: { value: 1.15 } },
  vertexShader: `
    attribute float aSize; attribute float aPhase; uniform float uTime, uPulse, uOpacity; varying float vA;
    void main(){
      vec3 p = position;
      p.y += sin(uTime * .35 + aPhase * 6.283) * .35; p.x += cos(uTime * .27 + aPhase * 12.) * .3;
      vec4 mv = modelViewMatrix * vec4(p, 1.);
      gl_Position = projectionMatrix * mv;
      gl_PointSize = min(40., aSize * 210. * (1. + .6 * uPulse) / -mv.z);
      float tw = .55 + .45 * sin(uTime * 2.1 + aPhase * 40.);
      vA = tw * uOpacity * smoothstep(.6, 4., -mv.z) * smoothstep(140., 60., -mv.z);
    }`,
  fragmentShader: `
    uniform vec3 uColor; uniform float uI; varying float vA;
    void main(){ float d = length(gl_PointCoord - .5); float a = smoothstep(.5, .0, d); a *= a;
      gl_FragColor = vec4(uColor * uI * a * vA, 1.); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});
const particles = new THREE.Points(pGeo, pMat); scene.add(particles);

// линии варпа: подмножество тех же частиц, хвост тянется по z
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
      gl_Position = projectionMatrix * mv; vT = aTail;
      vA = smoothstep(.5, 3., -mv.z);
    }`,
  fragmentShader: `uniform vec3 uColor; uniform float uOpacity; varying float vA; varying float vT;
    void main(){ gl_FragColor = vec4(uColor * 2.2 * uOpacity * vA * (1. - vT * .85), 1.); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});
const warp = new THREE.LineSegments(wGeo, wMat); scene.add(warp);

// ---------- нейросфера ----------
const sphere = new THREE.Group(); scene.add(sphere);
const R_SPHERE = 2.3;
const sphereNodes = [], sphereEdges = [];
{
  const g = new THREE.IcosahedronGeometry(R_SPHERE, 2);
  const p = g.attributes.position.array, map = new Map(), idx = [];
  for (let i = 0; i < p.length / 3; i++) {
    const key = [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]].map((v) => v.toFixed(4)).join(',');
    if (!map.has(key)) { map.set(key, sphereNodes.length); sphereNodes.push(new THREE.Vector3(p[i * 3], p[i * 3 + 1], p[i * 3 + 2])); }
    idx.push(map.get(key));
  }
  const seen = new Set();
  for (let f = 0; f < idx.length; f += 3) {
    for (const [a, b] of [[idx[f], idx[f + 1]], [idx[f + 1], idx[f + 2]], [idx[f + 2], idx[f]]]) {
      const k = a < b ? `${a}_${b}` : `${b}_${a}`;
      if (!seen.has(k)) { seen.add(k); sphereEdges.push([a, b]); }
    }
  }
}
const nodeStart = [], nodeDelay = [];
{
  const r = rng(11);
  for (const n of sphereNodes) {
    const dir = n.clone().normalize();
    nodeStart.push(dir.multiplyScalar(9 + r() * 16).add(new THREE.Vector3((r() - 0.5) * 10, (r() - 0.5) * 10, (r() - 0.5) * 20)));
    nodeDelay.push(r() * 0.62);
  }
}
const sphereUniforms = { uAsm: { value: 1 }, uOpen: { value: 0 }, uPulse: { value: 0 }, uI: { value: 1 }, uTime: { value: 0 } };
const SPHERE_VERT_COMMON = `
  attribute vec3 aStart; attribute float aDelay;
  uniform float uAsm, uOpen, uPulse, uTime;
  float local(float d){ float x = clamp((uAsm - d) / .38, 0., 1.); return 1. - pow(1. - x, 3.); }
  vec3 place(vec3 target, vec3 start, float d){
    float k = local(d);
    float n = sin(dot(target, vec3(3.1, 1.7, 2.3)) + uTime * 1.3) * .05;
    vec3 t = target * (1. + uOpen * .32 + uPulse * .06 + n);
    return mix(start, t, k);
  }`;
const nodeGeo = new THREE.BufferGeometry();
{
  const pos = new Float32Array(sphereNodes.length * 3), st = new Float32Array(sphereNodes.length * 3), dl = new Float32Array(sphereNodes.length);
  sphereNodes.forEach((n, i) => { pos.set([n.x, n.y, n.z], i * 3); st.set([nodeStart[i].x, nodeStart[i].y, nodeStart[i].z], i * 3); dl[i] = nodeDelay[i]; });
  nodeGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  nodeGeo.setAttribute('aStart', new THREE.BufferAttribute(st, 3));
  nodeGeo.setAttribute('aDelay', new THREE.BufferAttribute(dl, 1));
}
const nodeMat = new THREE.ShaderMaterial({
  uniforms: { ...sphereUniforms, uColor: { value: CREAM.clone() } },
  vertexShader: SPHERE_VERT_COMMON + `
    varying float vA;
    void main(){
      vec3 p = place(position, aStart, aDelay);
      vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv;
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
  const E = sphereEdges.length, pos = new Float32Array(E * 6), st = new Float32Array(E * 6), dl = new Float32Array(E * 2), od = new Float32Array(E * 2);
  sphereEdges.forEach(([a, b], i) => {
    for (const [k, v, o] of [[0, a, b], [1, b, a]]) {
      const n = sphereNodes[v], s = nodeStart[v];
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
  uniforms: { ...sphereUniforms, uColor: { value: GOLD.clone() } },
  vertexShader: SPHERE_VERT_COMMON + `
    attribute float aOther; varying float vA;
    void main(){
      vec3 p = place(position, aStart, aDelay);
      vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv;
      vA = min(local(aDelay), local(aOther));
      vA *= vA;
    }`,
  fragmentShader: `uniform vec3 uColor; uniform float uI; varying float vA;
    void main(){ gl_FragColor = vec4(uColor * uI * vA * 1.35, 1.); }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});
sphere.add(new THREE.LineSegments(edgeGeo, edgeMat));
// share uniforms objects so one write updates both materials
for (const k of Object.keys(sphereUniforms)) { nodeMat.uniforms[k] = sphereUniforms[k]; edgeMat.uniforms[k] = sphereUniforms[k]; }

const inner = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.15, 0)),
  new THREE.LineBasicMaterial({ color: CREAM.clone().multiplyScalar(1.6), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }),
);
sphere.add(inner);
const core = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: GOLD.clone().multiplyScalar(2.2), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
core.scale.setScalar(5.5); sphere.add(core);

// ударные кольца на вспышках
const rings = [7.5, 30.0, 45.0, 56.25].map(() => {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.96, 1, 128), new THREE.MeshBasicMaterial({
    color: CREAM.clone().multiplyScalar(2.5), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
  }));
  scene.add(m); return m;
});
const RING_T = [7.5, 30.0, 45.0, 56.25];

// ---------- экраны с работами ----------
const loader = new THREE.TextureLoader();
const textures = {};
async function loadTex(url) {
  const tex = await loader.loadAsync(url);
  tex.colorSpace = THREE.SRGBColorSpace; tex.minFilter = THREE.LinearFilter; tex.generateMipmaps = false;
  return tex;
}
for (const w of works.works) {
  const m = manifest[w.slug]; if (!m) continue;
  textures[w.slug] = { tex: await loadTex('/' + m.still), frames: m.frames, count: m.count || 0, cur: -1 };
}
// кадр видео-фрагмента по времени (если нарезка есть); иначе остаётся превью
const bitmapCache = new Map();
async function videoFrame(slug, local) {
  const e = textures[slug]; if (!e || !e.count) return;
  const i = Math.max(0, Math.floor(local * FPS + 1e-6)) % e.count;
  if (i === e.cur) return;
  const url = `/${e.frames}/${String(i + 1).padStart(4, '0')}.jpg`;
  let bmp = bitmapCache.get(url);
  if (!bmp) {
    const blob = await (await fetch(url)).blob();
    bmp = await createImageBitmap(blob, { imageOrientation: 'flipY' });
    bitmapCache.set(url, bmp);
    if (bitmapCache.size > 400) { const [k, v] = bitmapCache.entries().next().value; v.close(); bitmapCache.delete(k); }
  }
  if (e.tex.isCanvasLike !== true) { e.tex.dispose(); e.tex = new THREE.Texture(); e.tex.colorSpace = THREE.SRGBColorSpace; e.tex.minFilter = THREE.LinearFilter; e.tex.generateMipmaps = false; e.tex.flipY = false; e.tex.isCanvasLike = true; }
  e.tex.image = bmp; e.tex.needsUpdate = true; e.cur = i;
}

const SW = 3.2, SH = 1.8, MARGIN = 0.22;
const screenVert = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`;
const screenFrag = `
  uniform sampler2D map; uniform vec2 uImg; uniform float uZoom, uOpacity, uBright, uGlow; uniform vec2 uPan; uniform vec3 uGold;
  varying vec2 vUv;
  const vec2 HALF = vec2(${(SW / 2).toFixed(3)}, ${(SH / 2).toFixed(3)});
  const vec2 OUTER = vec2(${(SW + 2 * MARGIN).toFixed(3)}, ${(SH + 2 * MARGIN).toFixed(3)});
  float sdBox(vec2 p, vec2 b, float r){ vec2 q = abs(p) - b + r; return length(max(q, 0.)) + min(max(q.x, q.y), 0.) - r; }
  void main(){
    vec2 q = (vUv - .5) * OUTER;
    float d = sdBox(q, HALF, .07);
    vec3 col = vec3(0.); float a = 0.;
    if (gl_FrontFacing) {
      vec2 cuv = q / (2. * HALF) + .5;
      float ca = HALF.x / HALF.y, ia = uImg.x / uImg.y;
      if (ia > ca) cuv.x = (cuv.x - .5) * ca / ia + .5; else cuv.y = (cuv.y - .5) * ia / ca + .5;
      cuv = (cuv - .5) / uZoom + .5 + uPan;
      vec3 img = texture2D(map, cuv).rgb * uBright;
      float inside = smoothstep(.006, -.006, d);
      col = img * inside; a = inside;
    } else {
      float inside = smoothstep(.006, -.006, d);
      col = mix(vec3(.02), uGold * .25, smoothstep(1.6, 0., length(q))) * inside; a = inside;
    }
    float line = exp(-abs(d) * 70.) * (.55 + uGlow);
    float halo = exp(-max(d, 0.) * 9.) * step(0., d) * .45 * uGlow;
    col += uGold * (line * 2.4 + halo);
    a = max(a, clamp(line + halo, 0., 1.));
    gl_FragColor = vec4(col, a * uOpacity);
  }`;
class Screen {
  constructor(slug) {
    this.mat = new THREE.ShaderMaterial({
      uniforms: {
        map: { value: null }, uImg: { value: new THREE.Vector2(16, 9) }, uZoom: { value: 1.08 }, uPan: { value: new THREE.Vector2() },
        uOpacity: { value: 1 }, uBright: { value: 1 }, uGlow: { value: 0 }, uGold: { value: GOLD.clone() },
      },
      vertexShader: screenVert, fragmentShader: screenFrag, transparent: true, depthWrite: false, side: THREE.DoubleSide,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(SW + 2 * MARGIN, SH + 2 * MARGIN), this.mat);
    this.mesh.visible = false; scene.add(this.mesh);
    this.setSlug(slug);
  }
  setSlug(slug) { this.slug = slug; }
  update(t, { visible = true, opacity = 1, bright = 1, glow = 0, local = t } = {}) {
    this.local = local;   // время внутри фрагмента работы
    this.mesh.visible = visible && opacity > 0.001;
    if (!this.mesh.visible) return;
    const e = textures[this.slug];
    const img = e.tex.image;
    this.mat.uniforms.map.value = e.tex;
    this.mat.uniforms.uImg.value.set(img.width || 16, img.height || 9);
    const s = this.slug.length * 1.37 + this.slug.charCodeAt(0) * 0.11;   // стабильное «зерно» для движения
    const still = !e.count;   // превью оживляем наездом, видео почти не трогаем
    this.mat.uniforms.uZoom.value = still ? 1.1 + 0.05 * Math.sin(t * 0.33 + s) : 1.03 + 0.015 * Math.sin(t * 0.33 + s);
    const pan = still ? 1 : 0.4;
    this.mat.uniforms.uPan.value.set(pan * 0.025 * Math.sin(t * 0.27 + s * 2.0), pan * 0.02 * Math.cos(t * 0.22 + s));
    this.mat.uniforms.uOpacity.value = opacity;
    this.mat.uniforms.uBright.value = bright;
    this.mat.uniforms.uGlow.value = glow;
  }
}
const carouselSlugs = [...works.carousel.map((c) => c.slug), ...works.carousel_fill];
// в кольце 8 экранов: избранные стоят через один, чтобы каждый такт выезжал следующий
const RING_ORDER = [0, 4, 1, 5, 2, 6, 3, 7].map((i) => carouselSlugs[i]);
const carousel = RING_ORDER.map((s) => new Screen(s));
const reasonA = new Screen(works.reasons[0]);
const reasonB = new Screen(works.reasons[1]);
const wall = works.wall.map((s) => new Screen(s));

// ---------- текстовый оверлей ----------
const overlay = document.getElementById('overlay');
const flashEl = document.getElementById('flash');
const blackEl = document.getElementById('black');
function el(html, cls, style = {}, tag = 'div') {
  const e = document.createElement(tag); e.className = cls; e.innerHTML = html; Object.assign(e.style, style); overlay.appendChild(e); return e;
}
const px = (v) => `${v}px`;
// show: появление (подъём + расфокус) и уход; всё — функция от t
function show(e, t, tIn, tOut, o = {}) {
  const dIn = o.dIn ?? 0.4, dOut = o.dOut ?? 0.28, dy = o.dy ?? 46, sc = o.scale ?? 1;
  const a = eOutExpo(prog(t, tIn, tIn + dIn)), b = eInCubic(prog(t, tOut - dOut, tOut));
  const op = a * (1 - b) * (o.max ?? 1);
  e.style.opacity = op.toFixed(3);
  if (op <= 0) { e.style.visibility = 'hidden'; return 0; }
  e.style.visibility = 'visible';
  const y = (1 - a) * dy - b * (o.dyOut ?? 24);
  const s = sc * lerp(o.s0 ?? 0.94, 1, a) * (1 + (o.punch ?? 0));
  const blur = (1 - a) * (o.blur ?? 14) + b * 10;
  e.style.transform = `translate(${(o.dx ?? 0) * (1 - a)}px, ${y.toFixed(2)}px) scale(${s.toFixed(4)})`;
  e.style.filter = blur > 0.05 ? `blur(${blur.toFixed(2)}px)` + (o.keepFilter ? ' ' + o.keepFilter : '') : (o.keepFilter || '');
  return op;
}

const TX = 150;   // левое поле текста
// 1. интро
const i1 = el('Представьте видео,', 't center', { top: px(800), fontSize: px(70), fontWeight: 600 });
const i2 = el('которому не нужна съёмочная площадка', 't center', { top: px(895), fontSize: px(54), fontWeight: 500, color: '#F9E9B4' });
// 2. факты
const shadeL = el('', 'shade-left');
const logoS2 = el('<img src="/vendor/logo.png" style="width:820px;display:block">', 'logo', { left: px(TX - 40), top: px(330) });
const s2sub = el('ИИ-видеопродакшн полного цикла', 't m', { left: px(TX), top: px(640), fontSize: px(50), fontWeight: 600 });
const rule2 = el('', 'rule', { left: px(TX), top: px(615), width: px(640) });
const f800 = el('800+', 't gold', { left: px(TX - 10), top: px(300), fontSize: px(260), fontWeight: 800, lineHeight: 1 });
const f800s = el('реализованных проектов', 't m', { left: px(TX), top: px(610), fontSize: px(56) });
const f22 = el('С 2022', 't gold', { left: px(TX - 6), top: px(330), fontSize: px(210), fontWeight: 800, lineHeight: 1 });
const f22s = el('года создаём видео с&nbsp;нейросетями', 't m', { left: px(TX), top: px(610), fontSize: px(56) });
const noWords = ['БЕЗ СЪЁМОК', 'БЕЗ АКТЁРОВ', 'БЕЗ ЛОКАЦИЙ', 'БЕЗ ГРАНИЦ'].map((w, i) =>
  el(w, 't' + (i === 3 ? ' gold' : ''), { left: px(TX), top: px(250 + i * 150), fontSize: px(108), fontWeight: 800 }));
// 3. работы
const worksTitle = el('Наши работы', 't', { left: px(TX), top: px(96), fontSize: px(66), fontWeight: 700 });
const worksRule = el('', 'rule', { left: px(TX), top: px(196), width: px(420) });
const capEls = works.carousel.map((c, i) => [
  el(c.caption, 't center', { top: px(890), fontSize: px(54), fontWeight: 600 }),
  el(`0${i + 1} / 04`, 't m center gold', { top: px(970), fontSize: px(30), fontWeight: 700, letterSpacing: '6px' }),
]);
// 4. почему
const shadeC = el('', 'shade');
const why1 = el('Почему выбирают', 't center', { top: px(400), fontSize: px(84), fontWeight: 600 });
const why2 = el('PRO NEURO?', 't center gold', { top: px(515), fontSize: px(150), fontWeight: 800 });
// 5. причины
const REASONS = [
  ['01', 'Быстро', 'Ролик за дни, а&nbsp;не&nbsp;месяцы'],
  ['02', 'Выгодно', 'Без съёмочной группы,<br>аренды и&nbsp;актёров'],
  ['03', 'Без ограничений', 'Любая локация,<br>эпоха и&nbsp;герой'],
  ['04', 'Под ключ', 'Сценарий, генерация, озвучка,<br>графика и&nbsp;монтаж'],
].map(([n, title, sub]) => ({
  n: el(n, 't outline', { left: px(TX - 6), top: px(250), fontSize: px(190), fontWeight: 800, lineHeight: 1 }),
  title: el(title, 't', { left: px(TX), top: px(500), fontSize: px(title.length > 10 ? 66 : 96), fontWeight: 800 }),
  rule: el('', 'rule', { left: px(TX), top: px(640), width: px(520) }),
  sub: el(sub, 't m', { left: px(TX), top: px(670), fontSize: px(52), fontWeight: 600, lineHeight: 1.3, whiteSpace: 'normal', width: px(800) }),
}));
// 6. стена
const wall1 = el('Ваш ролик', 't center', { top: px(400), fontSize: px(170), fontWeight: 800 });
const wall2a = el('может быть', 't center', { top: px(330), fontSize: px(140), fontWeight: 800 });
const wall2b = el('следующим', 't center gold', { top: px(510), fontSize: px(160), fontWeight: 800 });
// 7. финал
const logoF = el('<img src="/vendor/logo.png" style="width:900px;display:block">', 'logo', { left: px((W - 900) / 2), top: px(470) });
const finSub = el('ИИ-видеопродакшн полного цикла', 't m center', { top: px(745), fontSize: px(44), fontWeight: 600 });
const finBtn = el('Обсудить проект', 'btn', { left: px(W / 2), top: px(818) });
const finContacts = el('neuroprovideo.ru&nbsp;&nbsp;·&nbsp;&nbsp;+7 968 589-55-16', 't m center', { top: px(960), fontSize: px(40), fontWeight: 700, letterSpacing: '1px' });

// ---------- камера и сцена по разделам ----------
const v3 = (x, y, z) => new THREE.Vector3(x, y, z);
const tmpLook = new THREE.Vector3();

function sphereSpin(t) {
  // равномерное вращение + ускорение на билде (интеграл скорости задан аналитически)
  const build = prog(t, bar(15), 30.0);
  return t * 0.22 + 3.2 * build * build * build + 1.2 * eOutCubic(prog(t, 7.5, 9));
}

function flashAt(t) {
  let f = 0;
  for (const [t0, peak, dec] of [[7.5, 0.85, 0.55], [30.0, 1.0, 0.7], [56.25, 0.9, 0.7], [37.5, 0.22, 0.3], [45.0, 0.35, 0.35]]) {
    if (t >= t0) f = Math.max(f, peak * Math.exp(-(t - t0) / (dec * 0.45)));
    else f = Math.max(f, peak * 0.9 * eInCubic(prog(t, t0 - 0.12, t0)));
  }
  return f;
}

function setScreen(s, t, pos, rotY, rotX, scale, o) {
  s.mesh.position.copy(pos); s.mesh.rotation.set(rotX, rotY, 0); s.mesh.scale.setScalar(scale);
  s.update(t, o);
}

// ---------- основной расчёт кадра ----------
async function renderAt(t) {
  const kick = kickEnv(t);
  const time = t;
  pMat.uniforms.uTime.value = time; wMat.uniforms.uTime.value = time; sphereUniforms.uTime.value = time;
  pMat.uniforms.uPulse.value = kick;
  sphereUniforms.uPulse.value = kick;

  let camPos = v3(0, 0, 12), look = v3(0, 0, 0), fov = 50;
  let sphereI = 1, sphereScale = 1, spherePos = v3(0, 0, 0);
  let pOpacity = 1, warpAmt = 0, bloomStr = 0.75 + kick * 0.3;

  // --- 1. интро 0–7.5
  if (t < 7.5) {
    const k = eInOutCubic(prog(t, 0, 7.5));
    camPos = v3(Math.sin(t * 0.4) * 1.2, 0.6 * Math.cos(t * 0.3), lerp(78, 11.5, k));
    sphereUniforms.uAsm.value = prog(t, 1.2, 7.1);
    sphereUniforms.uOpen.value = 0;
    sphereI = 0.6 + 0.6 * prog(t, 4, 7.4);
    pOpacity = 0.4 + 0.6 * prog(t, 0, 2);
    fov = lerp(58, 50, k);
    bloomStr = 0.7 + 0.5 * prog(t, 5.5, 7.5);
  } else {
    sphereUniforms.uAsm.value = 1;
    sphereUniforms.uOpen.value = t < 30 ? eOutBack(prog(t, 7.5, 8.4), 2.2) : 1;
  }
  // --- 2. факты 7.5–15: текст слева, сфера справа
  if (t >= 7.5 && t < 15) {
    const k = prog(t, 7.5, 15);
    const g = eOutCubic(prog(t, 7.5, 8.6));
    camPos = v3(lerp(0, -5.6, g) - 0.4 * k, lerp(0.2, -0.2, k), lerp(11.5, 12.6, k));
    look = v3(lerp(0, -5.5, g) - 0.4 * k, 0, 0);
    sphereScale = lerp(1, 0.84, g);
    sphereI = 1.0;
  }
  // --- 3. карусель 15–22.5
  const RING_R = 6.2, N_RING = 8;
  let ringOn = false;
  if (t >= 15 && t < 24.5) {
    ringOn = true;
    const k = prog(t, 15, 22.5);
    camPos = v3(0, lerp(2.0, 1.4, k), lerp(14.5, 13.2, k));
    look = v3(0, 0.25, 0);
    // смена от 3-го к 4-му разделу: облёт к сфере
    if (t >= 22.5) {
      const d = eInOutCubic(prog(t, 22.5, 28.125));
      camPos = v3(0, lerp(1.4, 0.3, d), lerp(13.2, 8.0, d));
    }
    sphereScale = 0.62; spherePos = v3(0, 0.9, 0);
  }
  if (t >= 15 && t < 22.5) sphereI = 0.7;
  // --- 4. брейк и билд 22.5–30
  if (t >= 22.5 && t < 30) {
    const d = eInOutCubic(prog(t, 22.5, 28.125));
    const w = prog(t, bar(16), 30.0);
    camPos = v3(0, lerp(1.4, 0.3, d), lerp(13.2, 8.0, d) - 3.4 * eInCubic(w));
    look = v3(0, 0, 0);
    sphereScale = lerp(0.62, 1, eInOutCubic(prog(t, 22.5, 25)));
    warpAmt = eInCubic(w);
    fov = 50 + 26 * eInCubic(w);
    sphereI = 1 + 0.6 * prog(t, 26.25, 30);
    bloomStr = 0.75 + 0.8 * w + kick * 0.3;
  }
  // --- 5. четыре причины 30–45
  const inReasons = t >= 30 && t < 45.3;
  if (inReasons) {
    const k = prog(t, 30, 45);
    camPos = v3(lerp(0.4, -0.2, k), lerp(0.25, -0.15, k), lerp(11.6, 10.6, k));
    look = v3(0, 0, 0);
    spherePos = v3(5.2, 1.0, -11);
    sphereScale = 1.1; sphereI = 0;
    pOpacity = 0.75;
  }
  // --- 6. видеостена 45–52.5
  const inWall = t >= 45 && t < 55;
  if (t >= 45 && t < 52.5) {
    const k = eInOutCubic(prog(t, 45, 52.5));
    look = v3(lerp(-2.6, 2.6, k), lerp(0.9, -0.9, k), 0);
    camPos = look.clone().add(v3(1.4, 0.7, 8.6 - 0.8 * Math.sin(k * Math.PI)));
    sphereI = 0; pOpacity = 0.5;
  }
  // --- 7. финал 52.5–60
  if (t >= 52.5) {
    const k = eInOutCubic(prog(t, 52.5, 55));
    const from = v3(2.6 + 1.4, -0.9 + 0.7, 8.6);
    camPos = from.clone().lerp(v3(0, -0.4, 13.5 + 1.5 * prog(t, 55, 60)), k);
    look = v3(2.6, -0.9, 0).lerp(v3(0, -0.4, 0), k);
    spherePos = v3(0, 2.55, 0);
    sphereScale = 0.72 + 0.04 * eOutBack(prog(t, 56.25, 57.2));
    sphereI = 0.2 + 0.9 * eOutCubic(prog(t, 52.8, 55));
    pOpacity = 0.4 + 0.5 * prog(t, 52.5, 54);
  }

  camera.position.copy(camPos); camera.fov = fov; camera.updateProjectionMatrix(); camera.lookAt(look);
  sphere.position.copy(spherePos);
  sphere.scale.setScalar(sphereScale);
  sphere.rotation.set(0.35 + 0.15 * Math.sin(t * 0.21), sphereSpin(t), 0.1 * Math.sin(t * 0.17));
  sphereUniforms.uI.value = sphereI * (1 + kick * 0.35);
  sphere.visible = sphereI > 0.001;
  inner.material.opacity = 0.7 * clamp(sphereUniforms.uAsm.value * 1.4 - 0.4) * Math.min(1, sphereI);
  inner.rotation.set(-t * 0.5, -t * 0.7, 0);
  core.material.opacity = (0.22 + 0.3 * kick) * clamp(sphereUniforms.uAsm.value * 1.5 - 0.5) * Math.min(1, sphereI);
  haze.material.opacity = 0.08 + 0.06 * kick;
  haze.position.set(spherePos.x, spherePos.y, -25);

  pMat.uniforms.uOpacity.value = pOpacity * (1 - 0.6 * warpAmt);
  wMat.uniforms.uOpacity.value = warpAmt;
  wMat.uniforms.uStretch.value = 26 * warpAmt;
  warp.visible = warpAmt > 0.001;

  RING_T.forEach((t0, i) => {
    const r = rings[i], k = prog(t, t0, t0 + 1.1);
    r.visible = t >= t0 && k < 1;
    if (!r.visible) return;
    r.position.copy(sphere.position);
    r.scale.setScalar(lerp(2.0, 16, eOutCubic(k)) * sphereScale);
    r.material.opacity = (1 - k) * (1 - k);
    r.lookAt(camera.position);
  });

  // --- экраны карусели
  for (let i = 0; i < N_RING; i++) {
    const s = carousel[i];
    if (!ringOn) { s.update(t, { visible: false }); continue; }
    const step = clamp(Math.floor((t - 15) / BAR), 0, 3);
    const inBar = t - 15 - step * BAR;
    const prev = step === 0 ? -1.2 : (step - 1) * 2;
    const target = step * 2;
    const mv = step === 0 ? eOutCubic(clamp((t - 15) / 0.9)) : eOutBack(clamp(inBar / 0.42), 1.3);
    const pos = lerp(prev, target, mv);
    const a = ((i - pos) / N_RING) * Math.PI * 2;
    const featured = i === target ? eOutCubic(clamp(inBar / 0.4)) : (i === target - 2 && inBar < 0.4 ? 1 - eOutCubic(inBar / 0.4) : 0);
    const r = RING_R + featured * 2.4;
    let p = v3(Math.sin(a) * r, 1.1 + featured * 0.15, Math.cos(a) * r);
    let op = 1, rotY = a, scale = 0.95 + featured * 0.2 + kick * 0.015 * featured;
    // влёт
    const inK = eOutCubic(clamp((t - 15 - i * 0.03) / 0.7));
    p.multiplyScalar(lerp(3.2, 1, inK)); op = inK;
    // разлёт на брейке
    if (t >= 22.5) {
      const o = eInCubic(prog(t, 22.5 + (i % 4) * 0.06, 24.3));
      p = p.add(v3(Math.sin(a) * 18 * o, (i % 2 ? 1 : -1) * 6 * o, Math.cos(a) * 10 * o));
      rotY += o * (i % 2 ? 2 : -2); op *= 1 - o;
    }
    const back = Math.cos(a) < 0 ? 0.55 : 1;
    const local = i % 2 === 0 ? t - (15 + (i / 2) * BAR) : t - 15;   // избранная работа стартует, когда выезжает
    setScreen(s, t, p, rotY, 0, scale, { opacity: op, bright: (0.55 + 0.45 * featured) * back, glow: featured * (0.8 + kick), local });
  }

  // --- экран причин: смены на 33.75 (переворот), 37.5 (свайп), 41.25 (переворот)
  reasonA.update(t, { visible: false }); reasonB.update(t, { visible: false });
  let reasonIdx = -1;
  if (inReasons) {
    const R_BASE = v3(3.3, 0.05, 2.3), ROT_Y = -0.4, ROT_X = 0.04, SC = 1.6;
    reasonIdx = clamp(Math.floor((t - 30) / (2 * BAR)), 0, 3);
    const T = [30, 33.75, 37.5, 41.25];
    const drift = Math.sin(t * 0.6) * 0.05;
    const pulse = 1 + kick * 0.012;
    // влёт на 30.0
    const enter = eOutExpo(prog(t, 30, 30.7));
    const exit = eInCubic(prog(t, 44.6, 45.15));
    const base = R_BASE.clone().add(v3((1 - enter) * 9 + exit * 10, drift, -(1 - enter) * 4));
    const glow = 0.5 + kick * 0.8;
    const sw = (i) => (i % 2 === 1 ? 'swipe' : 'flip');
    // при переходе на i-ю причину (i>=1)
    const i = reasonIdx, ti = T[i], dt = t - ti;
    const nextI = i < 3 ? i + 1 : -1, tn = nextI > 0 ? T[nextI] : 1e9;
    const toNext = t - tn;   // < 0 до смены
    // текущий экран A — работа reasons[i]
    reasonA.setSlug(works.reasons[i]);
    let rotY = ROT_Y, posA = base.clone(), opA = 1 - exit, localA = dt;
    // хвост входа текущего (если пришёл переворотом или свайпом)
    if (i > 0 && dt < 0.3) {
      if (sw(i) === 'flip') rotY = ROT_Y + Math.PI * (1 - eOutCubic(clamp((dt + 0.2) / 0.5)));   // второй полуоборот
      else posA.x += 9 * (1 - eOutExpo(clamp(dt / 0.42)));
    }
    // начало ухода к следующему (за 0.2 с до доли)
    let showB = false;
    if (nextI > 0 && toNext > -0.2) {
      const kind = sw(nextI);
      if (kind === 'flip') {
        rotY = ROT_Y + Math.PI * (1 - eOutCubic(clamp((toNext + 0.2) / 0.5)));
        // после 90° показываем уже следующую работу
        if (toNext >= 0) { reasonA.setSlug(works.reasons[nextI]); localA = toNext; }
      } else {
        posA.x -= 11 * eInCubic(clamp((toNext + 0.2) / 0.3)); opA *= 1 - clamp((toNext + 0.05) / 0.2);
        showB = toNext >= 0;
        if (showB) {
          reasonB.setSlug(works.reasons[nextI]);
          const pb = base.clone(); pb.x += 9 * (1 - eOutExpo(clamp(toNext / 0.42)));
          setScreen(reasonB, t, pb, ROT_Y, ROT_X, SC * pulse, { opacity: 1, bright: 1, glow, local: toNext });
        }
      }
    }
    setScreen(reasonA, t, posA, rotY, ROT_X, SC * pulse, { opacity: opA, bright: 1, glow, local: localA });
  }

  // --- видеостена
  const COLS = 5, ROWS = 3, GAP = 0.4;
  let hi = -1;
  if (inWall) {
    const beatIdx = Math.floor((t - 45) / BEAT);
    // экран для подсветки: ближайшие к точке взгляда, порядок фиксирован зерном
    if (t < 52.5) {
      const r = rng(1000 + beatIdx);
      const cand = [];
      for (let j = 0; j < COLS * ROWS; j++) {
        const cx = (j % COLS - 2) * (SW + GAP), cy = (1 - Math.floor(j / COLS)) * (SH + GAP);
        const d = Math.hypot(cx - look.x, cy - look.y);
        if (d < 5.2) cand.push(j);
      }
      hi = cand[Math.floor(r() * cand.length)];
    }
    const sinceBeat = (t - 45) - beatIdx * BEAT;
    const hk = Math.exp(-sinceBeat * 3.2);
    for (let j = 0; j < COLS * ROWS; j++) {
      const s = wall[j];
      const cx = (j % COLS - 2) * (SW + GAP), cy = (1 - Math.floor(j / COLS)) * (SH + GAP);
      const inK = eOutExpo(clamp((t - 45 - ((j * 7) % 15) * 0.025) / 0.55));
      const outK = eInCubic(prog(t, 52.5 + ((j * 4) % 15) * 0.03, 54.4));
      const isHi = j === hi;
      const z = (1 - inK) * -22 + (isHi ? 0.55 * hk : 0) - outK * 40 + kick * 0.08;
      const pos = v3(cx * (1 + 0.012 * kick) + outK * cx * 0.6, cy * (1 + 0.012 * kick) + outK * cy * 0.6, z);
      const op = inK * (1 - outK);
      setScreen(s, t, pos, 0, 0, 1, {
        opacity: op, bright: isHi ? 1.0 : 0.34 + 0.16 * kick, glow: isHi ? 0.6 + 1.2 * hk : 0.05 + 0.25 * kick, local: t - 45,
      });
    }
  } else wall.forEach((s) => s.update(t, { visible: false }));

  // --- кадры видео для видимых экранов
  const vis = new Map([...carousel, reasonA, reasonB, ...wall].filter((s) => s.mesh.visible).map((s) => [s.slug, s.local]));
  await Promise.all([...vis].map(([slug, local]) => videoFrame(slug, local)));
  // после замены текстуры обновить ссылки
  for (const s of [...carousel, reasonA, reasonB, ...wall]) if (s.mesh.visible) s.mat.uniforms.map.value = textures[s.slug].tex;

  // ---------- оверлей ----------
  show(i1, t, 1.0, 7.35, { dIn: 0.7 });
  show(i2, t, 3.75, 7.35, { dIn: 0.7 });

  if (t < 22.5) show(shadeL, t, 7.5, 15.0, { dIn: 0.3, dy: 0, s0: 1, blur: 0, dOut: 0.2, max: 0.9 });
  else show(shadeL, t, 30.0, 45.0, { dIn: 0.2, dy: 0, s0: 1, blur: 0, max: 0.85 });
  show(logoS2, t, 7.5, bar(6), { dIn: 0.45, punch: kick * 0.02, keepFilter: 'drop-shadow(0 0 28px rgba(201,162,39,.45))' });
  show(s2sub, t, 7.5 + 0.23, bar(6), { dIn: 0.45 });
  rule2.style.opacity = (prog(t, 7.6, 7.9) * (1 - prog(t, bar(6) - 0.2, bar(6)))).toFixed(3);
  rule2.style.transform = `scaleX(${eOutExpo(prog(t, 7.6, 8.3)).toFixed(3)})`;
  show(f800, t, bar(6), bar(7), { dIn: 0.35, punch: kick * 0.03, s0: 0.8 });
  show(f800s, t, bar(6) + BEAT * 0.5, bar(7), { dIn: 0.4 });
  show(f22, t, bar(7), bar(8), { dIn: 0.35, punch: kick * 0.03, s0: 0.8 });
  show(f22s, t, bar(7) + BEAT * 0.5, bar(8), { dIn: 0.4 });
  noWords.forEach((e, i) => {
    const tIn = bar(8) + i * BEAT, act = t >= tIn && (i === 3 || t < tIn + BEAT);
    const op = show(e, t, tIn, 15.0, { dIn: 0.22, dy: 30, s0: 1.18, blur: 10, punch: act ? kick * 0.04 : 0 });
    if (op > 0 && !act) e.style.opacity = (op * 0.38).toFixed(3);
  });

  show(worksTitle, t, 15.0, 22.4, { dIn: 0.5 });
  worksRule.style.opacity = (prog(t, 15.2, 15.5) * (1 - prog(t, 22.2, 22.4))).toFixed(3);
  worksRule.style.transform = `scaleX(${eOutExpo(prog(t, 15.2, 16)).toFixed(3)})`;
  capEls.forEach(([c, n], i) => {
    const a = 15 + i * BAR, b = a + BAR;
    show(c, t, a + 0.18, i === 3 ? 22.4 : b, { dIn: 0.4, dOut: 0.18 });
    show(n, t, a + 0.28, i === 3 ? 22.4 : b, { dIn: 0.4, dOut: 0.18 });
  });

  if (t < 45) show(shadeC, t, 23.0, 28.6, { dIn: 0.8, dy: 0, s0: 1, blur: 0, max: 0.85 });
  show(why1, t, 23.2, 28.6, { dIn: 0.9, dy: 30 });
  show(why2, t, 24.1, 28.6, { dIn: 0.9, dy: 30, punch: t > 26.25 ? kick * 0.03 : 0 });

  REASONS.forEach((r, i) => {
    const a = 30 + i * 2 * BAR, b = i === 3 ? 44.85 : a + 2 * BAR;
    show(r.n, t, a, b, { dIn: 0.35, dOut: 0.16, dx: -60, dy: 0, punch: kick * 0.02 });
    show(r.title, t, a + 0.08, b, { dIn: 0.38, dOut: 0.16, dx: -60, dy: 0 });
    show(r.sub, t, a + 0.2, b, { dIn: 0.42, dOut: 0.16, dy: 26 });
    r.rule.style.opacity = (prog(t, a + 0.1, a + 0.3) * (1 - prog(t, b - 0.16, b))).toFixed(3);
    r.rule.style.transform = `scaleX(${eOutExpo(prog(t, a + 0.1, a + 0.8)).toFixed(3)})`;
  });

  if (t >= 45) show(shadeC, t, 45.0, 52.45, { dIn: 0.3, dy: 0, s0: 1, blur: 0, max: 0.9 });
  show(wall1, t, 45.0, 48.75, { dIn: 0.35, punch: kick * 0.03, s0: 1.15 });
  show(wall2a, t, 48.75, 52.45, { dIn: 0.35, s0: 1.15 });
  show(wall2b, t, 48.75 + BEAT, 52.45, { dIn: 0.35, s0: 1.15, punch: kick * 0.03 });

  // финал: логотип проявляется шторкой, на 56.25 вспышка и фиксация
  const lk = eInOutCubic(prog(t, 53.4, 55.4));
  const lock = prog(t, 56.25, 56.9);
  const op = show(logoF, t, 53.4, 61, { dIn: 0.6, dy: 0, blur: 8, s0: 1.0, punch: t < 56.25 ? 0.05 * (1 - lk) : 0.06 * (1 - eOutCubic(lock)), keepFilter: `drop-shadow(0 0 ${28 + 40 * (1 - lock) * (t >= 56.25 ? 1 : 0)}px rgba(201,162,39,.6))` });
  logoF.style.clipPath = `inset(0 ${((1 - lk) * 100).toFixed(2)}% 0 0)`;
  show(finSub, t, 55.0, 61, { dIn: 0.5 });
  const bo = show(finBtn, t, 55.5, 61, { dIn: 0.5, punch: kick * 0.025 });
  finBtn.style.transform = `translateX(-50%) ` + finBtn.style.transform;
  show(finContacts, t, 56.25, 61, { dIn: 0.5 });
  void op; void bo;

  flashEl.style.opacity = flashAt(t).toFixed(3);
  blackEl.style.opacity = eInOutCubic(prog(t, 59.4, 60)).toFixed(3);

  bloom.strength = bloomStr;
  finalPass.uniforms.uSeed.value = Math.round(t * FPS) % 997;
  composer.render();
}

window.renderAt = renderAt;
await document.fonts.load('800 100px Unbounded');
await document.fonts.load('600 100px Manrope');
await document.fonts.ready;
await Promise.all([...document.images].map((im) => im.decode().catch(() => {})));
window.sceneReady = true;
