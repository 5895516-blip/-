// Рендер промо: node render.mjs keys 1 4.2 9.5 ...   — пробные кадры в out/keys/
//               node render.mjs full [workers]        — полный ролик в out/
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(ROOT, 'out');
const FPS = 30, DURATION = 60, W = 1920, H = 1080;

async function loadPlaywright() {
  for (const p of ['playwright', '/opt/node-tools/node_modules/playwright/index.mjs']) {
    try { return await import(p); } catch { /* следующий вариант */ }
  }
  throw new Error('playwright не найден');
}

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.wav': 'audio/wav' };
function serve() {
  const srv = http.createServer((req, res) => {
    let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p === '/') p = '/src/index.html';
    const f = path.join(ROOT, path.normalize(p));
    if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise((ok) => srv.listen(0, '127.0.0.1', () => ok(srv)));
}

async function openPage(browser, port) {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  let fatal = null;
  page.on('pageerror', (e) => { console.error('pageerror:', e.message); fatal = e; });
  page.on('console', (m) => { if (m.type() === 'error') console.error('console:', m.text()); });
  await page.goto(`http://127.0.0.1:${port}/src/index.html`);
  for (let i = 0; i < 600 && !(await page.evaluate(() => window.sceneReady === true)); i++) {
    if (fatal) throw fatal;
    await new Promise((ok) => setTimeout(ok, 200));
  }
  return page;
}

const launchOpts = {
  headless: true,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--use-gl=angle'],
};

async function shot(page, t, type = 'jpeg') {
  await page.evaluate((tt) => window.renderAt(tt), t);
  return page.screenshot(type === 'png' ? { type } : { type, quality: 94 });
}

async function keys(times) {
  const { chromium } = await loadPlaywright();
  const srv = await serve();
  const browser = await chromium.launch(launchOpts);
  const page = await openPage(browser, srv.address().port);
  fs.mkdirSync(path.join(OUT, 'keys'), { recursive: true });
  for (const t of times) {
    const t0 = Date.now();
    const buf = await shot(page, t, 'png');
    const f = path.join(OUT, 'keys', `key_${t.toFixed(2).padStart(5, '0')}.png`);
    fs.writeFileSync(f, buf);
    console.log(`${f}  ${(Date.now() - t0)} ms`);
  }
  await browser.close(); srv.close();
}

function ffmpeg(args) {
  const p = spawn('ffmpeg', ['-v', 'error', '-y', ...args], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((ok, fail) => p.on('close', (c) => (c === 0 ? ok() : fail(new Error('ffmpeg ' + c)))));
  return { p, done };
}

async function worker(chromium, port, id, from, to) {
  const browser = await chromium.launch(launchOpts);
  const page = await openPage(browser, port);
  const seg = path.join(OUT, 'seg', `seg_${id}.mp4`);
  const { p, done } = ffmpeg(['-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '12', '-pix_fmt', 'yuv420p', seg]);
  const t0 = Date.now();
  for (let f = from; f < to; f++) {
    const buf = await shot(page, f / FPS);
    if (!p.stdin.write(buf)) await new Promise((ok) => p.stdin.once('drain', ok));
    if ((f - from) % 60 === 0) {
      const el = (Date.now() - t0) / 1000, n = f - from + 1;
      console.log(`[w${id}] кадр ${f} (${n}/${to - from}), ${(el / n).toFixed(2)} с/кадр`);
    }
  }
  p.stdin.end(); await done; await browser.close();
  return seg;
}

async function full(workers) {
  const { chromium } = await loadPlaywright();
  const srv = await serve();
  fs.mkdirSync(path.join(OUT, 'seg'), { recursive: true });
  const total = FPS * DURATION, per = Math.ceil(total / workers);
  const segs = await Promise.all(Array.from({ length: workers }, (_, i) =>
    worker(chromium, srv.address().port, i, i * per, Math.min(total, (i + 1) * per))));
  srv.close();
  const list = path.join(OUT, 'seg', 'list.txt');
  fs.writeFileSync(list, segs.map((s) => `file '${s}'`).join('\n'));
  const mp4 = path.join(OUT, 'neuroprovideo_promo_60s.mp4');
  await ffmpeg(['-f', 'concat', '-safe', '0', '-i', list, '-i', path.join(ROOT, 'music', 'track.wav'),
    '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-b:v', '10M', '-maxrate', '12M', '-bufsize', '20M',
    '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', String(FPS), '-c:a', 'aac', '-b:a', '256k', '-ar', '48000',
    '-t', String(DURATION), '-movflags', '+faststart', mp4]).done;
  await ffmpeg(['-ss', '57.5', '-i', mp4, '-frames:v', '1', '-q:v', '2', path.join(OUT, 'poster.jpg')]).done;
  console.log('готово:', mp4);
}

const [mode, ...rest] = process.argv.slice(2);
if (mode === 'keys') await keys(rest.map(Number));
else if (mode === 'full') await full(Number(rest[0] || 4));
else console.log('usage: node render.mjs keys <t...> | full [workers]');
