import * as THREE from 'three';
import type { Branch, Furniture, Side, TableDef } from '../types';
import { Batch, yawFromNormal } from './util';
import type { MatLib } from './materials';

const Y = new THREE.Vector3(0, 1, 0);
const mtx = (x: number, y: number, z: number, rotY = 0, s = 1) =>
  new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), new THREE.Quaternion().setFromAxisAngle(Y, rotY), new THREE.Vector3(s, s, s));

/** Résout une implantation (gestion des variantes « basedOn / removeTables »). */
export function resolveTables(f: Furniture, key: string): TableDef[] {
  const l = f.layouts[key];
  if (!l) return [];
  if (l.tables) return l.tables;
  const base = resolveTables(f, l.basedOn ?? '');
  return base.filter((t) => !(l.removeTables ?? []).includes(t.id));
}

/** Chaise (gabarit p.102) : piètement bois sombre, assise, dossier capitonné Chesterfield côté intérieur seulement. Face avant = +Z local. */
function chairGroup(f: Furniture, lib: MatLib, colorKey: string, cache: Map<string, THREE.Group>) {
  const hit = cache.get(colorKey); if (hit) return hit.clone();
  const s = f.specs.chaise; const b = new Batch();
  const fabric = lib[`tissu_${colorKey}`] ?? (lib[`tissu_${colorKey}`] = Object.assign(new THREE.MeshStandardMaterial({ color: f.chairColors[colorKey] ?? '#ccc', roughness: colorKey === 'noir' ? 0.55 : 0.85 }), { name: `tissu_${colorKey}` }));
  const legH = s.seatH - 0.09; const w = s.w; const d = s.d;
  for (const [lx, lz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]] as const) {
    const g = new THREE.CylinderGeometry(0.018, 0.013, legH, 10);
    b.add(g, lib.boisSombre, mtx(lx * (w / 2 - 0.04), legH / 2, lz * (d / 2 - 0.05)));
  }
  b.box(fabric, 0, s.seatH - 0.045, 0.02, w, 0.09, d - 0.04);           // assise
  const backH = s.h - s.seatH; const bz = -d / 2 + 0.05;
  b.box(fabric, 0, s.seatH + backH / 2 - 0.02, bz, w - 0.02, backH, 0.08); // dossier
  b.box(fabric, 0, s.h - 0.03, bz, w - 0.02, 0.06, 0.09);
  // capitonnage (boutons) uniquement sur la face intérieure du dossier
  const btn = new THREE.SphereGeometry(0.011, 8, 6);
  const dark = lib[`bouton_${colorKey}`] ?? (lib[`bouton_${colorKey}`] = Object.assign(fabric.clone(), { name: `bouton_${colorKey}` }));
  dark.color = fabric.color.clone().multiplyScalar(0.55);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4 - (r % 2); c++) {
    const n = 4 - (r % 2); const x = (c - (n - 1) / 2) * 0.1; const y = s.seatH + 0.12 + r * 0.1;
    b.add(btn, dark, mtx(x, y, bz + 0.04));
  }
  const g = b.build(`Chaise_${colorKey}`); cache.set(colorKey, g);
  return g.clone();
}

function tableGroup(f: Furniture, lib: MatLib, type: 'rect' | 'carree') {
  const s = type === 'rect' ? f.specs.tableRect : f.specs.tableCarree; const b = new Batch();
  b.box(lib.marbreCreme, 0, s.h - s.top / 2, 0, s.w, s.top, s.d);
  b.box(lib.laiton, 0, s.h - s.top - 0.01, 0, s.w - 0.06, 0.02, s.d - 0.06);
  b.add(new THREE.CylinderGeometry(0.045, 0.055, s.h - 0.08, 20), lib.noirPietement, mtx(0, (s.h - 0.08) / 2 + 0.03, 0));
  b.add(new THREE.CylinderGeometry(0.06, 0.06, 0.04, 20), lib.laiton, mtx(0, 0.2, 0));
  const baseR = type === 'rect' ? 0.3 : 0.28;
  b.add(new THREE.CylinderGeometry(baseR, baseR + 0.02, 0.03, 40), lib.noirPietement, mtx(0, 0.015, 0));
  b.add(new THREE.CylinderGeometry(baseR + 0.022, baseR + 0.022, 0.012, 40), lib.laiton, mtx(0, 0.006, 0));
  return b.build(`Table_${type}`);
}

