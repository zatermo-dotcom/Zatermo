import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Options, ProjectData, RenderItem } from './types';
import { loadProjectData } from './data';
import { Tour, type CamState, type ModelStats } from './engine/Tour';
import { polygonArea } from './engine/util';
import { PlanView } from './components/PlanView';
import { Gallery, SettingsPanel, SourcesPanel } from './components/Panels';

type Tab = 'vues' | 'plan' | 'rendus' | 'sources' | 'reglages';
interface Lightbox { file: string; title: string; page: number; note?: string; camera?: string; list?: RenderItem[]; index?: number }

const DEFAULT_OPTIONS: Options = { layout: 'amenagement-02', floor: 'sol-A', lustre: 'abat-jour', showCeiling: true, showFurniture: true, quality: 'standard', bloom: true };

declare global { interface Window { __tour?: Tour } }

export default function App() {
  const host = useRef<HTMLDivElement>(null);
  const tour = useRef<Tour | undefined>(undefined);
  const [data, setData] = useState<ProjectData>();
  const [error, setError] = useState<string>();
  const [options, setOptions] = useState<Options>(() => {
    const q = new URLSearchParams(location.search);
    return { ...DEFAULT_OPTIONS, ...(q.get('qualite') === 'elevee' ? { quality: 'elevee' } : {}) };
  });
  const [tab, setTab] = useState<Tab>('plan');
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth > 760);
  const [presentation, setPresentation] = useState(false);
  const [cam, setCam] = useState<CamState>();
  const [activeView, setActiveView] = useState<string | null>('vue-generale');
  const [stats, setStats] = useState<ModelStats>();
  const [lightbox, setLightbox] = useState<Lightbox | null>(null);
  const [toast, setToast] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [help, setHelp] = useState(false);

  const flash = (m: string) => { setToast(m); window.setTimeout(() => setToast(undefined), 2600); };

  useEffect(() => { loadProjectData().then(setData).catch((e: Error) => setError(e.message)); }, []);

  useEffect(() => {
    if (!data || !host.current || tour.current) return;
    try {
      const t = new Tour(host.current, data, options);
      tour.current = t; window.__tour = t;
      t.onCamera = setCam; t.onView = setActiveView;
      setStats(t.stats);
      const start = new URLSearchParams(location.search).get('vue') ?? 'vue-generale';
      t.goTo(start, true);
    } catch (e) { setError(`WebGL indisponible : ${(e as Error).message}`); }
    return () => { /* conservé pendant la session */ };
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => { tour.current?.dispose(); tour.current = undefined; }, []);

  const go = useCallback((id: string) => { tour.current?.goTo(id); setLightbox(null); if (window.innerWidth <= 760) setPanelOpen(false); }, []);
  const change = (o: Partial<Options>) => { const n = { ...options, ...o }; setOptions(n); tour.current?.setOptions(o); setStats(tour.current?.stats); };

  const reload = async () => {
    setBusy(true);
    try { const d = await loadProjectData(); setData(d); tour.current?.rebuild(d, options); setStats(tour.current?.stats); flash('Données rechargées'); }
    catch (e) { flash((e as Error).message); } finally { setBusy(false); }
  };
  const exportGLB = async () => {
    if (!tour.current) return; setBusy(true);
    try {
      const buf = await tour.current.exportGLB();
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([buf], { type: 'model/gltf-binary' }));
      a.download = `restaurant-ibis-oran_${options.layout}_${options.floor}.glb`; a.click(); URL.revokeObjectURL(a.href);
      flash(`GLB exporté (${(buf.byteLength / 1e6).toFixed(1)} Mo)`);
    } finally { setBusy(false); }
  };
  const copyView = async () => {
    const j = tour.current?.currentViewJSON(); if (!j) return;
    try { await navigator.clipboard.writeText(j); flash('Vue copiée : collez-la dans data/cameras.json'); } catch { window.prompt('Vue courante (à coller dans cameras.json) :', j); }
  };
  const fullscreen = async () => {
    const on = !document.fullscreenElement;
    try { if (on) await document.documentElement.requestFullscreen(); else await document.exitFullscreen(); } catch { /* iOS : mode présentation seul */ }
    setPresentation(on); if (on) setPanelOpen(false);
  };
  useEffect(() => {
    const f = () => { if (!document.fullscreenElement) setPresentation(false); };
    document.addEventListener('fullscreenchange', f); return () => document.removeEventListener('fullscreenchange', f);
  }, []);

  const area = useMemo(() => data ? polygonArea(data.geometry.outline.points) - data.geometry.poteau.w * data.geometry.poteau.d : 0, [data]);
  const view = data?.cameras.views.find((v) => v.id === activeView);
  const related = useMemo(() => (data && activeView ? data.renders.items.filter((r) => r.camera === activeView) : []), [data, activeView]);

  const openRender = (r: RenderItem, list?: RenderItem[]) => {
    const l = list ?? data?.renders.items ?? [];
    setLightbox({ file: r.file, title: r.title, page: r.page, note: r.note, camera: r.camera, list: l, index: l.findIndex((x) => x.id === r.id) });
  };
  const stepLightbox = (d: number) => {
    if (!lightbox?.list || lightbox.index === undefined) return;
    const i = (lightbox.index + d + lightbox.list.length) % lightbox.list.length; openRender(lightbox.list[i], lightbox.list);
  };

  // marche continue tant qu'un bouton tactile est maintenu
  const hold = useRef<number | undefined>(undefined);
  const startHold = (fn: () => void) => { fn(); hold.current = window.setInterval(fn, 30); };
  const stopHold = () => { window.clearInterval(hold.current); };

  if (error) return <div className="fatal"><h1>Visite indisponible</h1><p>{error}</p></div>;

  const groups = data ? Array.from(new Set(data.cameras.views.map((v) => v.group))) : [];
  const base = import.meta.env.BASE_URL;

  return (
    <div className={`app ${presentation ? 'presentation' : ''}`}>
      <div className="viewport" ref={host} />
      {!data && <div className="loading">Chargement du modèle…</div>}

      <header className="brand">
        <div className="title">Restaurant ibis · Oran</div>
        <div className="subtitle">Visite 3D — d'après le portfolio ILK (161,68 m²)</div>
      </header>

      <div className="topbar">
        <button className="btn icon" onClick={() => setHelp((h) => !h)} aria-label="Aide aux commandes">?</button>
        <button className="btn" onClick={fullscreen}>{presentation ? 'Quitter la présentation' : 'Plein écran'}</button>
        {!presentation && <button className="btn" onClick={() => setPanelOpen((o) => !o)}>{panelOpen ? 'Masquer le panneau' : 'Panneau'}</button>}
      </div>

      {data && !presentation && panelOpen && (
        <aside className="panel">
          <nav className="tabs" role="tablist">
            {([['plan', 'Plan'], ['vues', 'Vues'], ['rendus', 'Rendus'], ['sources', 'Sources'], ['reglages', 'Réglages']] as [Tab, string][]).map(([k, l]) => (
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
            ))}
          </nav>
          <div className="panel-body">
            {tab === 'plan' && (
              <>
                <p className="hint">Cliquez une zone ou un point de vue pour y déplacer la caméra. Le plan est tracé à partir des mêmes données que le modèle.</p>
                <PlanView data={data} layout={options.layout} cam={cam} activeView={activeView} onZone={go} onView={go} />
                <div className="legend"><span className="lg wall" />murs <span className="lg win" />baies <span className="lg ban" />banquettes <span className="lg buf" />buffets <span className="lg frame" />cadres sol/plafond</div>
              </>
            )}
            {tab === 'vues' && groups.map((gr) => (
              <div key={gr} className="viewgroup">
                <h4>{gr}</h4>
                {data.cameras.views.filter((v) => v.group === gr).map((v) => (
                  <button key={v.id} className={`viewbtn ${activeView === v.id ? 'on' : ''}`} onClick={() => go(v.id)}>
                    <span>{v.label}</span><span className="pages">p. {v.pages.join(', ')}</span>
                  </button>
                ))}
              </div>
            ))}
            {tab === 'rendus' && <Gallery data={data} onOpen={(r) => openRender(r)} onOpenPlan={(file, title, page) => setLightbox({ file, title, page })} />}
            {tab === 'sources' && <SourcesPanel data={data} area={area} />}
            {tab === 'reglages' && <SettingsPanel data={data} options={options} stats={stats} busy={busy} onChange={change} onReload={reload} onExport={exportGLB} onCopyView={copyView} />}
          </div>
        </aside>
      )}

      {data && (
        <nav className="viewbar" aria-label="Positions de caméra">
          {['vue-generale', 'salle-ensemble', 'plafond', 'banquettes-alcove', 'buffet-central', 'buffets-peripheriques', 'acces'].map((id) => {
            const v = data.cameras.views.find((x) => x.id === id); if (!v) return null;
            return <button key={id} className={activeView === id ? 'on' : ''} onClick={() => go(id)}>{v.label}</button>;
          })}
        </nav>
      )}

      {data && view && related.length > 0 && !lightbox && (
        <div className="related">
          <span>Rendus de référence pour « {view.label} » :</span>
          {related.map((r) => (
            <button key={r.id} onClick={() => openRender(r, related)} title={r.title}>
              <img src={`${base}${r.file}`} alt="" /><em>p.{r.page}</em>
            </button>
          ))}
        </div>
      )}

      {data && cam && !cam.overview && (
        <div className="walkpad" aria-label="Déplacement">
          <button onPointerDown={() => startHold(() => tour.current?.walk(0.05))} onPointerUp={stopHold} onPointerLeave={stopHold} aria-label="Avancer">▲</button>
          <div>
            <button onPointerDown={() => startHold(() => tour.current?.turn(0.02))} onPointerUp={stopHold} onPointerLeave={stopHold} aria-label="Tourner à gauche">◀</button>
            <button onPointerDown={() => startHold(() => tour.current?.walk(-0.05))} onPointerUp={stopHold} onPointerLeave={stopHold} aria-label="Reculer">▼</button>
            <button onPointerDown={() => startHold(() => tour.current?.turn(-0.02))} onPointerUp={stopHold} onPointerLeave={stopHold} aria-label="Tourner à droite">▶</button>
          </div>
        </div>
      )}

      {help && (
        <div className="help" onClick={() => setHelp(false)}>
          <h3>Commandes</h3>
          <ul>
            <li><b>Glisser</b> (souris ou doigt) : regarder autour / tourner autour du plan</li>
            <li><b>Double-clic / double-tap au sol</b> : se déplacer à cet endroit</li>
            <li><b>Molette</b>, <b>flèches</b>, <b>Z/Q/S/D</b> ou pavé ▲▼ : avancer, reculer, tourner</li>
            <li>Vue générale : molette / pincer = zoom, clic droit ou deux doigts = déplacer</li>
            <li><b>Plan</b> : cliquer une zone ou un point de vue</li>
            <li><b>Rendus</b> : images de référence du PDF, avec retour au modèle</li>
          </ul>
          <p className="hint">Cliquer pour fermer</p>
        </div>
      )}

      {lightbox && (
        <div className="lightbox" role="dialog" aria-modal="true" aria-label={lightbox.title} onKeyDown={(e) => { if (e.key === 'Escape') setLightbox(null); }}>
          <div className="lb-head">
            <div>
              <span className="badge st-ref">Image de référence du PDF — p.{lightbox.page}</span>
              <h3>{lightbox.title}</h3>
              {lightbox.note && <p className="note">{lightbox.note}</p>}
            </div>
            <div className="row">
              {lightbox.camera && <button className="btn primary" onClick={() => go(lightbox.camera!)}>Voir la position dans le modèle 3D</button>}
              <button className="btn" onClick={() => setLightbox(null)} autoFocus>Retour au modèle</button>
            </div>
          </div>
          <div className="lb-img">
            {lightbox.list && lightbox.list.length > 1 && <button className="lb-nav" onClick={() => stepLightbox(-1)} aria-label="Précédent">‹</button>}
            <img src={`${base}${lightbox.file}`} alt={lightbox.title} />
            {lightbox.list && lightbox.list.length > 1 && <button className="lb-nav" onClick={() => stepLightbox(1)} aria-label="Suivant">›</button>}
          </div>
          <p className="hint center">Rendu fixe fourni dans le dossier : il n'est ni un panorama ni une vue calculée du modèle ; certaines images montrent des variantes non retenues.</p>
        </div>
      )}

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
