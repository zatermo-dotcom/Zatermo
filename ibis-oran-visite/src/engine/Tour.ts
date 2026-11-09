import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import type { CameraView, Options, ProjectData } from '../types';
import { buildMaterials, skyTexture } from './materials';
import { buildArchitecture } from './architecture';
import { buildWallDecor } from './wallDecor';
import { buildCeiling } from './ceiling';
import { buildBanquettes, buildBuffets, buildIlot, buildTables } from './furniture';
import { buildLighting } from './lighting';
import { pointInPolygon } from './util';

export interface CamState { x: number; y: number; h: number; yaw: number; overview: boolean }
export interface ModelStats {
  tables: number; rect: number; carree: number; chairs: Record<string, number>;
  banquettes: number; banquettesL: number; buffets: number; ilotPortes: number; lustres: number; appliques: number; spots: number; faces: number; gorges: number;
}

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export class Tour {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(60, 1, 0.05, 200);
  readonly controls: OrbitControls;
  private composer: EffectComposer;
  private bloom: UnrealBloomPass;
  private model = new THREE.Group();
  private ceiling?: THREE.Group;
  private furniture = new THREE.Group();
  private floor?: THREE.Mesh;
  private anim?: { from: [THREE.Vector3, THREE.Vector3]; to: [THREE.Vector3, THREE.Vector3]; fov: [number, number]; t0: number; dur: number; done?: () => void };
  private overview = false;
  private overviewLights = new THREE.Group();
  private clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 2.6);
  private raycaster = new THREE.Raycaster();
  private lastTap = 0;
  private keys = new Set<string>();
  private frameId = 0;
  private listeners: (() => void)[] = [];
  data: ProjectData; options: Options;
  stats?: ModelStats;
  onCamera?: (s: CamState) => void;
  onView?: (id: string | null) => void;

  constructor(private container: HTMLElement, data: ProjectData, options: Options) {
    this.data = data; this.options = options;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.localClippingEnabled = false;
    container.appendChild(this.renderer.domElement);
    this.renderer.domElement.setAttribute('aria-label', 'Vue 3D du restaurant');

    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.07;
    this.scene.background = skyTexture();
    this.model.name = 'Modele';
    this.scene.add(this.model);
    // éclairage d'appoint réservé aux vues aériennes (maquette « maison de poupée »)
    const sun = new THREE.DirectionalLight('#fff1dc', 1.6); sun.position.set(4, 20, 18); sun.target.position.set(9, 0, 6.5);
    this.overviewLights.add(sun, sun.target, new THREE.AmbientLight('#ffe6c4', 0.9));
    this.overviewLights.visible = false; this.scene.add(this.overviewLights);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.09;
    this.controls.rotateSpeed = 0.45;
    this.controls.addEventListener('start', () => { this.anim = undefined; this.onView?.(null); });

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.5, 0.45, 0.9);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.bindInput();
    this.rebuild();
    this.resize();
    const ro = new ResizeObserver(() => this.resize()); ro.observe(container);
    this.listeners.push(() => ro.disconnect());
    this.loop();
  }

  /** Reconstruit le modèle à partir des données (après changement de variante ou rechargement JSON). */
  rebuild(data?: ProjectData, options?: Options) {
    if (data) this.data = data; if (options) this.options = options;
    const d = this.data; const o = this.options;
    this.model.traverse((x) => { if ((x as THREE.Mesh).geometry) (x as THREE.Mesh).geometry.dispose(); });
    this.model.clear();
    const lib = buildMaterials(d.materials);
    const A = d.lighting.ambiance;
    this.model.add(new THREE.AmbientLight('#ffd9ad', A.ambient));
    const hemi = new THREE.HemisphereLight(A.hemiSky, A.hemiGround, A.hemi); hemi.name = 'Hemi'; this.model.add(hemi);
    this.renderer.toneMappingExposure = A.exposure;
    this.bloom.strength = o.bloom ? A.bloom : 0;

    const arch = buildArchitecture(d.geometry, d.ceiling, d.materials, lib, o.floor);
    this.floor = arch.floor; this.model.add(arch.root);
    this.model.add(buildWallDecor(d.walls, d.geometry, lib));
    this.ceiling = buildCeiling(d.geometry, d.ceiling, d.lighting, lib);
    this.ceiling.visible = o.showCeiling;
    this.model.add(this.ceiling);
    const lights = buildLighting(d.geometry, d.ceiling, d.lighting, lib, o.lustre, o.quality);
    this.model.add(lights);

    this.furniture = new THREE.Group(); this.furniture.name = 'Mobilier';
    const tables = buildTables(d.furniture, lib, o.layout);
    const banq = buildBanquettes(d.furniture, lib);
    const buf = buildBuffets(d.furniture, lib);
    const ilot = buildIlot(d.furniture, lib);
    this.furniture.add(tables, banq, buf, ilot);
    this.furniture.visible = o.showFurniture;
    this.model.add(this.furniture);

    const tu = tables.userData as { tables: number; rect: number; carree: number; chairs: Record<string, number> };
    this.stats = {
      ...tu,
      banquettes: banq.children.length, banquettesL: d.furniture.banquettes.filter((b) => b.type === 'L').length,
      buffets: buf.children.length, ilotPortes: ilot.userData.portes as number,
      lustres: d.ceiling.rosaces.items.length, appliques: d.lighting.applique.items.length, spots: d.lighting.spot.items.length,
      faces: d.walls.faces.length, gorges: d.ceiling.gorges.length,
    };
    this.applyOverviewState(true);
  }

  setOptions(o: Partial<Options>) {
    const prev = this.options; this.options = { ...prev, ...o };
    const structural = (['layout', 'floor', 'lustre', 'quality'] as const).some((k) => o[k] !== undefined && o[k] !== prev[k]);
    if (structural) { this.rebuild(); return; }
    if (this.ceiling) this.applyOverviewState(true);
    this.furniture.visible = this.options.showFurniture;
    this.bloom.strength = this.options.bloom ? this.data.lighting.ambiance.bloom : 0;
  }

  get animating() { return !!this.anim; }

  view(id: string): CameraView | undefined { return this.data.cameras.views.find((v) => v.id === id); }

  /** Vol animé vers une vue nommée de cameras.json. */
  goTo(id: string, instant = false) {
    const v = this.view(id); if (!v) return;
    this.flyTo(new THREE.Vector3(v.pos[0], v.pos[2], v.pos[1]), new THREE.Vector3(v.target[0], v.target[2], v.target[1]), v.fov, instant ? 0 : 1300);
    this.onView?.(id);
  }

  flyTo(pos: THREE.Vector3, target: THREE.Vector3, fov = this.camera.fov, dur = 1200) {
    const fromT = this.overview ? this.controls.target.clone() : this.camera.position.clone().add(this.camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(pos.distanceTo(target)));
    this.anim = { from: [this.camera.position.clone(), fromT], to: [pos, target], fov: [this.camera.fov, fov], t0: performance.now(), dur, done: () => this.settle(pos, target) };
    this.controls.enabled = false;
    if (dur === 0) this.step(performance.now() + 1);
  }

  private settle(pos: THREE.Vector3, target: THREE.Vector3) {
    this.overview = pos.y > 4.2;
    const c = this.controls;
    if (this.overview) {
      c.target.copy(target); c.enableZoom = true; c.enablePan = true; c.minDistance = 4; c.maxDistance = 45; c.maxPolarAngle = Math.PI * 0.47; c.minPolarAngle = 0;
    } else {
      // regarder autour : pivot à 0,4 m devant l'œil
      const dir = target.clone().sub(pos).normalize();
      c.target.copy(pos.clone().add(dir.multiplyScalar(0.4)));
      c.enableZoom = false; c.enablePan = false; c.minDistance = 0; c.maxDistance = Infinity; c.minPolarAngle = 0.15; c.maxPolarAngle = Math.PI - 0.15;
    }
    c.enabled = true; c.update();
    this.applyOverviewState();
  }

  private applyOverviewState(force = false) {
    const ov = this.overview;
    if (this.ceiling) this.ceiling.visible = this.options.showCeiling && !ov;
    this.model.traverse((x) => { if (x.name.startsWith('Lustre_')) x.visible = !ov; });
    this.renderer.clippingPlanes = ov ? [this.clip] : [];
    this.overviewLights.visible = ov;
    void force;
  }

  private step(now: number) {
    const a = this.anim; if (!a) return;
    const t = Math.min(1, (now - a.t0) / Math.max(1, a.dur)); const k = ease(t);
    this.camera.position.lerpVectors(a.from[0], a.to[0], k);
    const tgt = new THREE.Vector3().lerpVectors(a.from[1], a.to[1], k);
    this.camera.fov = a.fov[0] + (a.fov[1] - a.fov[0]) * k; this.camera.updateProjectionMatrix();
    this.camera.lookAt(tgt);
    // pendant le vol : plafond masqué tant que la caméra est au-dessus
    const above = this.camera.position.y > 4.2;
    if (above !== this.overview) { this.overview = above; this.applyOverviewState(); }
    if (t >= 1) { this.anim = undefined; a.done?.(); }
  }

  /** Avance / recule / se décale dans le plan horizontal en restant dans le contour. */
  walk(forward: number, strafe = 0) {
    if (this.overview || this.anim) return;
    const dir = this.camera.getWorldDirection(new THREE.Vector3()); dir.y = 0; dir.normalize();
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0));
    const delta = dir.multiplyScalar(forward).add(right.multiplyScalar(strafe));
    const next = this.camera.position.clone().add(delta);
    if (!this.insideRoom(next.x, next.z)) return;
    this.camera.position.add(delta); this.controls.target.add(delta); this.controls.update();
  }

  insideRoom(x: number, y: number) {
    const g = this.data.geometry; const p = g.poteau;
    if (x > p.x - 0.15 && x < p.x + p.w + 0.15 && y > p.y - 0.15 && y < p.y + p.d + 0.15) return false;
    return pointInPolygon([x, y], g.outline.points);
  }

  /** Déplacement « clic au sol » (double-clic / double-tap). */
  private moveToPointer(ev: PointerEvent | MouseEvent) {
    if (!this.floor) return;
    const r = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(ndc, this.camera);
    const hits = this.raycaster.intersectObjects(this.model.children, true).filter((h) => h.object.visible);
    const hit = hits[0];
    if (!hit || hit.object !== this.floor) return;
    const p = hit.point; if (!this.insideRoom(p.x, p.z)) return;
    const eye = this.data.cameras.eyeHeight;
    const dir = this.camera.getWorldDirection(new THREE.Vector3()); dir.y = 0;
    if (this.overview) dir.set(p.x - this.camera.position.x, 0, p.z - this.camera.position.z);
    dir.normalize();
    const pos = new THREE.Vector3(p.x, eye, p.z);
    this.flyTo(pos, pos.clone().add(dir.multiplyScalar(4)), 62, 900);
    this.onView?.(null);
  }

  private bindInput() {
    const el = this.renderer.domElement;
    const onDbl = (e: MouseEvent) => this.moveToPointer(e);
    const onUp = (e: PointerEvent) => {
      if (e.pointerType !== 'touch') return;
      const now = performance.now();
      if (now - this.lastTap < 320) { this.moveToPointer(e); this.lastTap = 0; } else this.lastTap = now;
    };
    const onWheel = (e: WheelEvent) => { if (this.overview) return; e.preventDefault(); this.walk(-Math.sign(e.deltaY) * 0.35); };
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'SELECT') return;
      if (e.type === 'keydown') this.keys.add(e.key.toLowerCase()); else this.keys.delete(e.key.toLowerCase());
    };
    el.addEventListener('dblclick', onDbl); el.addEventListener('pointerup', onUp);
    el.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', onKey); window.addEventListener('keyup', onKey);
    this.listeners.push(() => {
      el.removeEventListener('dblclick', onDbl); el.removeEventListener('pointerup', onUp); el.removeEventListener('wheel', onWheel);
      window.removeEventListener('keydown', onKey); window.removeEventListener('keyup', onKey);
    });
  }

  private resize() {
    const w = this.container.clientWidth || 1; const h = this.container.clientHeight || 1;
    this.renderer.setSize(w, h); this.composer.setSize(w, h);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }

  private lastEmit = 0;
  private loop = () => {
    this.frameId = requestAnimationFrame(this.loop);
    const now = performance.now();
    if (this.anim) this.step(now); else this.controls.update();
    const k = this.keys; const sp = 0.06;
    if (k.size) {
      if (k.has('arrowup') || k.has('z') || k.has('w')) this.walk(sp);
      if (k.has('arrowdown') || k.has('s')) this.walk(-sp);
      if (k.has('q') || k.has('a')) this.walk(0, -sp);
      if (k.has('d')) this.walk(0, sp);
      if (k.has('arrowleft')) this.turn(0.025);
      if (k.has('arrowright')) this.turn(-0.025);
    }
    this.composer.render();
    if (this.onCamera && now - this.lastEmit > 90) {
      this.lastEmit = now;
      const d = this.camera.getWorldDirection(new THREE.Vector3());
      this.onCamera({ x: this.camera.position.x, y: this.camera.position.z, h: this.camera.position.y, yaw: Math.atan2(d.z, d.x), overview: this.overview });
    }
  };

  turn(angle: number) {
    if (this.overview || this.anim) return;
    const c = this.controls; const off = c.target.clone().sub(this.camera.position);
    off.applyAxisAngle(new THREE.Vector3(0, 1, 0), angle); c.target.copy(this.camera.position).add(off); c.update();
  }

  /** Position courante au format cameras.json (pour le bureau d'études). */
  currentViewJSON(id = 'nouvelle-vue') {
    const p = this.camera.position; const d = this.camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(4).add(p);
    const r = (n: number) => Math.round(n * 100) / 100;
    return JSON.stringify({ id, label: 'Nouvelle vue', group: 'Salle', pos: [r(p.x), r(p.z), r(p.y)], target: [r(d.x), r(d.z), r(d.y)], fov: Math.round(this.camera.fov), pages: [] });
  }

  screenshot(): string { this.composer.render(); return this.renderer.domElement.toDataURL('image/jpeg', 0.9); }

  /** Export GLB du modèle courant (géométries, matériaux, lumières ponctuelles). */
  async exportGLB(): Promise<ArrayBuffer> {
    const exporter = new GLTFExporter();
    const wasCeil = this.ceiling?.visible; if (this.ceiling) this.ceiling.visible = true;
    this.model.traverse((x) => { if (x.name.startsWith('Lustre_')) x.visible = true; });
    const root = new THREE.Group(); root.name = 'Restaurant_ibis_Oran';
    const clone = this.model.clone(true);
    clone.children.filter((c) => (c as THREE.Light).isLight && !(c as THREE.PointLight).isPointLight).forEach((c) => clone.remove(c));
    root.add(clone);
    root.userData = { source: 'ILK_Portfolio_Restaurant_Ibis_modifie.pdf', repere: 'x = X plan, y = hauteur, z = Y plan (m)', options: this.options };
    if (this.ceiling) this.ceiling.visible = !!wasCeil;
    this.applyOverviewState();
    const out = await exporter.parseAsync(root, { binary: true, onlyVisible: false });
    return out as ArrayBuffer;
  }

  dispose() {
    cancelAnimationFrame(this.frameId);
    this.listeners.forEach((f) => f());
    this.controls.dispose(); this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
