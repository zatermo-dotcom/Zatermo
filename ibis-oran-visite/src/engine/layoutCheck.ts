import type { Furniture, Geometry, P2, Side, TableDef } from '../types';
import { pointInPolygon } from './util';
import { resolveTables } from './furniture';

/** Emprise au sol : rectangle orienté (repère plan), rattaché à un groupe (table + ses chaises, banquette…). */
export interface Footprint { id: string; group: string; kind: 'table' | 'chaise' | 'banquette' | 'buffet' | 'ilot'; label: string; corners: P2[] }
export interface Issue { level: 'conflit' | 'passage'; a: string; b: string; text: string; at: P2; gap?: number }

const rect = (cx: number, cy: number, w: number, d: number, ang: number): P2[] => {
  const c = Math.cos(ang); const s = Math.sin(ang);
  return ([[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]] as P2[]).map(([x, y]) => [cx + x * c - y * s, cy + x * s + y * c]);
};
const SIDE: Record<Side, P2> = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };

/** Position et orientation d'une chaise (même règle que le constructeur 3D). */
export function chairPose(f: Furniture, t: TableDef, side: Side, off: number) {
  const s = t.type === 'rect' ? f.specs.tableRect : f.specs.tableCarree;
  const rot = (t.rot * Math.PI) / 180;
  const [nx, ny] = SIDE[side];
  const alongX = Math.abs(Math.cos(rot)) > 0.5 ? s.w : s.d; const alongY = Math.abs(Math.cos(rot)) > 0.5 ? s.d : s.w;
  const half = nx !== 0 ? alongX / 2 : alongY / 2;
  const dist = half + 0.12;
  return { x: t.x + nx * dist + (nx === 0 ? off : 0), y: t.y + ny * dist + (ny === 0 ? off : 0), nx, ny };
}

export function footprints(f: Furniture, layout: string): Footprint[] {
  const out: Footprint[] = [];
  for (const t of resolveTables(f, layout)) {
    const s = t.type === 'rect' ? f.specs.tableRect : f.specs.tableCarree;
    out.push({ id: t.id, group: t.id, kind: 'table', label: `Table ${t.id}`, corners: rect(t.x, t.y, s.w, s.d, (t.rot * Math.PI) / 180) });
    t.chairs.forEach(([side, off], i) => {
      const p = chairPose(f, t, side, off); const c = f.specs.chaise;
      // emprise de la chaise côté salle uniquement : la partie glissée sous la table est ignorée
      const back = 0.28 + 0.0; const front = 0.12; const depth = back + front;
      const cx = p.x + p.nx * (back - front) / 2 * 1; const cy = p.y + p.ny * (back - front) / 2;
      const ang = Math.atan2(p.ny, p.nx) + Math.PI / 2;
      out.push({ id: `${t.id}.c${i + 1}`, group: t.id, kind: 'chaise', label: `Chaise ${side} de ${t.id}`, corners: rect(cx, cy, c.w, depth, ang) });
    });
  }
  const strip = (id: string, kind: Footprint['kind'], label: string, a: P2, b: P2, n: P2, D: number, k: number) => {
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const cx = (a[0] + b[0]) / 2 + n[0] * D / 2; const cy = (a[1] + b[1]) / 2 + n[1] * D / 2;
    out.push({ id: `${id}.${k}`, group: id, kind, label, corners: rect(cx, cy, L, D, Math.atan2(b[1] - a[1], b[0] - a[0])) });
  };
  for (const b of f.banquettes) b.branches.forEach((br, k) => strip(b.id, 'banquette', `Banquette ${b.id}`, br.a, br.b, br.n, f.specs.banquette.depth, k));
  for (const b of f.buffets) b.branches.forEach((br, k) => strip(b.id, 'buffet', `Buffet ${b.id}`, br.a, br.b, br.n, b.depth, k));
  const il = f.ilot; const s = f.specs.ilot;
  out.push({ id: 'ILOT', group: 'ILOT', kind: 'ilot', label: 'Îlot central', corners: rect(il.x, il.y, s.w + 0.04, s.d + 0.04, (il.rot * Math.PI) / 180) });
  return out;
}

// ---- géométrie 2D ----
const axes = (p: P2[]) => [0, 1].map((i) => { const [x1, y1] = p[i]; const [x2, y2] = p[i + 1]; const l = Math.hypot(x2 - x1, y2 - y1); return [-(y2 - y1) / l, (x2 - x1) / l] as P2; });
function overlap(a: P2[], b: P2[], tol = 0.01) {
  for (const ax of [...axes(a), ...axes(b)]) {
    const pa = a.map((p) => p[0] * ax[0] + p[1] * ax[1]); const pb = b.map((p) => p[0] * ax[0] + p[1] * ax[1]);
    if (Math.max(...pa) - tol <= Math.min(...pb) || Math.max(...pb) - tol <= Math.min(...pa)) return false;
  }
  return true;
}
const segDist = (p: P2, a: P2, b: P2) => {
  const dx = b[0] - a[0]; const dy = b[1] - a[1]; const l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
};
function polyDist(a: P2[], b: P2[]) {
  if (overlap(a, b, 0)) return 0;
  let d = Infinity;
  for (const p of a) for (let i = 0; i < b.length; i++) d = Math.min(d, segDist(p, b[i], b[(i + 1) % b.length]));
  for (const p of b) for (let i = 0; i < a.length; i++) d = Math.min(d, segDist(p, a[i], a[(i + 1) % a.length]));
  return d;
}
const centroid = (p: P2[]): P2 => [p.reduce((s, q) => s + q[0], 0) / p.length, p.reduce((s, q) => s + q[1], 0) / p.length];

