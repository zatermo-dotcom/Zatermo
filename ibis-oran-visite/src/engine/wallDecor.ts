import * as THREE from 'three';
import type { Geometry, Walls } from '../types';
import { Batch, yawFromDir } from './util';
import type { MatLib } from './materials';

/**
 * Décor mural V3 (p.39-69) : double encadrement (01 + 02 en retrait de 70 mm) en partie haute,
 * cimaise 03 continue à +1,10, partie basse lisse, plinthe, petite corniche sous le bandeau +3,30.
 */
export function buildWallDecor(walls: Walls, geo: Geometry, lib: MatLib) {
  const root = new THREE.Group(); root.name = 'Decor_mural';
  const hz = geo.heights;
  const bas = hz.basCadres.value; const haut = hz.hautCadres.value;
  const cim = hz.axeCimaise.value; const pl = hz.plinthe.value; const gorge = hz.dessousGorge.value;
  const P = walls.profiles;
  for (const f of walls.faces) {
    const b = new Batch();
    const L = Math.hypot(f.b[0] - f.a[0], f.b[1] - f.a[1]);
    const ux = (f.b[0] - f.a[0]) / L; const uy = (f.b[1] - f.a[1]) / L;
    const yaw = yawFromDir(ux, uy);
    const put = (mat: THREE.Material, s0: number, s1: number, h0: number, h1: number, depth: number) => {
      const s = (s0 + s1) / 2; const x = f.a[0] + ux * s + f.n[0] * depth / 2; const z = f.a[1] + uy * s + f.n[1] * depth / 2;
      b.box(mat, x, (h0 + h1) / 2, z, s1 - s0, h1 - h0, depth, yaw);
    };
    const rect = (mat: THREE.Material, s0: number, s1: number, h0: number, h1: number, w: number, d: number) => {
      put(mat, s0, s1, h1 - w, h1, d); put(mat, s0, s1, h0, h0 + w, d);
      put(mat, s0, s0 + w, h0 + w, h1 - w, d); put(mat, s1 - w, s1, h0 + w, h1 - w, d);
    };
    // cimaise 03 (continue), plinthe, corniche de raccord
    put(lib.cimaise, 0, L, cim - P.cimaise03.width / 2, cim + P.cimaise03.width / 2, P.cimaise03.depth);
    put(lib.plinthe, 0, L, 0, pl, 0.012);
    put(lib.corniche, 0, L, gorge - 0.08, gorge, 0.05);
    put(lib.corniche, 0, L, gorge - 0.11, gorge - 0.08, 0.025);
    // cadres en partie haute uniquement
    const widths = f.frames.map((w) => w / 1000);
    if (widths.length) {
      const gap = widths.length > 1 ? 0.18 : 0;
      const total = widths.reduce((s, w) => s + w, 0) + gap * (widths.length - 1);
      let s = (L - total) / 2;
      const hFrame = P.frameHeight01; const h0 = bas + (haut - bas - hFrame) / 2;
      for (const w of widths) {
        rect(lib.moulure, s, s + w, h0, h0 + hFrame, P.cadre01.width, P.cadre01.depth);
        const o = P.cadre02.offset;
        if (w - 2 * o > 0.04) rect(lib.moulure, s + o, s + w - o, h0 + o, h0 + hFrame - o, P.cadre02.width, P.cadre02.depth);
        s += w + gap;
      }
    }
    const g = b.build(f.id);
    g.userData = { label: f.label, status: f.status, page: f.page, frames: f.frames };
    root.add(g);
  }
  return root;
}
