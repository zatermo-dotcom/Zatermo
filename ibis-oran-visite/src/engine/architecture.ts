import * as THREE from 'three';
import type { Ceiling, Geometry, Materials, Opening, P2 } from '../types';
import { Batch, pointInPolygon, yawFromDir } from './util';
import { floorTexture, type MatLib } from './materials';

/** Sol, murs percés des baies, poteau, menuiseries. */
export function buildArchitecture(geo: Geometry, ceiling: Ceiling, materials: Materials, lib: MatLib, floorKey: string) {
  const root = new THREE.Group(); root.name = 'Architecture';
  const pts = geo.outline.points;
  const H = geo.heights.plafondExistant.value;
  const t = geo.wallThickness.value;

  // ---- Sol (texture de calepinage) ----
  const variant = materials.floorVariants[floorKey] ?? Object.values(materials.floorVariants)[0];
  const { tex, sizeX, sizeY } = floorTexture(geo, ceiling, materials, variant);
  const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, -y)));
  // seuils sous les baies et l'accès, pour éviter un vide visuel
  const floorGeo = new THREE.ShapeGeometry(shape);
  floorGeo.rotateX(-Math.PI / 2);
  const pos = floorGeo.attributes.position; const uv = floorGeo.attributes.uv;
  for (let i = 0; i < pos.count; i++) uv.setXY(i, pos.getX(i) / sizeX, 1 - pos.getZ(i) / sizeY);
  const floorMat = lib.marbreCreme.clone(); floorMat.name = 'sol'; floorMat.map = tex; floorMat.color.set('#ffffff');
  const floor = new THREE.Mesh(floorGeo, floorMat); floor.name = `Sol_${floorKey}`; floor.userData.isFloor = true;
  root.add(floor);

  // sol extérieur neutre (vue générale)
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: '#2b2622', roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.position.set(9, -0.02, 6.5); ground.name = 'Exterieur_non_modelise';
  root.add(ground);

  // ---- Murs ----
  const walls = new Batch();
  const area2 = pts.reduce((s, p, i) => { const q = pts[(i + 1) % pts.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0);
  const sign = Math.sign(area2);
  const isConvex = (i: number) => {
    const p0 = pts[(i - 1 + pts.length) % pts.length]; const p1 = pts[i]; const p2 = pts[(i + 1) % pts.length];
    const cross = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0]);
    return Math.sign(cross) === sign;
  };
  const onEdge = (o: Opening, a: P2, b: P2) => {
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]); const ux = (b[0] - a[0]) / L; const uy = (b[1] - a[1]) / L;
    const proj = (p: P2) => ({ s: (p[0] - a[0]) * ux + (p[1] - a[1]) * uy, d: Math.abs(-(p[0] - a[0]) * uy + (p[1] - a[1]) * ux) });
    const pa = proj(o.a); const pb = proj(o.b);
    if (pa.d > 0.02 || pb.d > 0.02) return null;
    const s0 = Math.min(pa.s, pb.s); const s1 = Math.max(pa.s, pb.s);
    if (s1 < -1e-3 || s0 > L + 1e-3) return null;
    return { s0, s1 };
  };

  for (let i = 0; i < pts.length; i++) {
    const a = pts[i]; const b = pts[(i + 1) % pts.length];
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const ux = (b[0] - a[0]) / L; const uy = (b[1] - a[1]) / L;
    let nx = -uy; let ny = ux; // normale gauche
    const mid: P2 = [(a[0] + b[0]) / 2 + nx * 0.05, (a[1] + b[1]) / 2 + ny * 0.05];
    if (pointInPolygon(mid, pts)) { nx = -nx; ny = -ny; } // n = extérieur
    const e0 = isConvex(i) ? t : 0; const e1 = isConvex((i + 1) % pts.length) ? t : 0;
    const ops = geo.openings.map((o) => ({ o, r: onEdge(o, a, b) })).filter((x) => x.r).sort((p, q) => p.r!.s0 - q.r!.s0);
    // segments pleins
    let cursor = -e0;
    const yaw = yawFromDir(ux, uy);
    const seg = (s0: number, s1: number, h0: number, h1: number) => {
      if (s1 - s0 < 1e-4 || h1 - h0 < 1e-4) return;
      const sm = (s0 + s1) / 2;
      walls.box(lib.mur, a[0] + ux * sm + nx * t / 2, (h0 + h1) / 2, a[1] + uy * sm + ny * t / 2, s1 - s0, h1 - h0, t, yaw);
    };
    for (const { o, r } of ops) {
      seg(cursor, r!.s0, 0, H);
      seg(r!.s0, r!.s1, o.height, H); // linteau
      if (o.sill) seg(r!.s0, r!.s1, 0, o.sill);
      cursor = r!.s1;
      root.add(buildOpening(o, [nx, ny], t, lib));
    }
    seg(cursor, L + e1, 0, H);
  }
  // Poteau central et joue de l'accès
  const p = geo.poteau;
  walls.box(lib.mur, p.x + p.w / 2, H / 2, p.y + p.d / 2, p.w, H, p.d);
  const j = geo.jambeAcces;
  walls.box(lib.mur, j.x + j.w / 2, H / 2, j.y + j.d / 2, j.w, H, j.d);
  const wallGroup = walls.build('Murs');
  wallGroup.children.forEach((m) => { m.userData.isWall = true; });
  root.add(wallGroup);
  return { root, floor };
}

