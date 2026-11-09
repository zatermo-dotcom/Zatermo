import type { ProjectData } from './types';

const FILES = ['geometry', 'walls', 'ceiling', 'lighting', 'furniture', 'materials', 'cameras', 'renders', 'sources', 'pdf-index'] as const;

/** Charge les JSON éditables de public/data (sans cache, pour recharger après correction). */
export async function loadProjectData(): Promise<ProjectData> {
  const base = import.meta.env.BASE_URL;
  const entries = await Promise.all(FILES.map(async (f) => {
    const res = await fetch(`${base}data/${f}.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Impossible de charger data/${f}.json (${res.status})`);
    try { return [f, await res.json()] as const; }
    catch (e) { throw new Error(`JSON invalide dans data/${f}.json : ${(e as Error).message}`); }
  }));
  const d = Object.fromEntries(entries) as Record<string, unknown>;
  return {
    geometry: d.geometry, walls: d.walls, ceiling: d.ceiling, lighting: d.lighting, furniture: d.furniture,
    materials: d.materials, cameras: d.cameras, renders: d.renders, sources: d.sources, pdfIndex: d['pdf-index'],
  } as ProjectData;
}
