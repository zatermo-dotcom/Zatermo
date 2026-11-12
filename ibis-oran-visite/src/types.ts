export type Status = 'coté' | 'déduit' | 'proposé' | 'à confirmer' | string;
export type P2 = [number, number];

export interface Opening {
  id: string; type: 'porte-fenetre' | 'fixe' | 'porte' | 'acces'; label: string;
  a: P2; b: P2; height: number; sill?: number; leaves?: number; status: Status; pages: number[];
}
export interface Zone { id: string; label: string; camera: string; polygon: P2[]; pages: number[] }
export interface Geometry {
  outline: { points: P2[] };
  wallThickness: { value: number };
  heights: Record<string, { value: number; status: Status; note?: string; pages: number[] }>;
  poteau: { x: number; y: number; w: number; d: number };
  jambeAcces: { x: number; y: number; w: number; d: number };
  openings: Opening[];
  zones: Zone[];
}
export interface WallFace { id: string; label: string; a: P2; b: P2; n: P2; frames: number[]; status: Status; page: number }
export interface Walls {
  profiles: {
    cadre01: { width: number; depth: number }; cadre02: { width: number; depth: number; offset: number };
    cimaise03: { width: number; depth: number }; frameHeight01: number; frameHeight02: number;
  };
  faces: WallFace[];
}
export interface Gorge { id: string; x0: number; y0: number; x1: number; y1: number; led: number }
export interface Ceiling {
  gorge: { saillieP: number; ouvertureO: number; reculR: number; ledInset: number };
  corniche: { height: number; projection: number };
  gorges: Gorge[];
  rosaces: { diameter: number; items: { id: string; x: number; y: number }[] };
}
export interface Lighting {
  ambiance: { ambient: number; hemiSky: string; hemiGround: string; hemi: number; exposure: number; bloom: number };
  lustre: { dropBottom: number; diameter: number; intensity: number; distance: number; color: string };
  applique: { height: number; intensity: number; distance: number; color: string; items: { id: string; x: number; y: number; support: string }[] };
  spot: { diameter: number; color: string; items: [string, number, number][] };
  gorgeLed: { color: string; intensity: number };
}
export type Side = 'N' | 'S' | 'E' | 'W';
export interface TableDef { id: string; type: 'rect' | 'carree'; x: number; y: number; rot: number; chairs: [Side, number, string][] }
export interface Branch { a: P2; b: P2; n: P2 }
export interface Layout { label: string; pages: number[]; tables?: TableDef[]; basedOn?: string; removeTables?: string[] }
export interface Furniture {
  specs: {
    chaise: { w: number; d: number; h: number; seatH: number };
    tableRect: { w: number; d: number; h: number; top: number };
    tableCarree: { w: number; d: number; h: number; top: number };
    banquette: { depth: number; h: number; seatH: number };
    buffetPeripherique: { h: number; top: number };
    ilot: { w: number; d: number; h: number; top: number; bays: number; niches: number };
  };
  chairColors: Record<string, string>;
  layouts: Record<string, Layout>;
  banquettes: { id: string; type: string; branches: Branch[]; note?: string }[];
  buffets: { id: string; type: string; depth: number; branches: Branch[]; note?: string }[];
  ilot: { id: string; x: number; y: number; rot: number };
}
export interface MatDef { color: string; roughness?: number; metalness?: number; opacity?: number }
export interface FloorVariant { label: string; tile: number; band: number; bandAround: string; pages: number[]; status: string }
export interface Materials {
  [k: string]: unknown;
  floorVariants: Record<string, FloorVariant>;
  lustreVariants: Record<string, { label: string; pages: number[]; status: string }>;
}
export interface CameraView { id: string; label: string; group: string; pos: [number, number, number]; target: [number, number, number]; fov: number; pages: number[] }
export interface Cameras { eyeHeight: number; views: CameraView[] }
export interface RenderItem { id: string; file: string; page: number; title: string; zone: string; camera: string; note?: string }
export interface Renders { items: RenderItem[]; plans: { file: string; page: number; title: string }[] }
export interface SourceItem { element: string; value: string; pages: number[]; status: Status; note?: string; file: string }
export interface PdfRow { pages: string; category: string; content: string; usage: string; zone: string }

export interface ProjectData {
  geometry: Geometry; walls: Walls; ceiling: Ceiling; lighting: Lighting; furniture: Furniture;
  materials: Materials; cameras: Cameras; renders: Renders;
  sources: { items: SourceItem[] }; pdfIndex: { rows: PdfRow[] };
}

export interface Options {
  layout: string;        // clé de furniture.layouts
  floor: string;         // clé de materials.floorVariants
  lustre: string;        // clé de materials.lustreVariants
  showCeiling: boolean;
  showFurniture: boolean;
  quality: 'standard' | 'elevee';
  bloom: boolean;
}