const SIDE: Record<Side, [number, number]> = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };

export function buildTables(f: Furniture, lib: MatLib, layoutKey: string) {
  const root = new THREE.Group(); root.name = `Tables_et_chaises_${layoutKey}`;
  const cache = new Map<string, THREE.Group>();
  const tplRect = tableGroup(f, lib, 'rect'); const tplSq = tableGroup(f, lib, 'carree');
  const count: Record<string, number> = {};
  const tables = resolveTables(f, layoutKey);
  for (const t of tables) {
    const tg = (t.type === 'rect' ? tplRect : tplSq).clone();
    tg.name = t.id; tg.position.set(t.x, 0, t.y); tg.rotation.y = -THREE.MathUtils.degToRad(t.rot);
    tg.userData = { id: t.id, type: t.type };
    root.add(tg);
    const s = t.type === 'rect' ? f.specs.tableRect : f.specs.tableCarree;
    const rot = THREE.MathUtils.degToRad(t.rot);
    for (const [side, off, color] of t.chairs) {
      // côté exprimé dans le repère plan (N = -Y) ; dimension de table selon la rotation
      const [nx, ny] = SIDE[side];
      const alongX = Math.abs(Math.cos(rot)) > 0.5 ? s.w : s.d; const alongY = Math.abs(Math.cos(rot)) > 0.5 ? s.d : s.w;
      const half = nx !== 0 ? alongX / 2 : alongY / 2;
      const dist = half + 0.12;
      const px = t.x + nx * dist + (nx === 0 ? off : 0); const py = t.y + ny * dist + (ny === 0 ? off : 0);
      const ch = chairGroup(f, lib, color, cache);
      ch.position.set(px, 0, py);
      ch.rotation.y = yawFromNormal(-nx, -ny); // face avant (+Z local) vers la table
      ch.name = `${t.id}_chaise_${side}${off >= 0 ? '+' : ''}${off}`; ch.userData = { color };
      root.add(ch);
      count[color] = (count[color] ?? 0) + 1;
    }
  }
  root.userData = { tables: tables.length, rect: tables.filter((t) => t.type === 'rect').length, carree: tables.filter((t) => t.type === 'carree').length, chairs: count };
  return root;
}

/** Banquette le long d'une branche (dos contre le mur, assise vers n). */
function addBranch(b: Batch, br: Branch, depth: number, fn: (b: Batch, L: number, put: (mat: THREE.Material, s0: number, s1: number, d0: number, d1: number, h0: number, h1: number) => void, place: (s: number, d: number) => [number, number], yaw: number) => void) {
  const L = Math.hypot(br.b[0] - br.a[0], br.b[1] - br.a[1]);
  const ux = (br.b[0] - br.a[0]) / L; const uy = (br.b[1] - br.a[1]) / L;
  const yaw = yawFromNormal(br.n[0], br.n[1]);
  const place = (s: number, d: number): [number, number] => [br.a[0] + ux * s + br.n[0] * d, br.a[1] + uy * s + br.n[1] * d];
  const put = (mat: THREE.Material, s0: number, s1: number, d0: number, d1: number, h0: number, h1: number) => {
    const [x, z] = place((s0 + s1) / 2, (d0 + d1) / 2);
    // la boîte est construite dans le repère (u, h, n) : largeur L sur u
    const m = new THREE.Matrix4().compose(new THREE.Vector3(x, (h0 + h1) / 2, z), new THREE.Quaternion().setFromAxisAngle(Y, yaw), new THREE.Vector3(1, 1, 1));
    // l'axe local X est colinéaire à u car n est perpendiculaire à la branche
    b.add(new THREE.BoxGeometry(s1 - s0, h1 - h0, d1 - d0), mat, m);
  };
  fn(b, L, put, place, yaw);
  void depth;
}

