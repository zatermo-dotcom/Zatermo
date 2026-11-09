import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { P2 } from '../types';

/** Repère plan R07 (X droite, Y bas, mètres) → monde Three.js (x = X, y = hauteur, z = Y). */
export const W = (x: number, y: number, h = 0) => new THREE.Vector3(x, h, y);

export function pointInPolygon(p: P2, poly: P2[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]; const [xj, yj] = poly[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function polygonArea(poly: P2[]): number {
  let a = 0;
  for (let i = 0; i < poly.length; i++) { const [x1, y1] = poly[i]; const [x2, y2] = poly[(i + 1) % poly.length]; a += x1 * y2 - x2 * y1; }
  return Math.abs(a) / 2;
}

/**
 * Regroupe des géométries par matériau puis les fusionne : beaucoup de petites moulures
 * deviennent un seul mesh par matériau (performances), nommé pour l'export GLB.
 */
export class Batch {
  private parts = new Map<THREE.Material, THREE.BufferGeometry[]>();
  add(geo: THREE.BufferGeometry, mat: THREE.Material, matrix?: THREE.Matrix4) {
    const g = geo.index ? geo.toNonIndexed() : geo.clone();
    if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    if (matrix) g.applyMatrix4(matrix);
    const list = this.parts.get(mat) ?? [];
    list.push(g); this.parts.set(mat, list);
  }
  /** Boîte orientée : centre (monde), dimensions (le long de l'axe u, hauteur, profondeur), rotation Y. */
  box(mat: THREE.Material, cx: number, cy: number, cz: number, sx: number, sy: number, sz: number, rotY = 0) {
    const m = new THREE.Matrix4().compose(new THREE.Vector3(cx, cy, cz), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), rotY), new THREE.Vector3(1, 1, 1));
    this.add(new THREE.BoxGeometry(sx, sy, sz), mat, m);
  }
  build(name: string): THREE.Group {
    const g = new THREE.Group(); g.name = name;
    for (const [mat, geos] of this.parts) {
      const merged = mergeGeometries(geos, false);
      if (!merged) continue;
      const mesh = new THREE.Mesh(merged, mat);
      mesh.name = `${name}_${mat.name || 'mat'}`;
      g.add(mesh);
      geos.forEach((x) => x.dispose());
    }
    this.parts.clear();
    return g;
  }
}

/** Angle (rotation autour de Y) qui aligne l'axe local +X sur la direction plan (dx, dy). */
export const yawFromDir = (dx: number, dy: number) => -Math.atan2(dy, dx);

/** Rotation Y qui oriente l'axe local +Z vers la normale plan n. */
export const yawFromNormal = (nx: number, ny: number) => Math.atan2(nx, ny);