/**
 * Contrôle de l'implantation (indicatif, pas une vérification réglementaire) :
 * - conflits : emprises qui se chevauchent, sortent du contour, touchent le poteau ou une baie ouvrante ;
 * - passages : écart libre entre deux groupes de mobilier inférieur au seuil (mesure en plan).
 */
export function checkLayout(f: Furniture, g: Geometry, layout: string, passage = 0.6): Issue[] {
  const fp = footprints(f, layout); const issues: Issue[] = [];
  const outline = g.outline.points; const pt = g.poteau;
  const pot: P2[] = [[pt.x, pt.y], [pt.x + pt.w, pt.y], [pt.x + pt.w, pt.y + pt.d], [pt.x, pt.y + pt.d]];
  const j = g.jambeAcces;
  const jam: P2[] = [[j.x, j.y], [j.x + j.w, j.y], [j.x + j.w, j.y + j.d], [j.x, j.y + j.d]];
  for (const a of fp) {
    const shrunk = a.corners.map((c) => { const m = centroid(a.corners); return [m[0] + (c[0] - m[0]) * 0.98, m[1] + (c[1] - m[1]) * 0.98] as P2; });
    if (shrunk.some((c) => !pointInPolygon(c, outline))) issues.push({ level: 'conflit', a: a.id, b: 'mur', text: `${a.label} dépasse le nu des murs`, at: centroid(a.corners) });
    if (overlap(a.corners, pot)) issues.push({ level: 'conflit', a: a.id, b: 'poteau', text: `${a.label} touche le poteau central`, at: centroid(a.corners) });
    if (overlap(a.corners, jam)) issues.push({ level: 'conflit', a: a.id, b: 'joue', text: `${a.label} touche la joue de l'accès`, at: centroid(a.corners) });
    for (const o of g.openings.filter((x) => x.type !== 'fixe')) {
      // débattement / passage devant une porte : bande de 0,90 m côté salle
      const L = Math.hypot(o.b[0] - o.a[0], o.b[1] - o.a[1]); const ux = (o.b[0] - o.a[0]) / L; const uy = (o.b[1] - o.a[1]) / L;
      let nx = -uy; let ny = ux; const m: P2 = [(o.a[0] + o.b[0]) / 2 + nx * 0.1, (o.a[1] + o.b[1]) / 2 + ny * 0.1];
      if (!pointInPolygon(m, outline)) { nx = -nx; ny = -ny; }
      const zone: P2[] = [o.a, o.b, [o.b[0] + nx * 0.9, o.b[1] + ny * 0.9], [o.a[0] + nx * 0.9, o.a[1] + ny * 0.9]];
      if (!overlap(a.corners, zone)) continue;
      if (o.type === 'porte-fenetre') issues.push({ level: 'passage', a: a.id, b: o.id, gap: 0, text: `${a.label} devant la baie ${o.id} : dégagement à confirmer`, at: centroid(a.corners) });
      else issues.push({ level: 'conflit', a: a.id, b: o.id, text: `${a.label} empiète sur le dégagement de 0,90 m de la baie ${o.id}`, at: centroid(a.corners) });
    }
  }
  // tables alignées le long d'une même banquette : rangée voulue, l'écart n'est pas un passage
  const banqOf = (tid: string) => new Set(fp.filter((x) => x.kind === 'banquette' && polyDist(x.corners, fp.find((t) => t.id === tid)!.corners) < 0.35).map((x) => x.group));
  const sameRow = (a: Footprint, b: Footprint) => a.kind === 'table' && b.kind === 'table' && [...banqOf(a.id)].some((x) => banqOf(b.id).has(x));
  const groups = new Map<string, Footprint[]>();
  fp.forEach((x) => groups.set(x.group, [...(groups.get(x.group) ?? []), x]));
  const keys = [...groups.keys()];
  for (let i = 0; i < keys.length; i++) for (let k = i + 1; k < keys.length; k++) {
    let best = Infinity; let pair: [Footprint, Footprint] | null = null;
    for (const a of groups.get(keys[i])!) for (const b of groups.get(keys[k])!) {
      const d = polyDist(a.corners, b.corners); if (d < best) { best = d; pair = [a, b]; }
    }
    if (!pair) continue;
    const [a, b] = pair;
    // une table placée devant une banquette : contact voulu (assise côté banquette)
    const seated = (a.kind === 'table' && b.kind === 'banquette') || (b.kind === 'table' && a.kind === 'banquette');
    const at: P2 = [(centroid(a.corners)[0] + centroid(b.corners)[0]) / 2, (centroid(a.corners)[1] + centroid(b.corners)[1]) / 2];
    if (best === 0 && !seated) issues.push({ level: 'conflit', a: a.id, b: b.id, text: `${a.label} chevauche : ${b.label}`, at });
    else if (best > 0 && best < passage && !seated && !sameRow(a, b)) issues.push({ level: 'passage', a: a.id, b: b.id, gap: best, text: `Passage ${best.toFixed(2).replace('.', ',')} m : ${a.label} / ${b.label}`, at });
  }
  // une seule alerte par couple d'éléments (les branches d'un même ensemble sont regroupées)
  const grp = (id: string) => fp.find((x) => x.id === id)?.group ?? id;
  const seen = new Set<string>();
  return issues.filter((i) => { const k = `${i.level}|${grp(i.a)}|${grp(i.b)}`; if (seen.has(k)) return false; seen.add(k); return true; });
}