export function buildBanquettes(f: Furniture, lib: MatLib) {
  const root = new THREE.Group(); root.name = 'Banquettes';
  const s = f.specs.banquette; const D = s.depth;
  const btnMat = Object.assign(lib.veloursBordeaux.clone(), { name: 'bouton_bordeaux' }); btnMat.color.multiplyScalar(0.5);
  const btn = new THREE.SphereGeometry(0.014, 8, 6);
  for (const bq of f.banquettes) {
    const b = new Batch();
    for (const br of bq.branches) {
      addBranch(b, br, D, (bb, L, put, place) => {
        put(lib.socleBanquette, 0, L, 0.04, D - 0.03, 0, 0.12);           // soubassement foncé
        put(lib.veloursBordeaux, 0, L, 0.16, D, 0.12, s.seatH);          // assise
        put(lib.veloursBordeaux, 0, L, 0, 0.18, 0.12, s.h);              // dossier
        put(lib.veloursBordeaux, 0, L, 0.0, 0.2, s.h - 0.05, s.h);       // bourrelet
        // capitonnage en losanges sur la face du dossier
        for (let r = 0; r < 3; r++) for (let x = 0.12 + (r % 2) * 0.1; x < L - 0.08; x += 0.2) {
          const [px, pz] = place(x, 0.185);
          bb.add(btn, btnMat, mtx(px, s.seatH + 0.1 + r * 0.11, pz));
        }
      });
    }
    const g = b.build(bq.id); g.userData = { type: bq.type, note: bq.note ?? '' };
    root.add(g);
  }
  return root;
}

/** Buffets périphériques : caissons à portes (rangements fermés), plinthe noire, plateau marbre clair. */
export function buildBuffets(f: Furniture, lib: MatLib) {
  const root = new THREE.Group(); root.name = 'Buffets_peripheriques';
  const s = f.specs.buffetPeripherique;
  for (const bf of f.buffets) {
    const b = new Batch(); const D = bf.depth;
    for (const br of bf.branches) {
      addBranch(b, br, D, (bb, L, put, place, yaw) => {
        put(lib.buffetPlinthe, 0, L, 0, D - 0.05, 0, 0.1);
        put(lib.buffetCaisson, 0, L, 0, D - 0.03, 0.1, s.h - s.top);
        put(lib.marbreCreme, 0, L, 0, D + 0.02, s.h - s.top, s.h);
        // portes : panneaux à cadre doré + bouton
        const n = Math.max(1, Math.round(L / 0.55)); const pw = L / n;
        for (let k = 0; k < n; k++) {
          const s0 = k * pw + 0.03; const s1 = (k + 1) * pw - 0.03;
          put(lib.buffetCaisson, s0, s1, D - 0.03, D - 0.01, 0.13, s.h - s.top - 0.05);
          const fz0 = D - 0.01; const fz1 = D + 0.002; const h0 = 0.2; const h1 = s.h - s.top - 0.12;
          put(lib.moulure, s0 + 0.05, s1 - 0.05, fz0, fz1, h1 - 0.012, h1); put(lib.moulure, s0 + 0.05, s1 - 0.05, fz0, fz1, h0, h0 + 0.012);
          put(lib.moulure, s0 + 0.05, s0 + 0.062, fz0, fz1, h0, h1); put(lib.moulure, s1 - 0.062, s1 - 0.05, fz0, fz1, h0, h1);
          const [kx, kz] = place(k % 2 === 0 ? s1 - 0.04 : s0 + 0.04, D + 0.01);
          bb.add(new THREE.SphereGeometry(0.012, 10, 8), lib.laiton, mtx(kx, 0.62, kz, yaw));
        }
      });
    }
    const g = b.build(bf.id); g.userData = { type: bf.type, note: bf.note ?? '' };
    root.add(g);
  }
  return root;
}

