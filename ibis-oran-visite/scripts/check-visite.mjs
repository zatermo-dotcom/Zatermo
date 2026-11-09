// Vérification automatique de la visite : démarre le serveur de prévisualisation (dist/),
// ouvre la page dans Chromium, contrôle les quantités, parcourt les vues, le plan et les rendus,
// enregistre des captures dans docs/captures/. Usage : npm run build && npm run check
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { preview } from 'vite';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const out = new URL('../docs/captures/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });

const server = await preview({ preview: { port: 4179, host: '127.0.0.1' }, logLevel: 'silent' });
const url = 'http://127.0.0.1:4179/';
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 860 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const fail = (m) => { console.error('ÉCHEC :', m); process.exitCode = 1; };

await page.goto(url);
await page.waitForFunction(() => !!window.__tour?.stats, null, { timeout: 60000 });
const stats = await page.evaluate(() => window.__tour.stats);
console.log('Quantités :', JSON.stringify(stats));
const c = stats.chairs;
if (stats.tables !== 15 || stats.rect !== 10 || stats.carree !== 5) fail('tables');
if (c.ivoire !== 26 || c.bordeaux !== 10 || c.noir !== 4) fail('chaises');
if (stats.banquettes !== 6 || stats.banquettesL !== 3) fail('banquettes');
if (stats.ilotPortes !== 0) fail('îlot');
if (stats.lustres !== 7 || stats.appliques !== 19 || stats.spots !== 30 || stats.faces !== 26 || stats.gorges !== 6) fail('éclairage / faces');

const views = await page.evaluate(() => window.__tour.data.cameras.views.map((v) => v.id));
for (const id of views) {
  await page.evaluate((v) => window.__tour.goTo(v), id);
  await page.waitForFunction(() => !window.__tour.animating, null, { timeout: 30000 });
  await page.waitForTimeout(300);
  const cam = await page.evaluate(() => { const p = window.__tour.camera.position; return [p.x, p.z, p.y]; });
  const want = await page.evaluate((v) => window.__tour.view(v).pos, id);
  if (Math.hypot(cam[0] - want[0], cam[1] - want[1], cam[2] - want[2]) > 0.05) fail(`caméra ${id} non atteinte`);
  await page.screenshot({ path: `${out}${id}.jpg`, quality: 82 });
  console.log('vue OK', id);
}

// Plan : clic sur la zone « Espace self-service »
await page.getByRole('tab', { name: 'Plan' }).click();
await page.locator('polygon.zone').nth(2).click();
await page.waitForTimeout(500);
await page.waitForFunction(() => !window.__tour.animating, null, { timeout: 30000 });
const afterZone = await page.evaluate(() => { const p = window.__tour.camera.position; return [p.x, p.z]; });
const zoneCam = await page.evaluate(() => window.__tour.view(window.__tour.data.geometry.zones.find((z) => z.id === 'self').camera).pos);
if (Math.hypot(afterZone[0] - zoneCam[0], afterZone[1] - zoneCam[1]) > 0.1) fail('clic plan → buffet');
else console.log('plan → buffet central OK');
await page.screenshot({ path: `${out}ui-plan.jpg`, quality: 82 });

// Rendus : ouvrir un rendu associé, aller à la vue, revenir au modèle
await page.locator('.related button').first().click();
await page.waitForSelector('.lightbox img');
await page.waitForTimeout(400);
await page.screenshot({ path: `${out}ui-rendu.jpg`, quality: 82 });
await page.getByRole('button', { name: 'Retour au modèle' }).click();
if (await page.locator('.lightbox').count()) fail('retour au modèle');
else console.log('rendu → retour au modèle OK');

// Navigation : double-clic au sol dans la salle
await page.evaluate(() => window.__tour.goTo('salle-ensemble', true));
await page.waitForTimeout(300);
await page.mouse.dblclick(720, 700);
await page.waitForTimeout(200);
await page.waitForFunction(() => !window.__tour.animating, null, { timeout: 30000 });
const moved = await page.evaluate(() => { const p = window.__tour.camera.position; return [p.x, p.z]; });
console.log('double-clic au sol → position', moved.map((n) => n.toFixed(2)).join(', '));
if (Math.hypot(moved[0] - 10.9, moved[1] - 7.7) < 0.3) fail('double-clic sans déplacement');

// Murs : vue frontale de chaque face (caméra dans la salle, regard vers la face)
const faceRes = await page.evaluate(async () => {
  const t = window.__tour; const bad = [];
  for (const f of t.data.walls.faces) {
    t.goToFace(f.id);
    await new Promise((r) => { const w = () => (t.animating ? setTimeout(w, 50) : r()); w(); });
    const p = t.camera.position; const d = t.camera.getWorldDirection(new p.constructor());
    const mx = (f.a[0] + f.b[0]) / 2; const my = (f.a[1] + f.b[1]) / 2;
    const facing = -(d.x * f.n[0] + d.z * f.n[1]);
    const L = Math.hypot(f.b[0] - f.a[0], f.b[1] - f.a[1]);
    if (!t.insideRoom(p.x, p.z) || facing < (L < 0.6 ? 0.45 : 0.95) || Math.hypot(p.x - mx, p.z - my) < 0.6) bad.push(`${f.id}(${facing.toFixed(2)})`);
  }
  return bad;
});
if (faceRes.length) fail(`vues frontales incorrectes : ${faceRes.join(', ')}`); else console.log('26 vues frontales OK');
await page.getByRole('tab', { name: 'Murs' }).click();
await page.locator('table.faces button', { hasText: 'Vue 3D' }).nth(1).click(); // M02
await page.waitForTimeout(200);
await page.waitForFunction(() => !window.__tour.animating, null, { timeout: 30000 });
await page.screenshot({ path: `${out}face-M02.jpg`, quality: 82 });
await page.locator('table.faces button', { hasText: 'Élévation' }).nth(1).click();
await page.waitForSelector('.lightbox img');
await page.waitForTimeout(300);
await page.screenshot({ path: `${out}ui-elevation-M02.jpg`, quality: 82 });
await page.getByRole('button', { name: 'Vue frontale dans le modèle 3D' }).click();

// Comparaison rendu / modèle
await page.getByRole('tab', { name: 'Rendus' }).click();
await page.locator('.thumb', { hasText: 'p.14' }).click();
await page.getByRole('button', { name: 'Comparer avec le modèle' }).click();
await page.waitForSelector('.compare img', { timeout: 30000 });
const cmp = await page.locator('.compare img').first().getAttribute('src');
if (!cmp?.startsWith('data:image/jpeg')) fail('comparaison'); else console.log('comparaison rendu / modèle OK');
await page.locator('.compare input[type=range]').fill('50');
await page.waitForTimeout(300);
await page.screenshot({ path: `${out}ui-comparaison.jpg`, quality: 82 });
await page.getByRole('button', { name: 'Retour au modèle' }).click();

// Plan : double-clic sur un point de l'alcôve
await page.getByRole('tab', { name: 'Plan' }).click();
const box = await page.locator('svg.plan').boundingBox();
const toPx = (x, y) => [box.x + ((x + 0.9) / 20.1) * box.width, box.y + ((y + 0.9) / 15.0) * box.height];
const [px, py] = toPx(8.6, 10.5);
await page.mouse.dblclick(px, py);
await page.waitForTimeout(200);
await page.waitForFunction(() => !window.__tour.animating, null, { timeout: 30000 });
const pm = await page.evaluate(() => { const p = window.__tour.camera.position; return [p.x, p.z]; });
if (Math.hypot(pm[0] - 8.6, pm[1] - 10.5) > 0.25) fail(`double-clic plan → ${pm}`); else console.log('double-clic plan → alcôve OK');

// Variantes
for (const o of [{ layout: 'amenagement-01' }, { floor: 'sol-B' }, { lustre: 'vasque' }, { layout: 'amenagement-02', floor: 'sol-A', lustre: 'abat-jour', quality: 'elevee' }]) {
  await page.evaluate((x) => window.__tour.setOptions(x), o);
}
const s1 = await page.evaluate(() => window.__tour.stats);
if (s1.tables !== 15) fail('retour version principale');
await page.getByRole('tab', { name: 'Sources' }).click();
await page.screenshot({ path: `${out}ui-sources.jpg`, quality: 82 });
await page.getByRole('tab', { name: 'Réglages' }).click();
await page.screenshot({ path: `${out}ui-reglages.jpg`, quality: 82 });

// Mobile / tactile (la première page est fermée pour libérer le rendu logiciel)
await page.close();
const m = await browser.newPage({ viewport: { width: 390, height: 780 }, isMobile: true, hasTouch: true });
m.on('pageerror', (e) => errors.push(String(e)));
await m.goto(`${url}?vue=buffet-central`);
await m.waitForFunction(() => !!window.__tour?.stats, null, { timeout: 60000 });
await m.waitForTimeout(800);
await m.screenshot({ path: `${out}mobile-buffet.jpg`, quality: 80 });

if (errors.length) fail(`erreurs console : ${errors.join(' | ')}`);
await browser.close();
await new Promise((r) => server.httpServer.close(r));
console.log(process.exitCode ? 'Vérification : ÉCHECS' : 'Vérification : tout est conforme');
