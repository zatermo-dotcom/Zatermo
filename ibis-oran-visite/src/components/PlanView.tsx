import { useMemo, useRef, useState, type MouseEvent, type PointerEvent } from 'react';
import type { P2, ProjectData } from '../types';
import type { CamState } from '../engine/Tour';
import { resolveTables } from '../engine/furniture';
import { footprints, type Issue } from '../engine/layoutCheck';

export type PlanMode = 'nav' | 'edit' | 'measure';
interface Props {
  data: ProjectData; layout: string; cam?: CamState; activeView: string | null;
  mode?: PlanMode; issues?: Issue[]; selected?: string | null;
  onZone: (camera: string) => void; onView: (id: string) => void; onMove?: (x: number, y: number) => void;
  onSelect?: (id: string | null) => void; onDrag?: (id: string, x: number, y: number) => void; onDragEnd?: () => void;
}

const pts = (p: P2[]) => p.map((q) => q.join(',')).join(' ');

/** Plan interactif généré depuis geometry.json / furniture.json (mêmes données que le modèle 3D). */
export function PlanView({ data, layout, cam, activeView, mode = 'nav', issues = [], selected, onZone, onView, onMove, onSelect, onDrag, onDragEnd }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const [measure, setMeasure] = useState<P2[]>([]);
  const [cursor, setCursor] = useState<P2 | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ id: string; dx: number; dy: number; moved: boolean } | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const g = data.geometry; const f = data.furniture;
  const tables = useMemo(() => resolveTables(f, layout), [f, layout]);
  const fps = useMemo(() => footprints(f, layout), [f, layout]);
  const t = g.wallThickness.value;
  const nav = mode === 'nav';

  const toPlan = (clientX: number, clientY: number): P2 | null => {
    const m = svgRef.current?.getScreenCTM(); if (!m) return null;
    const p = new DOMPoint(clientX, clientY).matrixTransform(m.inverse());
    return [p.x, p.y];
  };
  // un clic sur une zone est différé pour laisser la place au double-clic (déplacement au point)
  const zoneClick = (camera: string) => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => onZone(camera), 260); };
  const dbl = (e: MouseEvent<SVGSVGElement>) => {
    if (!nav) return; window.clearTimeout(timer.current);
    const p = toPlan(e.clientX, e.clientY); if (p && onMove) onMove(p[0], p[1]);
  };
  const click = (e: MouseEvent<SVGSVGElement>) => {
    if (mode !== 'measure') return;
    const p = toPlan(e.clientX, e.clientY); if (!p) return;
    const q: P2 = [Math.round(p[0] * 100) / 100, Math.round(p[1] * 100) / 100];
    setMeasure((m) => (m.length >= 2 ? [q] : [...m, q]));
  };
  const down = (id: string, cx: number, cy: number) => (e: PointerEvent<SVGElement>) => {
    if (mode !== 'edit') return;
    e.stopPropagation(); (e.target as Element).setPointerCapture(e.pointerId);
    const p = toPlan(e.clientX, e.clientY); if (!p) return;
    drag.current = { id, dx: p[0] - cx, dy: p[1] - cy, moved: false }; onSelect?.(id);
  };
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const p = toPlan(e.clientX, e.clientY);
    if (mode === 'measure') setCursor(p);
    const d = drag.current; if (!d || !p) return;
    d.moved = true; onDrag?.(d.id, p[0] - d.dx, p[1] - d.dy);
  };
  const up = () => { if (drag.current?.moved) onDragEnd?.(); drag.current = null; };

  const m0 = measure[0]; const m1 = measure[1] ?? (mode === 'measure' && measure.length === 1 ? cursor : null);
  const dist = m0 && m1 ? Math.hypot(m1[0] - m0[0], m1[1] - m0[1]) : 0;

  return (
    <svg ref={svgRef} onDoubleClick={dbl} onClick={click} onPointerMove={move} onPointerUp={up}
      className={`plan mode-${mode}`} viewBox="-0.9 -0.9 20.1 15.0" role="img" aria-label="Plan interactif du restaurant">
      <polygon points={pts(g.outline.points)} fill="none" stroke="#5b4c3d" strokeWidth={t * 2} strokeLinejoin="miter" />
      <polygon points={pts(g.outline.points)} fill="#f3ead8" stroke="none" />
      {g.openings.map((o) => (
        <line key={o.id} x1={o.a[0]} y1={o.a[1]} x2={o.b[0]} y2={o.b[1]} stroke={o.type === 'acces' ? '#f3ead8' : '#7fb0cf'} strokeWidth={t * 2.05}>
          <title>{`${o.label} – ${o.status}`}</title>
        </line>
      ))}
      {data.ceiling.gorges.map((gg) => (
        <rect key={gg.id} x={gg.x0} y={gg.y0} width={gg.x1 - gg.x0} height={gg.y1 - gg.y0} fill="none" stroke="#1d1b1a" strokeOpacity={0.45} strokeWidth={0.12} />
      ))}
      {data.ceiling.rosaces.items.map((r) => <circle key={r.id} cx={r.x} cy={r.y} r={0.22} fill="none" stroke="#b08a3e" strokeWidth={0.05} />)}
      <rect x={g.poteau.x} y={g.poteau.y} width={g.poteau.w} height={g.poteau.d} fill="#5b4c3d" />
      <rect x={g.jambeAcces.x} y={g.jambeAcces.y} width={g.jambeAcces.w} height={g.jambeAcces.d} fill="#5b4c3d" />
      {/* mobilier : emprises issues du contrôle d'implantation */}
      {fps.filter((x) => x.kind === 'banquette').map((x) => <polygon key={x.id} points={pts(x.corners)} fill="#6e1423" opacity={0.85}><title>{x.label}</title></polygon>)}
      {fps.filter((x) => x.kind === 'buffet').map((x) => <polygon key={x.id} points={pts(x.corners)} fill="#d8c8a6" stroke="#9a835a" strokeWidth={0.03}><title>{x.label}</title></polygon>)}
      {fps.filter((x) => x.kind === 'chaise').map((x) => {
        const color = x.label && tables.find((tb) => x.group === tb.id)?.chairs[Number(x.id.split('.c')[1]) - 1]?.[2];
        return <polygon key={x.id} points={pts(x.corners)} fill={data.furniture.chairColors[color ?? 'ivoire']} stroke="#8a7a62" strokeWidth={0.015} className={selected === x.group ? 'sel' : ''} />;
      })}
      {fps.filter((x) => x.kind === 'table' || x.kind === 'ilot').map((x) => {
        const c = x.corners.reduce((s, p) => [s[0] + p[0] / 4, s[1] + p[1] / 4], [0, 0]);
        return (
          <g key={x.id}>
            <polygon points={pts(x.corners)} fill="#fffaf0" stroke={selected === x.group ? '#1f78c8' : '#9a835a'} strokeWidth={selected === x.group ? 0.06 : 0.03}
              className={mode === 'edit' ? 'draggable' : ''} onPointerDown={down(x.group, c[0], c[1])}>
              <title>{x.label}</title>
            </polygon>
            {mode === 'edit' && <text x={c[0]} y={c[1] + 0.12} className="tid">{x.id === 'ILOT' ? 'îlot' : x.id}</text>}
          </g>
        );
      })}
      {/* zones cliquables (navigation) */}
      {g.zones.map((z) => (
        <polygon key={z.id} points={pts(z.polygon)} style={{ pointerEvents: nav ? 'auto' : 'none' }}
          className={`zone ${hover === z.id ? 'hover' : ''}`}
          onMouseEnter={() => setHover(z.id)} onMouseLeave={() => setHover(null)}
          onClick={() => zoneClick(z.camera)} tabIndex={nav ? 0 : -1} role="button" aria-label={`Aller à : ${z.label}`}
          onKeyDown={(e) => { if (e.key === 'Enter') onZone(z.camera); }}>
          <title>{z.label}</title>
        </polygon>
      ))}
      {nav && g.zones.map((z) => {
        const cx = z.polygon.reduce((s, p) => s + p[0], 0) / z.polygon.length; const cy = z.polygon.reduce((s, p) => s + p[1], 0) / z.polygon.length;
        return <text key={z.id} x={cx} y={cy + (z.id === 'salle' ? 0.9 : 0)} className="zone-label">{z.label}</text>;
      })}
      {nav && data.cameras.views.filter((v) => v.pos[2] < 4).map((v) => {
        const dx = v.target[0] - v.pos[0]; const dy = v.target[1] - v.pos[1]; const l = Math.hypot(dx, dy) || 1;
        return (
          <g key={v.id} className={`viewpoint ${activeView === v.id ? 'active' : ''}`} onClick={() => onView(v.id)} role="button" aria-label={v.label}>
            <line x1={v.pos[0]} y1={v.pos[1]} x2={v.pos[0] + (dx / l) * 0.8} y2={v.pos[1] + (dy / l) * 0.8} />
            <circle cx={v.pos[0]} cy={v.pos[1]} r={0.22} />
            <title>{v.label}</title>
          </g>
        );
      })}
      {/* alertes du contrôle d'implantation */}
      {issues.map((i, k) => (
        <circle key={k} cx={i.at[0]} cy={i.at[1]} r={0.18} className={`issue ${i.level}`}><title>{i.text}</title></circle>
      ))}
      {cam && !cam.overview && nav && (
        <g transform={`translate(${cam.x} ${cam.y}) rotate(${(cam.yaw * 180) / Math.PI})`} className="me">
          <path d="M0 0 L1.6 -0.75 A1.8 1.8 0 0 1 1.6 0.75 Z" />
          <circle r={0.2} />
        </g>
      )}
      {/* mesure */}
      {m0 && <circle cx={m0[0]} cy={m0[1]} r={0.08} className="mpt" />}
      {m0 && m1 && (
        <g className="measure">
          <line x1={m0[0]} y1={m0[1]} x2={m1[0]} y2={m1[1]} />
          <circle cx={m1[0]} cy={m1[1]} r={0.08} className="mpt" />
          <text x={(m0[0] + m1[0]) / 2} y={(m0[1] + m1[1]) / 2 - 0.2}>{dist.toFixed(2).replace('.', ',')} m</text>
        </g>
      )}
      <g className="dim">
        <line x1={0} y1={14.0} x2={18.3} y2={14.0} /><text x={9.15} y={14.45}>18,30 m (coté)</text>
        <line x1={19.0} y1={0} x2={19.0} y2={12.8} /><text x={19.35} y={6.4} transform="rotate(90 19.35 6.4)">12,80 m (coté)</text>
      </g>
    </svg>
  );
}
