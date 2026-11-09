import type { Furniture, Side } from '../types';

/** Implantation qui porte réellement les tables (une variante « basedOn » modifie sa base). */
export function editableLayout(f: Furniture, key: string): string {
  let k = key; const seen = new Set<string>();
  while (f.layouts[k] && !f.layouts[k].tables && f.layouts[k].basedOn && !seen.has(k)) { seen.add(k); k = f.layouts[k].basedOn!; }
  return k;
}

const snap = (v: number, step = 0.05) => Math.round(v / step) * step;
const r3 = (v: number) => Math.round(v * 1000) / 1000;

export function moveTable(f: Furniture, layout: string, id: string, x: number, y: number): Furniture {
  const n = structuredClone(f); const k = editableLayout(n, layout);
  const t = n.layouts[k].tables?.find((x) => x.id === id); if (!t) return f;
  t.x = r3(snap(x)); t.y = r3(snap(y));
  return n;
}

/** Rotation de +90° (sens horaire sur le plan) : la table et ses chaises tournent ensemble. */
export function rotateTable(f: Furniture, layout: string, id: string): Furniture {
  const n = structuredClone(f); const k = editableLayout(n, layout);
  const t = n.layouts[k].tables?.find((x) => x.id === id); if (!t) return f;
  t.rot = (t.rot + 90) % 360;
  const map: Record<Side, [Side, number]> = { E: ['S', -1], S: ['W', 1], W: ['N', -1], N: ['E', 1] };
  t.chairs = t.chairs.map(([side, off, c]) => [map[side][0], r3(off * map[side][1]), c]);
  return n;
}

export function moveIlot(f: Furniture, x: number, y: number): Furniture {
  const n = structuredClone(f); n.ilot.x = r3(snap(x)); n.ilot.y = r3(snap(y));
  return n;
}

export function downloadJSON(name: string, obj: unknown) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2) + '\n'], { type: 'application/json' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
