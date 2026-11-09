import * as THREE from 'three';
import type { Ceiling, Geometry, Lighting } from '../types';
import { Batch, pointInPolygon, yawFromNormal } from './util';
import type { MatLib } from './materials';

const mtx = (x: number, y: number, z: number, q?: THREE.Quaternion) => new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), q ?? new THREE.Quaternion(), new THREE.Vector3(1, 1, 1));

/**
 * Luminaires d'ambiance aux positions R07 : 7 lustres (2 styles), 19 appliques sur supports pleins.
 * Les sources lumineuses sont des réglages visuels, sans valeur photométrique.
 */
export function buildLighting(geo: Geometry, ceil: Ceiling, L: Lighting, lib: MatLib, style: string, quality: 'standard' | 'elevee') {
  const root = new THREE.Group(); root.name = 'Luminaires';
  const ba13 = geo.heights.sousFaceBA13.value;
  const shadeMat = new THREE.MeshStandardMaterial({ color: '#f3e3c2', emissive: new THREE.Color(L.lustre.color), emissiveIntensity: 1.7, roughness: 0.8, side: THREE.DoubleSide, name: 'abat_jour' });
  const bulbMat = new THREE.MeshStandardMaterial({ color: '#000', emissive: new THREE.Color('#ffd9a0'), emissiveIntensity: 4, name: 'ampoule' });
  const glassMat = new THREE.MeshStandardMaterial({ color: '#f6ead6', emissive: new THREE.Color(L.lustre.color), emissiveIntensity: 1.5, roughness: 0.4, transparent: true, opacity: 0.92, name: 'vasque' });

  // --- Lustres L01-L07 ---
  const R = L.lustre.diameter / 2; const bottom = L.lustre.dropBottom;
  for (const r of ceil.rosaces.items) {
    const b = new Batch(); const x = r.x; const z = r.y;
    if (style === 'vasque') {
      const y = bottom + 0.25;
      b.add(new THREE.CylinderGeometry(0.008, 0.008, ba13 - y, 6), lib.laiton, mtx(x, (ba13 + y) / 2, z));
      const bowl = new THREE.SphereGeometry(R * 0.72, 40, 16, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2);
      b.add(bowl, glassMat, mtx(x, y, z));
      const rim = new THREE.TorusGeometry(R * 0.72, 0.015, 8, 48); rim.rotateX(Math.PI / 2);
      b.add(rim, lib.laiton, mtx(x, y, z));
      for (let k = 0; k < 3; k++) { const a = (k / 3) * Math.PI * 2; const c = new THREE.CylinderGeometry(0.004, 0.004, 0.45, 4); b.add(c, lib.laiton, mtx(x + Math.cos(a) * R * 0.36, y + 0.22, z + Math.sin(a) * R * 0.36)); }
    } else {
      const body = bottom + 0.3; const arms = 6;
      b.add(new THREE.CylinderGeometry(0.01, 0.01, ba13 - body, 6), lib.laiton, mtx(x, (ba13 + body) / 2, z));
      b.add(new THREE.SphereGeometry(0.09, 20, 14), lib.laiton, mtx(x, body, z));
      b.add(new THREE.CylinderGeometry(0.03, 0.06, 0.25, 16), lib.laiton, mtx(x, body - 0.18, z));
      b.add(new THREE.SphereGeometry(0.045, 14, 10), lib.laiton, mtx(x, bottom, z));
      const ring = new THREE.TorusGeometry(R * 0.55, 0.012, 8, 48); ring.rotateX(Math.PI / 2);
      b.add(ring, lib.laiton, mtx(x, body - 0.08, z));
      for (let k = 0; k < arms; k++) {
        const a = (k / arms) * Math.PI * 2; const cx = Math.cos(a); const cz = Math.sin(a);
        const arm = new THREE.CylinderGeometry(0.009, 0.009, R, 6); arm.rotateZ(Math.PI / 2);
        const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -a);
        b.add(arm, lib.laiton, mtx(x + cx * R / 2, body - 0.08, z + cz * R / 2, q));
        const tx = x + cx * R; const tz = z + cz * R;
        b.add(new THREE.CylinderGeometry(0.03, 0.02, 0.05, 12), lib.laiton, mtx(tx, body - 0.05, tz));
        b.add(new THREE.CylinderGeometry(0.012, 0.012, 0.09, 8), bulbMat, mtx(tx, body + 0.02, tz));
        b.add(new THREE.CylinderGeometry(0.055, 0.09, 0.13, 20, 1, true), shadeMat, mtx(tx, body + 0.07, tz));
      }
    }
    const g = b.build(`Lustre_${r.id}`); g.userData = { id: r.id, style };
    const pl = new THREE.PointLight(L.lustre.color, L.lustre.intensity, L.lustre.distance, 1.6);
    pl.position.set(x, bottom + 0.3, z); pl.name = `Lumiere_${r.id}`;
    g.add(pl);
    root.add(g);
  }

  // --- Appliques A01-A19 : orientées depuis leur support plein vers la salle ---
  const pts = geo.outline.points;
  const minX = 0; const maxX = Math.max(...pts.map((p) => p[0]));
  for (const a of L.applique.items) {
    // normale déduite de la position collée au parement (coordonnée à 0,06 du nu)
    const n = normalFor(a.x, a.y, geo, minX, maxX);
    const yaw = yawFromNormal(n[0], n[1]);
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
    const b = new Batch(); const h = L.applique.height;
    const wx = a.x - n[0] * 0.05; const wz = a.y - n[1] * 0.05; // contre le mur
    b.add(new THREE.BoxGeometry(0.1, 0.2, 0.02), lib.laiton, mtx(wx + n[0] * 0.01, h, wz + n[1] * 0.01, q));
    for (const side of [-1, 1]) {
      const ox = Math.cos(yaw) * side * 0.14; const oz = -Math.sin(yaw) * side * 0.14;
      const px = wx + n[0] * 0.12 + ox; const pz = wz + n[1] * 0.12 + oz;
      b.add(new THREE.CylinderGeometry(0.008, 0.008, 0.2, 6), lib.laiton, mtx((wx + px) / 2, h - 0.02, (wz + pz) / 2, new THREE.Quaternion().setFromEuler(new THREE.Euler(0, yaw + side * 0.9, Math.PI / 2))));
      b.add(new THREE.CylinderGeometry(0.025, 0.018, 0.04, 10), lib.laiton, mtx(px, h + 0.04, pz));
      b.add(new THREE.CylinderGeometry(0.01, 0.01, 0.06, 8), bulbMat, mtx(px, h + 0.09, pz));
      b.add(new THREE.CylinderGeometry(0.05, 0.075, 0.12, 20, 1, true), shadeMat, mtx(px, h + 0.13, pz));
    }
    const g = b.build(`Applique_${a.id}`); g.userData = { id: a.id, support: a.support };
    if (quality === 'elevee') {
      const pl = new THREE.PointLight(L.applique.color, L.applique.intensity, L.applique.distance, 1.8);
      pl.position.set(a.x + n[0] * 0.2, h + 0.1, a.y + n[1] * 0.2); pl.name = `Lumiere_${a.id}`;
      g.add(pl);
    }
    root.add(g);
  }
  return root;
}

/** Normale (vers la salle) du support le plus proche d'un point d'applique. */
function normalFor(x: number, y: number, geo: Geometry, minX: number, maxX: number): [number, number] {
  const pts = geo.outline.points; let best = 1e9; let n: [number, number] = [0, 1];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i]; const b = pts[(i + 1) % pts.length];
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]); const ux = (b[0] - a[0]) / L; const uy = (b[1] - a[1]) / L;
    const s = (x - a[0]) * ux + (y - a[1]) * uy; if (s < -0.05 || s > L + 0.05) continue;
    const d = Math.abs(-(x - a[0]) * uy + (y - a[1]) * ux);
    if (d < best) {
      best = d;
      const c: [number, number] = [-uy, ux]; const mx = (a[0] + b[0]) / 2 + c[0] * 0.05; const my = (a[1] + b[1]) / 2 + c[1] * 0.05;
      const inside = mx > minX - 1 && mx < maxX + 1 && pointInPolygon([mx, my], pts);
      n = inside ? c : [uy, -ux];
    }
  }
  return n;
}
