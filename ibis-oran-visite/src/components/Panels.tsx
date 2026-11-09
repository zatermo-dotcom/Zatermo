import { useMemo, useState } from 'react';
import type { Options, ProjectData, RenderItem, Status } from '../types';
import type { ModelStats } from '../engine/Tour';

export const statusClass = (s: Status) =>
  s.startsWith('coté') ? 'st-cote' : s.startsWith('déduit') ? 'st-deduit' : s.startsWith('proposé') ? 'st-propose' : 'st-confirmer';

export function StatusBadge({ s }: { s: Status }) { return <span className={`badge ${statusClass(s)}`}>{s}</span>; }

export function Pages({ pages }: { pages: number[] }) {
  return <span className="pages">{pages.length ? `p. ${pages.join(', ')}` : '—'}</span>;
}

const ZONES: [string, string][] = [['tous', 'Tous'], ['salle', 'Salle'], ['self', 'Buffet'], ['plafond', 'Plafond'], ['acces', 'Accès'], ['mobilier', 'Mobilier'], ['plan', 'Plans illustrés']];

export function Gallery({ data, onOpen, onOpenPlan }: { data: ProjectData; onOpen: (r: RenderItem) => void; onOpenPlan: (file: string, title: string, page: number) => void }) {
  const [zone, setZone] = useState('tous');
  const items = data.renders.items.filter((r) => zone === 'tous' || r.zone === zone);
  const base = import.meta.env.BASE_URL;
  return (
    <div>
      <p className="hint">Rendus extraits du PDF : images de référence d'ambiance, associées à une position de caméra. Ce ne sont pas des vues 3D.</p>
      <div className="chips">{ZONES.map(([k, l]) => <button key={k} className={`chip ${zone === k ? 'on' : ''}`} onClick={() => setZone(k)}>{l}</button>)}</div>
      <div className="thumbs">
        {items.map((r) => (
          <button key={r.id} className="thumb" onClick={() => onOpen(r)} title={r.title}>
            <img src={`${base}${r.file}`} alt={r.title} loading="lazy" />
            <span>p.{r.page} · {r.title}</span>
          </button>
        ))}
      </div>
      <h4>Planches techniques (géométrie)</h4>
      <ul className="planlist">
        {data.renders.plans.map((p) => <li key={p.file}><button className="link" onClick={() => onOpenPlan(p.file, p.title, p.page)}>p.{p.page} — {p.title}</button></li>)}
      </ul>
    </div>
  );
}

export function SourcesPanel({ data, area }: { data: ProjectData; area: number }) {
  const [filter, setFilter] = useState('tous');
  const [tab, setTab] = useState<'sources' | 'index'>('sources');
  const rows = data.sources.items.filter((s) => filter === 'tous' || statusClass(s.status) === filter);
  return (
    <div>
      <div className="chips">
        <button className={`chip ${tab === 'sources' ? 'on' : ''}`} onClick={() => setTab('sources')}>Sources et hypothèses</button>
        <button className={`chip ${tab === 'index' ? 'on' : ''}`} onClick={() => setTab('index')}>Correspondance des 109 pages</button>
      </div>
      {tab === 'sources' ? (
        <>
          <p className="hint">Surface du contour modélisé (hors poteau) : <b>{area.toFixed(2)} m²</b> — surface inscrite au plan : <b>161,68 m²</b>.</p>
          <div className="chips small">
            {[['tous', 'Tous'], ['st-cote', 'Coté'], ['st-deduit', 'Déduit'], ['st-propose', 'Proposé'], ['st-confirmer', 'À confirmer']].map(([k, l]) => (
              <button key={k} className={`chip ${filter === k ? 'on' : ''}`} onClick={() => setFilter(k)}>{l}</button>
            ))}
          </div>
          <table className="src">
            <thead><tr><th>Élément</th><th>Valeur retenue</th><th>Pages</th><th>Statut</th></tr></thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.element}>
                  <td>{s.element}<div className="file">{s.file}</div></td>
                  <td>{s.value}{s.note && <div className="note">{s.note}</div>}</td>
                  <td><Pages pages={s.pages} /></td>
                  <td><StatusBadge s={s.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <table className="src">
          <thead><tr><th>Pages</th><th>Type</th><th>Contenu</th><th>Usage dans le modèle</th></tr></thead>
          <tbody>{data.pdfIndex.rows.map((r) => <tr key={r.pages}><td className="nowrap">{r.pages}</td><td>{r.category}</td><td>{r.content}</td><td>{r.usage}</td></tr>)}</tbody>
        </table>
      )}
    </div>
  );
}

