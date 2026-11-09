import * as THREE from 'three';
import type { Ceiling, Geometry, Lighting } from '../types';
import { Batch } from './util';
import { gorgeGlowTexture, type MatLib } from './materials';

/**
 * Plafond R07 interprété : bandeaux + périphérie en sous-face +3,30 ; caissons G1-G6 ouverts jusqu'au BA13 +3,60 ;
 * gorge (tablette P, lèvre, ruban LED à 0,133 m) ; cadres moulurés autour des caissons ; rosaces ; spots.
 */
export function buildCeiling(geo: Geometry, c: Ceiling, light: Lighting, lib: MatLib) {
  const root = new THREE.Group(); root.name = 'Plafond';
  const hz = geo.heights;
  const ba13 = hz.sousFaceBA13.value; const low = hz.dessousGorge.value;
  const pts = geo.outline.points;
  const plafond = lib.plafond.clone(); plafond.side = THREE.DoubleSide; plafond.name = 'plafond';

  // BA13 (fond des caissons)
  const top = new THREE.ShapeGeometry(new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y))));
  top.rotateX(Math.PI / 2); top.translate(0, ba13, 0);
  const topMesh = new THREE.Mesh(top, plafond); topMesh.name = 'BA13_sous_face_3.60';
  root.add(topMesh);

  // bandeau +3,30 percé des caissons
  const band = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
  for (const g of c.gorges) {
    band.holes.push(new THREE.Path([new THREE.Vector2(g.x0, g.y0), new THREE.Vector2(g.x0, g.y1), new THREE.Vector2(g.x1, g.y1), new THREE.Vector2(g.x1, g.y0)]));
  }
  const bandGeo = new THREE.ShapeGeometry(band); bandGeo.rotateX(Math.PI / 2); bandGeo.translate(0, low, 0);
  const bandMesh = new THREE.Mesh(bandGeo, plafond); bandMesh.name = 'Bandeau_dessous_gorge_3.30';
  root.add(bandMesh);

  const glowTex = gorgeGlowTexture(light.gorgeLed.color);
  const led = new THREE.MeshStandardMaterial({ color: '#000000', emissive: new THREE.Color(light.gorgeLed.color), emissiveIntensity: light.gorgeLed.intensity * 1.6, name: 'led_gorge' });
  const P = c.gorge.saillieP; const inset = c.gorge.ledInset; const lipTop = ba13 - c.gorge.ouvertureO;

  for (const g of c.gorges) {
    const b = new Batch();
    const w = g.x1 - g.x0; const d = g.y1 - g.y0; const cx = (g.x0 + g.x1) / 2; const cz = (g.y0 + g.y1) / 2;
    const ring = (mat: THREE.Material, off: number, wid: number, h0: number, h1: number) => {
      // anneau rectangulaire : bord extérieur décalé de `off` vers l'intérieur du caisson (off<0 = vers l'extérieur)
      const x0 = g.x0 + off; const x1 = g.x1 - off; const y0 = g.y0 + off; const y1 = g.y1 - off;
      const hy = (h0 + h1) / 2; const hh = h1 - h0;
      b.box(mat, (x0 + x1) / 2, hy, y0 + wid / 2, x1 - x0, hh, wid);
      b.box(mat, (x0 + x1) / 2, hy, y1 - wid / 2, x1 - x0, hh, wid);
      b.box(mat, x0 + wid / 2, hy, (y0 + y1) / 2, wid, hh, y1 - y0 - 2 * wid);
      b.box(mat, x1 - wid / 2, hy, (y0 + y1) / 2, wid, hh, y1 - y0 - 2 * wid);
    };
    ring(plafond, -0.02, 0.02, low, ba13);          // joue du caisson
    ring(plafond, 0, P, low, low + 0.03);            // tablette de gorge (saillie P)
    ring(plafond, P - 0.02, 0.02, low, lipTop);      // lèvre / cache-vue
    ring(led, inset - 0.008, 0.016, low + 0.03, low + 0.042); // ruban LED
    // cadres moulurés sur le bandeau (profil schématique, motif non inventé)
    ring(lib.corniche, -0.10, 0.06, low - 0.03, low);
    ring(lib.corniche, -0.22, 0.03, low - 0.018, low);
    ring(lib.moulure, -0.05, 0.012, low - 0.02, low);
    const grp = b.build(`Caisson_${g.id}`);
    // halo de gorge sur le fond du caisson
    const glowMat = new THREE.MeshStandardMaterial({ color: lib.plafond.color, roughness: 0.9, emissive: new THREE.Color('#ffffff'), emissiveMap: glowTex, emissiveIntensity: light.gorgeLed.intensity * 0.55, name: `halo_${g.id}` });
    const glow = new THREE.Mesh(new THREE.PlaneGeometry(w, d), glowMat);
    glow.rotation.x = Math.PI / 2; glow.position.set(cx, ba13 - 0.004, cz); glow.name = `Halo_${g.id}`;
    grp.add(glow);
    grp.userData = { gorge: g.id, ledLength: g.led };
    root.add(grp);
  }

  // Rosaces (emprise et anneaux de relief ; ornement réel à relever)
  const D = c.rosaces.diameter;
  for (const r of c.rosaces.items) {
    const b = new Batch();
    const m = new THREE.Matrix4();
    const disc = new THREE.CylinderGeometry(D / 2, D / 2, 0.02, 64);
    b.add(disc, lib.rosace, m.makeTranslation(r.x, ba13 - 0.01, r.y));
    for (const [rr, tube] of [[D * 0.48, 0.022], [D * 0.36, 0.016], [D * 0.24, 0.02], [D * 0.1, 0.03]] as const) {
      const tor = new THREE.TorusGeometry(rr, tube, 10, 72); tor.rotateX(Math.PI / 2);
      b.add(tor, lib.rosace, new THREE.Matrix4().makeTranslation(r.x, ba13 - 0.022, r.y));
    }
    const grp = b.build(`Rosace_${r.id}`); grp.userData = { id: r.id, x: r.x, y: r.y };
    root.add(grp);
  }

  // Spots encastrés : sur le bandeau (+3,30) ou dans un caisson (+3,60)
  const sb = new Batch();
  const spotMat = new THREE.MeshStandardMaterial({ color: '#000', emissive: new THREE.Color(light.spot.color), emissiveIntensity: 3, name: 'spot' });
  const opened = (x: number, y: number) => c.gorges.some((g) => x > g.x0 + P && x < g.x1 - P && y > g.y0 + P && y < g.y1 - P);
  for (const [, x, y] of light.spot.items) {
    const h = opened(x, y) ? ba13 : low;
    const r = light.spot.diameter / 2;
    const trim = new THREE.CylinderGeometry(r + 0.015, r + 0.015, 0.008, 24);
    sb.add(trim, lib.laiton, new THREE.Matrix4().makeTranslation(x, h - 0.004, y));
    sb.add(new THREE.CylinderGeometry(r, r, 0.004, 24), spotMat, new THREE.Matrix4().makeTranslation(x, h - 0.009, y));
  }
  root.add(sb.build('Spots_30'));
  return root;
}
