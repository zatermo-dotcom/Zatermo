import * as THREE from 'three';
import type { Ceiling, FloorVariant, Geometry, MatDef, Materials } from '../types';

export type MatLib = Record<string, THREE.MeshStandardMaterial>;

/** Construit un matériau PBR nommé par entrée de materials.json (éditable). */
export function buildMaterials(m: Materials): MatLib {
  const lib: MatLib = {};
  for (const [key, v] of Object.entries(m)) {
    if (!v || typeof v !== 'object' || !('color' in (v as object))) continue;
    const d = v as MatDef;
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(d.color), roughness: d.roughness ?? 0.7, metalness: d.metalness ?? 0,
    });
    if (d.opacity !== undefined) { mat.transparent = true; mat.opacity = d.opacity; mat.depthWrite = false; }
    mat.name = key;
    lib[key] = mat;
  }
  return lib;
}

/** Générateur pseudo-aléatoire déterministe (même veinage à chaque chargement). */
function rng(seed: number) { return () => ((seed = (seed * 16807) % 2147483647) / 2147483647); }

/**
 * Texture du sol : dalles marbre crème (joints ton pierre) + cadres de marbre noir
 * alignés sur les caissons G1-G6 (calepinage p.22). Variante = largeur de bande.
 */
export function floorTexture(geo: Geometry, ceiling: Ceiling, mats: Materials, v: FloorVariant, pxPerM = 110) {
  const pts = geo.outline.points;
  const maxX = Math.max(...pts.map((p) => p[0])); const maxY = Math.max(...pts.map((p) => p[1]));
  const W = Math.ceil(maxX * pxPerM); const H = Math.ceil(maxY * pxPerM);
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d')!;
  const cream = (mats.marbreCreme as MatDef).color; const black = (mats.marbreNoir as MatDef).color;
  const joint = (mats.joint as MatDef).color;
  g.fillStyle = cream; g.fillRect(0, 0, W, H);
  const r = rng(7);
  // veinage léger (texture de matériau, pas un motif de calepinage)
  for (let i = 0; i < 260; i++) {
    g.strokeStyle = `rgba(${150 + r() * 40},${130 + r() * 30},${100 + r() * 30},${0.05 + r() * 0.08})`;
    g.lineWidth = 0.6 + r() * 1.6;
    g.beginPath(); let x = r() * W; let y = r() * H; g.moveTo(x, y);
    for (let k = 0; k < 6; k++) { const nx = x + (r() - 0.3) * 160; const ny = y + (r() - 0.5) * 90; g.quadraticCurveTo((x + nx) / 2 + (r() - 0.5) * 40, (y + ny) / 2 + (r() - 0.5) * 40, nx, ny); x = nx; y = ny; }
    g.stroke();
  }
  // joints de dalles, trame alignée sur l'origine O
  g.strokeStyle = joint; g.lineWidth = Math.max(1, pxPerM * 0.004);
  for (let x = 0; x <= maxX + 1e-6; x += v.tile) { g.beginPath(); g.moveTo(x * pxPerM, 0); g.lineTo(x * pxPerM, H); g.stroke(); }
  for (let y = 0; y <= maxY + 1e-6; y += v.tile) { g.beginPath(); g.moveTo(0, y * pxPerM); g.lineTo(W, y * pxPerM); g.stroke(); }
  // cadres noirs : bord extérieur = cadre de gorge
  const band = v.band * pxPerM;
  const drawBand = (x0: number, y0: number, x1: number, y1: number, b: number) => {
    g.fillStyle = black;
    g.fillRect(x0, y0, x1 - x0, b); g.fillRect(x0, y1 - b, x1 - x0, b);
    g.fillRect(x0, y0, b, y1 - y0); g.fillRect(x1 - b, y0, b, y1 - y0);
    g.strokeStyle = 'rgba(200,160,90,0.35)'; g.lineWidth = 1;
    for (let i = 0; i < 18; i++) { // veines dorées du marbre noir
      const t = r(); const side = Math.floor(r() * 4);
      const sx = side < 2 ? x0 + t * (x1 - x0) : side === 2 ? x0 + r() * b : x1 - r() * b;
      const sy = side >= 2 ? y0 + t * (y1 - y0) : side === 0 ? y0 + r() * b : y1 - r() * b;
      g.beginPath(); g.moveTo(sx, sy); g.lineTo(sx + (r() - 0.5) * 30, sy + (r() - 0.5) * 30); g.stroke();
    }
  };
  for (const gg of ceiling.gorges) drawBand(gg.x0 * pxPerM, gg.y0 * pxPerM, gg.x1 * pxPerM, gg.y1 * pxPerM, band);
  // cadre autour du poteau (p.22)
  const p = geo.poteau; const m = 0.12 + v.band;
  drawBand((p.x - m) * pxPerM, (p.y - m) * pxPerM, (p.x + p.w + m) * pxPerM, (p.y + p.d + m) * pxPerM, Math.min(band, 0.1 * pxPerM + band / 3));
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return { tex, sizeX: W / pxPerM, sizeY: H / pxPerM };
}

/** Halo de gorge lumineuse projeté sur la sous-face du caisson (plus intense sur les bords). */
export function gorgeGlowTexture(color: string) {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d')!;
  const col = new THREE.Color(color);
  const rgb = `${Math.round(col.r * 255)},${Math.round(col.g * 255)},${Math.round(col.b * 255)}`;
  g.fillStyle = 'rgb(0,0,0)'; g.fillRect(0, 0, 256, 256);
  const edge = (x0: number, y0: number, x1: number, y1: number) => {
    const gr = g.createLinearGradient(x0, y0, x1, y1);
    gr.addColorStop(0, `rgba(${rgb},0.95)`); gr.addColorStop(0.35, `rgba(${rgb},0.25)`); gr.addColorStop(1, `rgba(${rgb},0)`);
    return gr;
  };
  g.globalCompositeOperation = 'lighter';
  g.fillStyle = edge(0, 0, 0, 90); g.fillRect(0, 0, 256, 90);
  g.fillStyle = edge(0, 256, 0, 166); g.fillRect(0, 166, 256, 90);
  g.fillStyle = edge(0, 0, 90, 0); g.fillRect(0, 0, 90, 256);
  g.fillStyle = edge(256, 0, 166, 0); g.fillRect(166, 0, 90, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Fond extérieur neutre (nuit) : l'extérieur n'est pas modélisé. */
export function skyTexture() {
  const c = document.createElement('canvas'); c.width = 16; c.height = 256;
  const g = c.getContext('2d')!;
  const gr = g.createLinearGradient(0, 0, 0, 256);
  gr.addColorStop(0, '#0b1222'); gr.addColorStop(0.55, '#1b2a44'); gr.addColorStop(0.75, '#3a3a48'); gr.addColorStop(1, '#141418');
  g.fillStyle = gr; g.fillRect(0, 0, 16, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.mapping = THREE.EquirectangularReflectionMapping;
  return t;
}
