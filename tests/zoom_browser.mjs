// The figure at full size (reports), in a real browser: node tests/zoom_browser.mjs
// Not run by the unit tests: it needs Playwright with Chromium, found from this folder or by NODE_PATH. It serves pages made
// here (a temporary folder) with `talkpage serve --reports`.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = createRequire(import.meta.url)('playwright');
const REPO = fileURLToPath(new URL('..', import.meta.url));

const svgFile = (w, h, fill) => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">` +
  `<rect width="${w}" height="${h}" fill="${fill}"/><path d="M0 0L${w} ${h}" stroke="#000" stroke-width="${w / 100}"/></svg>`;
const HEAD = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>zoom</title><style>
  body { background: #fbf8ee; } main { max-width: 760px; margin: 0 auto; }
  img { max-width: 240px; height: auto; border: 4px solid red; padding: 3px; }
  #lb { display: none; position: fixed; inset: 0; background: #000; } #lb.on { display: block; }
  .tall { height: 1500px; }
  main svg text { fill: rgb(200, 0, 0); }
</style></head><body>`;
// a report with a smaller view of its own, as older ones have
const OLD = `<div id="lb"><img alt=""></div><script>
  window.opened = 0;
  document.querySelectorAll('figure img, #draw, #plain').forEach((i) => i.addEventListener('click', () => {
    window.opened++; document.getElementById('lb').className = 'on';
  }));
</script>`;
const FIGURES = `
  <h1>Figures</h1>
  <p id="para">Some text of the report to comment on.</p>
  <figure><img id="mid" src="/mid.svg" data-full="/big.svg" alt=""></figure>
  <figure><img id="small" src="/small.svg" alt=""></figure>
  <svg id="draw" viewBox="0 0 400 200" style="width:400px;font-size:20px">
    <text id="word" x="10" y="40">several words of the drawing</text>
    <path d="M0 100H400" stroke="#000"/><a href="#jumped"><rect id="link" x="300" y="120" width="80" height="60"/></a>
  </svg>
  <svg id="plain" width="300" height="150"><circle cx="75" cy="75" r="70"/></svg>
  <svg id="icon" viewBox="0 0 16 16" width="16" height="16"><rect width="16" height="16"/></svg>
  <a id="linked" href="#jumped"><img src="/small.svg" alt=""></a>
  <button id="control"><img src="/small.svg" alt=""></button>
  <img id="off" src="/small.svg" data-talk-nozoom alt="">
  <div data-talk-nozoom><img id="off2" src="/small.svg" alt=""></div>
  <p class="tall"></p>`;

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'talkpage-zoom-'));
const write = (p, text) => {
  const f = path.join(root, ...p.split('/'));
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, text);
};
write('small.svg', svgFile(200, 100, '#cde'));
write('mid.svg', svgFile(1600, 800, '#dec'));
write('big.svg', svgFile(6400, 3200, '#edc'));
const OLD_PAGE = 'old/20261103-1000-r1/index.html', NO_MAIN = 'nomain/20261103-1000-r1/index.html';
write(OLD_PAGE, HEAD + `<main>${FIGURES}</main>${OLD}</body></html>`);
write(NO_MAIN, HEAD + FIGURES + OLD + '</body></html>');
// a page with a copy of the layer of its own (delegated click, its element marked as ours)
write('copy/20261103-1000-r1/index.html', HEAD + `<main>${FIGURES}</main><div id="zoom" class="talk-ui" hidden><img alt=""></div><script>
  window.opened = 0;
  document.addEventListener('click', (e) => {
    const i = e.target.closest('img');
    if (i && !i.closest('#zoom, a, .talk-ui')) { window.opened++; document.getElementById('zoom').hidden = false; }
  });
</script></body></html>`);
// a page of talkpage items, not a report: nothing changes for it
write('items/index.html', HEAD + `<script src="/_talk/talkpage.js" defer></script><main>${FIGURES}</main>${OLD}</body></html>`);

const free = await new Promise((ok) => {
  const s = net.createServer().listen(0, '127.0.0.1', () => { const { port } = s.address(); s.close(() => ok(port)); });
});
const server = spawn(process.env.PYTHON || 'python', [path.join(REPO, 'talkpage.py'), 'serve', root, '--reports', '--port', String(free)], { stdio: 'ignore' });
const BASE = `http://127.0.0.1:${free}/`;
for (let i = 0; ; i++) {
  try { if ((await fetch(BASE + '_talk/api/info')).ok) break; } catch (e) { /* not up yet */ }
  if (i > 50) throw new Error('the server did not start');
  await new Promise((ok) => setTimeout(ok, 200));
}

let fails = 0;
const ok = (c, name, extra = '') => {
  console.log(`${c ? 'ok' : 'NG'}  ${name}${c ? '' : '  ' + JSON.stringify(extra)}`);
  if (!c) fails++;
};
const near = (a, b, d = 2) => Math.abs(a - b) < d;
const st = (page) => page.evaluate(() => {
  const z = document.querySelector('.talk-zoom'), f = z.querySelector('.talk-zoom-fig'), r = f && f.getBoundingClientRect();
  const y = z.getBoundingClientRect();
  return {
    open: !z.hidden, pct: z.querySelector('.talk-zoom-pct').textContent, tag: f && f.tagName, x: r && r.x, y: r && r.y, w: r && r.width, h: r && r.height,
    zw: z.clientWidth, zh: z.clientHeight, zx: y.x, zy: y.y, src: f && new URL(f.src || location.href).pathname, viewBox: f && f.getAttribute('viewBox'),
    cursor: f && getComputedStyle(f).cursor, border: f && getComputedStyle(f).borderTopWidth, maxw: f && getComputedStyle(f).maxWidth, bg: f && getComputedStyle(f).backgroundColor,
    font: f && getComputedStyle(f).fontSize, back: getComputedStyle(z).backgroundColor, layerZ: getComputedStyle(z).zIndex,
    plusOff: z.querySelectorAll('button')[2].disabled, minusOff: z.querySelectorAll('button')[0].disabled,
  };
});
const opened = (page) => page.evaluate(() => window.opened);
const button = (page, i) => page.locator('.talk-zoom-bar button').nth(i);
const load = async (ctx, p) => {
  const page = await ctx.newPage();
  page.errors = [];
  page.on('pageerror', (e) => page.errors.push(String(e)));
  await page.goto(BASE + p, { waitUntil: 'load' });   // not networkidle: the page keeps a long poll open
  await page.waitForFunction(() => document.querySelector('.talk-dock'));
  return page;
};

const browser = await chromium.launch();
try {
  // ---- with a mouse
  const pc = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  let page = await load(pc, OLD_PAGE);
  let big = 0;
  page.on('request', (r) => { if (r.url().endsWith('/big.svg')) big++; });
  await page.locator('#mid').click();
  let s = await st(page);
  ok(s.open && s.pct === '100%' && s.cursor === 'zoom-in', 'a press opens it at 100%, the cursor a plus', s);
  ok(await opened(page) === 0, "the report's own view stays shut");
  ok(s.back === 'rgba(10, 12, 16, 0.7)', 'the page is seen behind it', s.back);
  ok(s.layerZ === '3000', 'over the cards (2000 the highest)', s.layerZ);
  ok(s.border === '0px' && s.maxw === 'none', "the report's CSS for images does not reach it", s);
  ok(near(s.w, s.zw - 32) && near(s.h, s.w / 2), 'as wide as the window allows', s);
  ok(big === 0 && s.src === '/mid.svg', 'data-full is not read while the pixels are enough', [big, s.src]);
  const cx = s.x + s.w / 2, cy = s.y + s.h / 3;
  await page.mouse.click(cx, cy);
  await page.waitForFunction(() => document.querySelector('.talk-zoom-fig').src.endsWith('/big.svg'));
  s = await st(page);
  ok(s.pct === '200%' && big === 1, 'the next press: 200%, data-full takes over once the pixels run short', [s.pct, big]);
  await page.mouse.click(cx, cy);
  s = await st(page);
  ok(s.pct === '400%' && s.cursor === 'zoom-in', '400%', s.pct);
  await page.mouse.click(cx, cy);
  s = await st(page);
  ok(s.pct === '800%' && s.cursor === 'zoom-out' && s.plusOff, '800%, the cursor a minus', s);
  ok(s.x <= 0 && s.x + s.w >= s.zw && s.y <= 0 && s.y + s.h >= s.zh, 'no gap at its edges', s);
  const b4 = s;
  await page.mouse.move(640, 400);
  await page.mouse.down();
  await page.mouse.move(440, 200, { steps: 5 });
  await page.mouse.up();
  s = await st(page);
  ok(s.pct === '800%' && near(s.x - b4.x, -200) && near(s.y - b4.y, -200), 'a drag moves it and is no press', [s.pct, s.x - b4.x, s.y - b4.y]);
  await page.mouse.click(640, 400);
  s = await st(page);
  ok(s.open && s.pct === '100%' && s.minusOff, 'a press at 800% goes back to the whole', s);
  const wx = s.x + s.w * .25, wy = s.y + s.h * .5, u0 = (wx - s.x) / s.w;
  await page.mouse.move(wx, wy);
  await page.mouse.wheel(0, -100);
  await page.mouse.wheel(0, -100);
  await page.waitForFunction(() => document.querySelector('.talk-zoom-pct').textContent !== '100%');
  await page.waitForTimeout(50);
  s = await st(page);
  ok(parseInt(s.pct, 10) > 130 && parseInt(s.pct, 10) < 170, 'the wheel zooms by little', s.pct);
  ok(Math.abs((wx - s.x) / s.w - u0) < .003, 'the point under the wheel stays', [u0, (wx - s.x) / s.w]);
  const report = () => page.locator('.talk-sb-zoom').textContent();
  const z0 = await report();
  await page.keyboard.down('Control');
  await page.mouse.wheel(0, 100);
  await page.keyboard.up('Control');
  await page.waitForTimeout(50);
  ok(await report() === z0, "Ctrl + wheel zooms the figure, not the report's text", [z0, await report()]);
  await button(page, 2).click();
  s = await st(page);
  ok(s.pct === '200%', 'the + button', s.pct);
  await button(page, 2).click();
  await button(page, 0).click();
  s = await st(page);
  ok(s.pct === '200%', 'the − button', s.pct);
  await button(page, 1).click();
  s = await st(page);
  ok(s.pct === '100%' && s.minusOff, 'the % button: the whole', s.pct);
  await page.keyboard.press('+');
  s = await st(page);
  ok(s.pct === '200%', 'the + key', s.pct);
  const x0 = s.x;
  await page.keyboard.press('ArrowLeft');
  s = await st(page);
  ok(s.x !== x0 || s.w <= s.zw, 'the arrow keys', [x0, s.x]);
  await page.keyboard.press('-');
  s = await st(page);
  ok(s.pct === '100%', 'the − key', s.pct);
  await page.keyboard.press('Escape');
  ok(!(await st(page)).open, 'Esc closes');
  await page.locator('#mid').click();
  s = await st(page);
  ok(s.pct === '100%' && s.src === '/mid.svg', 'opens anew at 100% with the image of the page', s);
  await page.mouse.click(4, 400);
  ok(!(await st(page)).open, 'a press beside it closes');
  await page.locator('#mid').click();
  await button(page, 3).click();
  ok(!(await st(page)).open, '× closes');
  await page.locator('#mid').click();
  await button(page, 3).focus();
  await page.keyboard.press('Enter');
  ok(!(await st(page)).open, 'Enter on a button works');
  await page.locator('#small').click();
  s = await st(page);
  ok(near(s.w, s.zw - 32), 'a small image is spread over the window too', s.w);
  await page.keyboard.press('Escape');
  ok(await opened(page) === 0, "the report's own view stayed shut all along");

  // the figures left alone
  for (const [sel, name] of [['#icon', 'an icon'], ['#control img', 'an image in a button'], ['#off', 'data-talk-nozoom'], ['#off2', 'data-talk-nozoom on an ancestor']]) {
    await page.locator(sel).click();
    ok(!(await st(page)).open, 'not opened: ' + name);
  }
  await page.locator('#linked img').click();
  ok(!(await st(page)).open && await page.evaluate(() => location.hash) === '#jumped', 'an image in a link stays a link');
  await page.evaluate(() => { location.hash = ''; });

  // a drawing
  await page.locator('#draw').click({ position: { x: 200, y: 120 } });
  s = await st(page);
  ok(s.open && s.tag === 'svg' && near(s.h, s.w / 2), 'a drawn figure opens, in its proportions', s);
  ok(s.bg === 'rgb(251, 248, 238)', 'on the colour of the page, not on the dark layer', s.bg);
  ok(s.font === '20px', 'its own styles stay', s.font);
  ok(await page.evaluate(() => getComputedStyle(document.querySelector('.talk-zoom-fig text')).fill) === 'rgb(200, 0, 0)', "and what the report's CSS gave it by its place in the page");
  ok(await opened(page) === 0, "the report's own view stays shut");
  const l = await page.evaluate(() => { const r = document.querySelector('.talk-zoom-fig a rect').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
  await page.mouse.click(l[0], l[1]);
  s = await st(page);
  ok(s.pct === '200%' && await page.evaluate(() => location.hash) === '', 'a link in the copy is a press like any other', [s.pct]);
  await page.keyboard.press('Escape');
  await page.locator('#plain').click();
  s = await st(page);
  ok(s.viewBox === '0 0 300 150' && near(s.h, s.w / 2), 'a drawing without a viewBox scales too', s);
  await page.keyboard.press('Escape');
  await page.locator('#word').scrollIntoViewIfNeeded();
  const box = await page.locator('#word').boundingBox();
  await page.mouse.move(box.x + 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 2, box.y + box.height / 2, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(50);
  s = await st(page);
  ok(!s.open && await opened(page) === 0, 'selecting words of a drawing opens nothing', [s.open, await opened(page), box]);
  ok(await page.evaluate(() => getSelection().toString().length) > 3 && await page.locator('.talk-selbtn').isVisible(), 'and offers the comment button');
  await page.mouse.click(4, 4);

  // with a comment being written (the sidebar closed: a card in the margin, not in the middle of the screen)
  await page.locator('.talk-sb-tog').click();
  await page.locator('#para').selectText();
  await page.mouse.move(100, 100);
  await page.evaluate(() => document.dispatchEvent(new MouseEvent('mouseup')));
  await page.locator('.talk-selbtn').click();
  await page.locator('.talk-rcard textarea').fill('about the figure');
  await page.locator('#mid').click();
  ok((await st(page)).open, 'a figure opens while a comment is written');
  await page.mouse.click(640, 400);
  await page.keyboard.press('Escape');
  ok(!(await st(page)).open && await page.locator('.talk-rcard textarea').inputValue() === 'about the figure', 'Esc closes it, the comment stays');
  await page.keyboard.press('Escape');
  ok(await page.locator('.talk-rcard').count() === 0, 'the next Esc is for the comment again');
  await page.locator('.talk-sb-tog').click();

  // under the zoom of the report
  await page.locator('.talk-sb-zoom').waitFor();
  await page.locator('.talk-sb-zbtn').nth(1).click();
  await page.locator('.talk-sb-zbtn').nth(1).click();
  await page.locator('#plain').click();
  s = await st(page);
  ok(s.viewBox === '0 0 300 150', "a viewBox made under the report's zoom is the same", s.viewBox);
  await page.keyboard.press('Escape');
  await page.locator('#draw').click({ position: { x: 200, y: 120 } });
  const size = await page.evaluate(() => getComputedStyle(document.querySelector('.talk-zoom-fig text')).fontSize);
  ok(size === '20px', "the report's zoom does not reach the sizes in a drawing", size);
  await page.keyboard.press('Escape');
  await page.locator('.talk-sb-zoom').click();
  ok(page.errors.length === 0, 'no errors in the page', page.errors);
  await page.close();

  page = await load(pc, 'copy/20261103-1000-r1/index.html');
  await page.locator('#mid').click();
  s = await st(page);
  ok(s.open && await page.evaluate(() => document.getElementById('zoom').hidden) && await opened(page) === 0, 'a page with a copy of the layer opens one only');
  await page.keyboard.press('Escape');
  await page.locator('#link').click();
  ok(!(await st(page)).open && await page.evaluate(() => location.hash) === '#jumped', 'a link in the drawing stays a link');
  await page.close();

  page = await load(pc, NO_MAIN);
  await page.locator('#mid').click();
  s = await st(page);
  ok(s.open && await page.evaluate(() => !!document.querySelector('.talk-content') && !document.querySelector('.talk-content .talk-zoom')), 'a report without <main>');
  await page.close();

  page = await load(pc, 'items/index.html');
  await page.locator('#mid').click();
  ok(await page.locator('.talk-zoom').count() === 0 && await opened(page) === 1, 'a page that is no report keeps its own view');
  await page.close();
  await pc.close();

  // ---- with fingers
  const sp = await browser.newContext({ viewport: { width: 375, height: 700 }, hasTouch: true, isMobile: true, deviceScaleFactor: 3 });
  page = await load(sp, OLD_PAGE);
  ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) <= 0, 'no sideways scrolling on a phone');
  await page.locator('#mid').tap();
  s = await st(page);
  ok(s.open && s.pct === '100%' && near(s.w, s.zw - 2 * s.zw * .02), 'a tap opens it', s);
  await page.touchscreen.tap(187, 350);
  s = await st(page);
  ok(s.pct === '200%', 'a tap on it: 200%', s.pct);
  const cdp = await sp.newCDPSession(page);
  const touch = (type, pts) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map(([x, y], i) => ({ x, y, id: i })) });
  await touch('touchStart', [[150, 350], [225, 350]]);
  for (let k = 1; k <= 5; k++) await touch('touchMove', [[150 - 10 * k, 350], [225 + 10 * k, 350]]);
  await touch('touchEnd', []);
  await page.waitForTimeout(50);
  s = await st(page);
  ok(parseInt(s.pct, 10) > 300 && parseInt(s.pct, 10) < 500, 'two fingers zoom', s.pct);
  const f0 = s;
  await touch('touchStart', [[200, 350]]);
  for (let k = 1; k <= 5; k++) await touch('touchMove', [[200 - 20 * k, 350 - 10 * k]]);
  await touch('touchEnd', []);
  await page.waitForTimeout(50);
  s = await st(page);
  ok(near(s.x - f0.x, -100, 3) && s.pct === f0.pct, 'one finger moves it', [s.x - f0.x, s.pct]);
  await button(page, 1).tap();
  await page.waitForTimeout(50);
  s = await st(page);
  ok(s.pct === '100%', 'a tap on % right after a drag', s.pct);
  await page.touchscreen.tap(187, Math.max(12, s.y - 20));
  await page.waitForTimeout(600);
  ok(!(await st(page)).open && await opened(page) === 0, 'a tap beside it closes, and the tap reaches nothing below');
  await page.locator('#mid').tap();
  ok((await st(page)).open, 'opens again');
  await button(page, 3).tap();
  await page.waitForTimeout(600);
  ok(!(await st(page)).open, '× by a tap closes');
  await page.locator('#draw').tap({ position: { x: 100, y: 60 } });
  s = await st(page);
  ok(s.open && s.tag === 'svg', 'a tap opens a drawing', s);
  await button(page, 3).tap();
  await page.waitForTimeout(600);

  // the page zoomed by pinch: what opens lies over what is on screen, its buttons in reach
  await page.locator('#mid').scrollIntoViewIfNeeded();
  await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 2.5 });
  await page.waitForTimeout(300);
  const at = await page.evaluate(() => { const r = document.getElementById('mid').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await page.touchscreen.tap(at[0], at[1]);   // through CDP: in the coordinates of the page, not of the screen
  await page.waitForTimeout(200);
  s = await st(page);
  const q = await page.evaluate(() => { const v = visualViewport, x = document.querySelectorAll('.talk-zoom-bar button')[3].getBoundingClientRect(); return { l: v.offsetLeft, t: v.offsetTop, w: v.width, h: v.height, scale: v.scale, x: [x.left, x.top, x.width, x.height] }; });
  ok(s.open && near(s.zx, q.l) && near(s.zy, q.t) && near(s.zw, q.w) && near(s.zh, q.h), 'zoomed by pinch: over what is on screen', [s.zx, s.zy, s.zw, s.zh, q]);
  ok(q.x[0] >= q.l - 1 && q.x[1] >= q.t - 1 && q.x[0] + q.x[2] <= q.l + q.w + 1 && q.x[1] + q.x[3] <= q.t + q.h + 1 && near(q.x[2] * q.scale, 42), 'its buttons on screen, at their own size', q);
  await page.touchscreen.tap(q.x[0] + q.x[2] / 2, q.x[1] + q.x[3] / 2);
  await page.waitForTimeout(600);
  ok(!(await st(page)).open, '× closes it there');
  ok(page.errors.length === 0, 'no errors in the page', page.errors);
  await sp.close();
} finally {
  await browser.close();
  server.kill();
  await new Promise((ok) => setTimeout(ok, 200));
  fs.rmSync(root, { recursive: true, force: true });
}
console.log(fails ? `${fails} failed` : 'all ok');
process.exitCode = fails ? 1 : 0;