/** Menuiseries : portes-fenêtres, baies fixes, porte cuisine, accès (ouvert). */
function buildOpening(o: Opening, n: P2, t: number, lib: MatLib) {
  const g = new THREE.Group(); g.name = `Baie_${o.id}`; g.userData = { label: o.label, status: o.status, pages: o.pages };
  const b = new Batch();
  const L = Math.hypot(o.b[0] - o.a[0], o.b[1] - o.a[1]);
  const ux = (o.b[0] - o.a[0]) / L; const uy = (o.b[1] - o.a[1]) / L;
  const yaw = yawFromDir(ux, uy);
  const at = (s: number, off: number) => [o.a[0] + ux * s + n[0] * off, o.a[1] + uy * s + n[1] * off] as const;
  const fr = 0.06; const off = t * 0.5; const h = o.height;
  const bar = (s0: number, s1: number, h0: number, h1: number, mat: THREE.Material, depth = 0.07, o2 = off) => {
    const [x, z] = at((s0 + s1) / 2, o2); b.box(mat, x, (h0 + h1) / 2, z, Math.max(s1 - s0, 0.001), h1 - h0, depth, yaw);
  };
  if (o.type === 'acces') {
    bar(0, L, -0.005, 0.005, lib.marbreNoir, t);
    g.add(b.build(`Baie_${o.id}`)); return g;
  }
  if (o.type === 'porte') {
    const leaves = o.leaves ?? 1; const lw = L / leaves;
    const leafOff = t * 0.15; const moldOff = leafOff - 0.0225 - 0.006;
    for (let k = 0; k < leaves; k++) {
      bar(k * lw + 0.01, (k + 1) * lw - 0.01, 0.0, h, lib.porte, 0.045, leafOff);
      // cadres moulurés de vantail
      for (const [h0, h1] of [[0.25, 1.0], [1.2, h - 0.2]] as const) {
        const s0 = k * lw + 0.12; const s1 = (k + 1) * lw - 0.12;
        bar(s0, s1, h0, h0 + 0.025, lib.moulure, 0.012, moldOff); bar(s0, s1, h1 - 0.025, h1, lib.moulure, 0.012, moldOff);
        bar(s0, s0 + 0.025, h0, h1, lib.moulure, 0.012, moldOff); bar(s1 - 0.025, s1, h0, h1, lib.moulure, 0.012, moldOff);
      }
      const hs = k === 0 ? (k + 1) * lw - 0.1 : k * lw + 0.1;
      bar(hs - 0.06, hs + 0.06, 1.04, 1.06, lib.laiton, 0.02, leafOff - 0.05);
    }
    bar(-0.05, 0, 0, h + 0.05, lib.menuiserie, t + 0.02, off); bar(L, L + 0.05, 0, h + 0.05, lib.menuiserie, t + 0.02, off);
    bar(-0.05, L + 0.05, h, h + 0.05, lib.menuiserie, t + 0.02, off);
    g.add(b.build(`Porte_${o.id}`)); return g;
  }
  // vitrages : cadre, montants, imposte (hauteurs à confirmer)
  bar(0, fr, 0, h, lib.menuiserie); bar(L - fr, L, 0, h, lib.menuiserie);
  bar(0, L, h - fr, h, lib.menuiserie); bar(0, L, 0, fr, lib.menuiserie);
  const transom = Math.min(2.35, h - 0.4);
  bar(0, L, transom - fr / 2, transom + fr / 2, lib.menuiserie);
  const divisions = o.type === 'porte-fenetre' ? (o.leaves ?? 2) : 3;
  for (let k = 1; k < divisions; k++) { const s = (L * k) / divisions; bar(s - fr / 2, s + fr / 2, 0, h, lib.menuiserie); }
  if (o.type === 'porte-fenetre') {
    for (let k = 0; k < divisions; k++) { const s = (L * (k + 0.5)) / divisions + (k === 0 ? 0.3 : -0.3); bar(s - 0.015, s + 0.015, 0.95, 1.25, lib.laiton, 0.09); }
  }
  const glassGeo = new THREE.PlaneGeometry(L, h);
  const glass = new THREE.Mesh(glassGeo, lib.vitrage);
  const [gx, gz] = at(L / 2, off);
  glass.position.set(gx, h / 2, gz); glass.rotation.y = yaw; glass.name = `Vitrage_${o.id}`;
  g.add(glass);
  g.add(b.build(`Menuiserie_${o.id}`));
  return g;
}