/** Îlot central 2,20 × 1,80 × 0,90 : 4 travées ouvertes par grande face (8), 2 niches par travée (16), sans porte. */
export function buildIlot(f: Furniture, lib: MatLib) {
  const s = f.specs.ilot; const b = new Batch();
  const W = s.w; const D = s.d; const H = s.h; const T = s.top;
  const body = H - T; const plinth = 0.1; const panel = 0.03;
  b.box(lib.buffetPlinthe, 0, plinth / 2, 0, W - 0.08, plinth, D - 0.08);
  b.box(lib.marbreCreme, 0, H - T / 2, 0, W + 0.04, T, D + 0.04);
  b.box(lib.buffetCaisson, 0, body - panel / 2, 0, W, panel, D);                 // dessus du caisson
  b.box(lib.buffetCaisson, 0, plinth + panel / 2, 0, W, panel, D);               // fond
  b.box(lib.buffetCaisson, 0, (plinth + body) / 2, 0, W, body - plinth, 0.04);   // âme centrale
  for (const sx of [-1, 1]) b.box(lib.buffetCaisson, sx * (W / 2 - panel / 2), (plinth + body) / 2, 0, panel, body - plinth, D); // joues (petites faces)
  // petites faces : cadres dorés
  for (const sx of [-1, 1]) for (const [z0, z1] of [[-D / 2 + 0.1, -0.06], [0.06, D / 2 - 0.1]] as const) {
    const x = sx * (W / 2 + 0.002); const h0 = 0.2; const h1 = body - 0.08; const zc = (z0 + z1) / 2;
    b.box(lib.moulure, x, h0, zc, 0.006, 0.014, z1 - z0); b.box(lib.moulure, x, h1, zc, 0.006, 0.014, z1 - z0);
    b.box(lib.moulure, x, (h0 + h1) / 2, z0, 0.006, h1 - h0, 0.014); b.box(lib.moulure, x, (h0 + h1) / 2, z1, 0.006, h1 - h0, 0.014);
  }
  const bays = s.bays / 2; const inner = W - 2 * panel; const bw = inner / bays;
  const plate = new THREE.CylinderGeometry(0.12, 0.1, 0.012, 28);
  for (const sz of [-1, 1]) {
    for (let k = 1; k < bays; k++) b.box(lib.buffetCaisson, -inner / 2 + k * bw, (plinth + body) / 2, sz * D / 4, 0.03, body - plinth, D / 2 - 0.02);
    const shelfY = (plinth + body) / 2;
    b.box(lib.buffetCaisson, 0, shelfY, sz * D / 4, inner, 0.025, D / 2 - 0.02);   // 2 niches par travée
    b.box(lib.moulure, 0, body - 0.01, sz * (D / 2 + 0.002), W, 0.02, 0.006);
    b.box(lib.moulure, 0, plinth + 0.03, sz * (D / 2 + 0.002), W, 0.012, 0.006);
    for (let k = 0; k < bays; k++) {
      const x = -inner / 2 + (k + 0.5) * bw;
      for (const y0 of [plinth + panel, shelfY + 0.0125]) for (let p = 0; p < 7; p++) b.add(plate, lib.plafond, mtx(x, y0 + 0.008 + p * 0.013, sz * D / 4));
    }
  }
  const g = b.build('Ilot_central');
  const il = f.ilot; g.position.set(il.x, 0, il.y); g.rotation.y = -THREE.MathUtils.degToRad(il.rot);
  g.userData = { dims: [W, D, H], bays: s.bays, niches: s.niches, portes: 0 };
  return g;
}
