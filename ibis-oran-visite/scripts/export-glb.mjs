// Exporte le modèle 3D en GLB (model/*.glb) à partir des données JSON, sans Blender.
// Usage : npm run build && npm run export:glb [-- amenagement-01 sol-B vasque]
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { preview } from 'vite';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const [layout = 'amenagement-02', floor = 'sol-A', lustre = 'abat-jour'] = process.argv.slice(2);
const outDir = new URL('../model/', import.meta.url).pathname; mkdirSync(outDir, { recursive: true });

const server = await preview({ preview: { port: 4181, host: '127.0.0.1' }, logLevel: 'silent' });
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 640, height: 400 } });
page.on('pageerror', (e) => { console.error(e); process.exitCode = 1; });
await page.goto('http://127.0.0.1:4181/');
await page.waitForFunction(() => !!window.__tour?.stats, null, { timeout: 60000 });
const bytes = await page.evaluate(async (o) => {
  window.__tour.setOptions(o);
  const buf = await window.__tour.exportGLB();
  return Array.from(new Uint8Array(buf));
}, { layout, floor, lustre, quality: 'elevee' });
const file = `${outDir}restaurant-ibis-oran_${layout}_${floor}_${lustre}.glb`;
writeFileSync(file, Buffer.from(bytes));
console.log(`GLB écrit : ${file} (${(bytes.length / 1e6).toFixed(2)} Mo)`);
await browser.close();
await new Promise((r) => server.httpServer.close(r));