interface SettingsProps {
  data: ProjectData; options: Options; stats?: ModelStats; busy: boolean;
  onChange: (o: Partial<Options>) => void; onReload: () => void; onExport: () => void; onCopyView: () => void;
}
export function SettingsPanel({ data, options, stats, busy, onChange, onReload, onExport, onCopyView }: SettingsProps) {
  const checks = useMemo(() => {
    if (!stats) return [];
    const c = stats.chairs;
    const main = options.layout === 'amenagement-02';
    return [
      ['Tables', `${stats.tables} (${stats.rect} rect. + ${stats.carree} carrées)`, !main || (stats.tables === 15 && stats.rect === 10 && stats.carree === 5)],
      ['Chaises', `${Object.values(c).reduce((a, b) => a + b, 0)} (${c.ivoire ?? 0} ivoire, ${c.bordeaux ?? 0} bordeaux, ${c.noir ?? 0} noires)`, !main || (c.ivoire === 26 && c.bordeaux === 10 && c.noir === 4)],
      ['Banquettes', `${stats.banquettes} ensembles (${stats.banquettesL} en L)`, stats.banquettes === 6 && stats.banquettesL === 3],
      ['Buffets périphériques', `${stats.buffets}`, stats.buffets === 2],
      ['Îlot – portes', `${stats.ilotPortes}`, stats.ilotPortes === 0],
      ['Lustres / appliques / spots', `${stats.lustres} / ${stats.appliques} / ${stats.spots}`, stats.lustres === 7 && stats.appliques === 19 && stats.spots === 30],
      ['Faces murales / caissons', `${stats.faces} / ${stats.gorges}`, stats.faces === 26 && stats.gorges === 6],
    ] as [string, string, boolean][];
  }, [stats, options.layout]);
  const f = data.furniture; const m = data.materials;
  return (
    <div className="settings">
      <label>Implantation du mobilier
        <select value={options.layout} onChange={(e) => onChange({ layout: e.target.value })}>
          {Object.entries(f.layouts).map(([k, l]) => <option key={k} value={k}>{l.label}</option>)}
        </select>
      </label>
      <label>Finition du sol
        <select value={options.floor} onChange={(e) => onChange({ floor: e.target.value })}>
          {Object.entries(m.floorVariants).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </label>
      <label>Lustres
        <select value={options.lustre} onChange={(e) => onChange({ lustre: e.target.value })}>
          {Object.entries(m.lustreVariants).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </label>
      <label>Qualité d'éclairage
        <select value={options.quality} onChange={(e) => onChange({ quality: e.target.value as Options['quality'] })}>
          <option value="standard">Standard (7 sources – mobiles)</option>
          <option value="elevee">Élevée (7 + 19 appliques)</option>
        </select>
      </label>
      <div className="toggles">
        <label><input type="checkbox" checked={options.showCeiling} onChange={(e) => onChange({ showCeiling: e.target.checked })} /> Plafond</label>
        <label><input type="checkbox" checked={options.showFurniture} onChange={(e) => onChange({ showFurniture: e.target.checked })} /> Mobilier</label>
        <label><input type="checkbox" checked={options.bloom} onChange={(e) => onChange({ bloom: e.target.checked })} /> Halo lumineux</label>
      </div>
      <h4>Contrôle des quantités (modèle courant)</h4>
      <table className="src checks"><tbody>
        {checks.map(([k, v, ok]) => <tr key={k}><td>{k}</td><td>{v}</td><td>{ok ? '✔' : '✖'}</td></tr>)}
      </tbody></table>
      <h4>Bureau d'études</h4>
      <p className="hint">Toutes les valeurs sont dans <code>public/data/*.json</code> (géométrie, murs, plafond, éclairage, mobilier, matériaux, caméras). Après modification, recharger :</p>
      <div className="row">
        <button className="btn" onClick={onReload} disabled={busy}>Recharger les données</button>
        <button className="btn" onClick={onExport} disabled={busy}>Exporter le GLB</button>
        <button className="btn" onClick={onCopyView}>Copier la vue (JSON)</button>
      </div>
    </div>
  );
}
