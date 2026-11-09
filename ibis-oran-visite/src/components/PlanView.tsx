import { useMemo, useRef, useState, type MouseEvent } from 'react';
import type { ProjectData } from '../types';
import type { CamState } from '../engine/Tour';
import { resolveTables } from '../engine/furniture';

interface Props { data: ProjectData; layout: string; cam?: CamState; activeView: string | null; onZone: (camera: string) => void; onView: (id: string) => void; onMove?: (x: number, y: number) => void }

/** Plan interactif généré depuis geometry.json / furniture.json (mêmes données que le modèle 3D). */
export function PlanView({ data, layout, cam, activeView, onZone, onView, onMove }: Props) {
  // un clic sur une zone est différé pour laisser la place au double-clic (déplacement au point)
  const timer = useRef<number | undefined>(undefined);
  const zoneClick = (camera: string) => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => onZone(camera), 260); };
  const dbl = (e: MouseEvent<SVGSVGElement>) => {
    window.clearTimeout(timer.current);
    const svg = e.currentTarget; const m = svg.getScreenCTM(); if (!m || !onMove) return;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    onMove(p.x, p.y);
  };
  const [hover, setHover] = useState<string | null>(null);
  const g = data.geometry; const f = data.furniture;
  const pts = g.outline.points.map((p) => p.join(',')).join(' ');
  const tables = useMemo(() => resolveTables(f, layout), [f, layout]);
  const t = g.wallThickness.value;
  return (
    <svg onDoubleClick={dbl} className="plan" viewBox={`${-0.9} ${-0.9} ${20.1} ${15.0}`} role="img" aria-label="Plan interactif du restaurant">
      <defs>
        <pattern id="hatch" width="0.2" height="0.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="0.2" stroke="#8a7a62" strokeWidth="0.04" />
        </pattern>
      </defs>
      {/* murs : contour épaissi vers l'extérieur */}
      <polygon points={pts} fill="none" stroke="#5b4c3d" strokeWidth={t * 2} strokeLinejoin="miter" />
      <polygon points={pts} fill="#f3ead8" stroke="none" />
      {/* baies */}
      {g.openings.map((o) => (
        <line key={o.id} x1={o.a[0]} y1={o.a[1]} x2={o.b[0]} y2={o.b[1]} stroke={o.type === 'acces' ? '#f3ead8' : '#7fb0cf'} strokeWidth={t * 2.05}>
          <title>{`${o.label} – ${o.status}`}</title>
        </line>
      ))}
      {/* caissons et cadres de sol */}
      {data.ceiling.gorges.map((gg) => (
        <rect key={gg.id} x={gg.x0} y={gg.y0} width={gg.x1 - gg.x0} height={gg.y1 - gg.y0} fill="none" stroke="#1d1b1a" strokeOpacity={0.55} strokeWidth={0.12} />
      ))}
      {data.ceiling.rosaces.items.map((r) => <circle key={r.id} cx={r.x} cy={r.y} r={0.22} fill="none" stroke="#b08a3e" strokeWidth={0.05} />)}
      <rect x={g.poteau.x} y={g.poteau.y} width={g.poteau.w} height={g.poteau.d} fill="#5b4c3d" />
      <rect x={g.jambeAcces.x} y={g.jambeAcces.y} width={g.jambeAcces.w} height={g.jambeAcces.d} fill="#5b4c3d" />
      {/* mobilier */}
      {f.banquettes.flatMap((b) => b.branches.map((br, i) => {
        const x0 = Math.min(br.a[0], br.b[0], br.a[0] + br.n[0] * 0.65); const x1 = Math.max(br.a[0], br.b[0], br.a[0] + br.n[0] * 0.65);
        const y0 = Math.min(br.a[1], br.b[1], br.a[1] + br.n[1] * 0.65); const y1 = Math.max(br.a[1], br.b[1], br.a[1] + br.n[1] * 0.65);
        return <rect key={`${b.id}${i}`} x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="#6e1423" opacity={0.85}><title>{b.id}</title></rect>;
      }))}
      {f.buffets.flatMap((b) => b.branches.map((br, i) => {
        const d = b.depth;
        const x0 = Math.min(br.a[0], br.b[0], br.a[0] + br.n[0] * d); const x1 = Math.max(br.a[0], br.b[0], br.a[0] + br.n[0] * d);
        const y0 = Math.min(br.a[1], br.b[1], br.a[1] + br.n[1] * d); const y1 = Math.max(br.a[1], br.b[1], br.a[1] + br.n[1] * d);
        return <rect key={`${b.id}${i}`} x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="#d8c8a6" stroke="#9a835a" strokeWidth={0.03}><title>{b.id}</title></rect>;
      }))}
      <rect x={f.ilot.x - f.specs.ilot.w / 2} y={f.ilot.y - f.specs.ilot.d / 2} width={f.specs.ilot.w} height={f.specs.ilot.d} fill="#d8c8a6" stroke="#9a835a" strokeWidth={0.03}><title>Îlot central</title></rect>
      {tables.map((tb) => {
        const s = tb.type === 'rect' ? f.specs.tableRect : f.specs.tableCarree;
        const w = Math.abs(Math.cos((tb.rot * Math.PI) / 180)) > 0.5 ? s.w : s.d; const h = w === s.w ? s.d : s.w;
        return <rect key={tb.id} x={tb.x - w / 2} y={tb.y - h / 2} width={w} height={h} fill="#fffaf0" stroke="#9a835a" strokeWidth={0.03}><title>{tb.id}</title></rect>;
      })}
      {/* zones cliquables */}
      {g.zones.map((z) => (
        <polygon key={z.id} points={z.polygon.map((p) => p.join(',')).join(' ')}
          className={`zone ${hover === z.id ? 'hover' : ''}`}
          onMouseEnter={() => setHover(z.id)} onMouseLeave={() => setHover(null)}
          onClick={() => zoneClick(z.camera)} tabIndex={0} role="button" aria-label={`Aller à : ${z.label}`}
          onKeyDown={(e) => { if (e.key === 'Enter') onZone(z.camera); }}>
          <title>{z.label}</title>
        </polygon>
      ))}
      {g.zones.map((z) => {
        const cx = z.polygon.reduce((s, p) => s + p[0], 0) / z.polygon.length; const cy = z.polygon.reduce((s, p) => s + p[1], 0) / z.polygon.length;
        return <text key={z.id} x={cx} y={cy + (z.id === 'salle' ? 0.9 : 0)} className="zone-label">{z.label}</text>;
      })}
      {/* points de vue */}
      {data.cameras.views.filter((v) => v.pos[2] < 4).map((v) => {
        const dx = v.target[0] - v.pos[0]; const dy = v.target[1] - v.pos[1]; const l = Math.hypot(dx, dy) || 1;
        return (
          <g key={v.id} className={`viewpoint ${activeView === v.id ? 'active' : ''}`} onClick={() => onView(v.id)} role="button" aria-label={v.label}>
            <line x1={v.pos[0]} y1={v.pos[1]} x2={v.pos[0] + (dx / l) * 0.8} y2={v.pos[1] + (dy / l) * 0.8} />
            <circle cx={v.pos[0]} cy={v.pos[1]} r={0.22} />
            <title>{v.label}</title>
          </g>
        );
      })}
      {/* caméra courante */}
      {cam && !cam.overview && (
        <g transform={`translate(${cam.x} ${cam.y}) rotate(${(cam.yaw * 180) / Math.PI})`} className="me">
          <path d="M0 0 L1.6 -0.75 A1.8 1.8 0 0 1 1.6 0.75 Z" />
          <circle r={0.2} />
        </g>
      )}
      {/* cotes de contrôle */}
      <g className="dim">
        <line x1={0} y1={14.0} x2={18.3} y2={14.0} /><text x={9.15} y={14.45}>18,30 m (coté)</text>
        <line x1={19.0} y1={0} x2={19.0} y2={12.8} /><text x={19.35} y={6.4} transform="rotate(90 19.35 6.4)">12,80 m (coté)</text>
      </g>
    </svg>
  );
}
