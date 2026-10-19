// Siège virtuel 3D : bâtiment à 3 niveaux généré depuis /api/building (bureaux réels + état d'accès de l'utilisateur).
// RDC : Direction générale et services communs · R+1 : eurl medater · R+2 : cabinet ILK.
// Three.js est servi localement (/vendor) : aucun accès Internet requis.
import * as THREE from '/vendor/three.module.min.js';

const FLOOR_H = 3.8, DEPTH = 16, CORRIDOR = 3, CORE = 6, OFFICE_W = 4.6;
const COLORS = { ok: 0xd9c3a0, okEdge: 0xc99a3c, locked: 0x56657c, glass: 0x9cc7e6, slab: 0xc9ced6, core: 0x2b3d57 };

export function mountHQ(host, building, { onOffice, onFloorChange } = {}) {
  const width = () => host.clientWidth, height = () => host.clientHeight;
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  host.prepend(renderer.domElement);
  const labels = document.createElement('div');
  labels.className = 'labels';
  host.append(labels);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d1d33);
  scene.fog = new THREE.Fog(0x0d1d33, 70, 150);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);

  scene.add(new THREE.HemisphereLight(0xdbe8ff, 0x1c2a3c, 1.4));
  const sun = new THREE.DirectionalLight(0xfff1dc, 2.2);
  sun.position.set(30, 45, 25);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45 });
  scene.add(sun);

  const mat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.05, ...extra });
  const M = {
    ground: mat(0x1a2d24), slab: mat(COLORS.slab), core: mat(COLORS.core), ok: mat(COLORS.ok), locked: mat(COLORS.locked),
    glass: mat(COLORS.glass, { transparent: true, opacity: 0.22, roughness: 0.1, metalness: 0.3, depthWrite: false }),
    desk: mat(0xa27b55), dark: mat(0x27313f), brass: mat(0xc99a3c, { emissive: 0xc99a3c, emissiveIntensity: 0.35, metalness: 0.6 }),
    led: mat(0xffffff, { emissive: 0xfff4e0, emissiveIntensity: 1.2 }), cabin: mat(0xd8dde5, { metalness: 0.6, roughness: 0.3 }),
    plant: mat(0x3f8f5c), path: mat(0xb9b2a3),
  };
  const box = (w, h, d, m, x, y, z, parent, shadow = true) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    mesh.position.set(x, y, z);
    mesh.castShadow = shadow; mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  };

  // Implantation des bureaux par niveau
  const floors = [0, 1, 2].map(level => building.offices.filter(o => o.floor === level));
  const perSide = Math.max(...floors.map(f => Math.ceil(f.length / 2)), 3);
  const halfLen = Math.ceil(perSide / 2) * OFFICE_W + CORE / 2 + 1;
  const LEN = halfLen * 2;

  const ground = new THREE.Mesh(new THREE.PlaneGeometry(220, 220), M.ground);
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.05; ground.receiveShadow = true;
  scene.add(ground);
  box(LEN + 14, 0.08, 6, M.path, 0, 0, DEPTH / 2 + 5, scene, false); // parvis
  for (const x of [-LEN / 2 - 4, LEN / 2 + 4]) for (const z of [-6, 6]) {
    box(0.4, 1.2, 0.4, M.dark, x, 0.6, z, scene);
    const crown = new THREE.Mesh(new THREE.SphereGeometry(1.4, 16, 12), M.plant);
    crown.position.set(x, 2.3, z); crown.castShadow = true; scene.add(crown);
  }

  const levelGroups = [], pickables = [], officeAnchors = [];
  floors.forEach((offices, level) => {
    const g = new THREE.Group();
    g.position.y = level * FLOOR_H;
    scene.add(g); levelGroups.push(g);
    box(LEN, 0.3, DEPTH, M.slab, 0, 0.15, 0, g);
    // Façades vitrées et poteaux
    for (const z of [-DEPTH / 2, DEPTH / 2]) box(LEN, FLOOR_H - 0.3, 0.06, M.glass, 0, FLOOR_H / 2 + 0.15, z, g, false);
    for (const x of [-LEN / 2, LEN / 2]) box(0.06, FLOOR_H - 0.3, DEPTH, M.glass, x, FLOOR_H / 2 + 0.15, 0, g, false);
    for (let x = -LEN / 2; x <= LEN / 2 + 0.01; x += OFFICE_W) for (const z of [-DEPTH / 2, DEPTH / 2]) box(0.25, FLOOR_H, 0.25, M.dark, x, FLOOR_H / 2, z, g);
    // Éclairage architectural : bandeau LED au plafond du couloir + lumière d'ambiance
    box(LEN - 2, 0.05, 0.25, M.led, 0, FLOOR_H - 0.1, 0, g, false);
    const pl = new THREE.PointLight(0xffe9c9, 18, 26, 1.6);
    pl.position.set(0, FLOOR_H - 0.6, 0); g.add(pl);
    // Noyau : ascenseur et escalier
    box(CORE, FLOOR_H - 0.3, CORRIDOR + 3, M.core, 0, FLOOR_H / 2 + 0.15, -DEPTH / 2 + (CORRIDOR + 3) / 2 + 0.2, g);
    // Signalétique d'étage
    const sign = box(5, 0.5, 0.08, M.brass, 0, FLOOR_H - 0.6, DEPTH / 2 + 0.05, g, false);
    sign.userData.floorSign = level;

    // Bureaux : deux rangées de part et d'autre du couloir, de chaque côté du noyau
    const slots = [];
    for (let i = 0; i < perSide; i++) {
      const side = i % 2 === 0 ? -1 : 1, k = Math.floor(i / 2);
      const x = side * (CORE / 2 + OFFICE_W / 2 + k * OFFICE_W);
      slots.push({ x, z: -(CORRIDOR / 2 + (DEPTH / 2 - CORRIDOR / 2) / 2) }, { x, z: CORRIDOR / 2 + (DEPTH / 2 - CORRIDOR / 2) / 2 });
    }
    const roomD = DEPTH / 2 - CORRIDOR / 2 - 0.2;
    offices.forEach((o, i) => {
      const s = slots[i];
      if (!s) return;
      const m = o.accessible ? M.ok : M.locked;
      const plate = box(OFFICE_W - 0.25, 0.06, roomD, m, s.x, 0.33, s.z, g, false);
      plate.userData.office = o;
      pickables.push(plate);
      // Cloisons vitrées côté couloir + latérales
      const zc = s.z + Math.sign(-s.z) * roomD / 2;
      box(OFFICE_W - 0.25, 2.6, 0.05, M.glass, s.x, 1.6, zc, g, false);
      box(0.05, 2.6, roomD, M.glass, s.x - OFFICE_W / 2 + 0.12, 1.6, s.z, g, false);
      // Mobilier : bureaux et écrans
      for (const dx of [-0.9, 0.9]) {
        const desk = box(1.4, 0.06, 0.7, M.desk, s.x + dx, 1.08, s.z, g);
        desk.userData.office = o; pickables.push(desk);
        box(0.06, 0.72, 0.6, M.dark, s.x + dx - 0.65, 0.7, s.z, g);
        box(0.55, 0.35, 0.04, M.dark, s.x + dx, 1.35, s.z - Math.sign(s.z) * 0.25, g);
      }
      // Bandeau de porte (couleur selon l'accès)
      const door = box(1.2, 0.18, 0.06, o.accessible ? M.brass : M.dark, s.x, 2.75, zc, g, false);
      door.userData.office = o; pickables.push(door);
      officeAnchors.push({ office: o, level, pos: new THREE.Vector3(s.x, level * FLOOR_H + 2.4, s.z) });
    });
  });

  // Toit et ascenseur vitré en façade
  const roof = box(LEN + 0.6, 0.35, DEPTH + 0.6, M.dark, 0, 3 * FLOOR_H + 0.2, 0, scene);
  const shaftX = LEN / 2 + 1.6;
  box(2.4, 3 * FLOOR_H + 0.4, 2.4, M.glass, shaftX, (3 * FLOOR_H) / 2, 0, scene, false);
  const cabin = box(2, 2.6, 2, M.cabin, shaftX, 1.6, 0, scene);

  // HTML : étiquettes des bureaux
  const tags = officeAnchors.map(a => {
    const t = document.createElement('div');
    t.className = 'lbl' + (a.office.accessible ? '' : ' locked');
    t.textContent = a.office.name.replace(/^MEP 0\d — /, '');
    t.title = a.office.accessible ? `Ouvrir : ${a.office.name}` : `${a.office.name} — accès non autorisé`;
    t.addEventListener('click', () => onOffice?.(a.office));
    labels.append(t);
    return { ...a, el: t };
  });
  // Vue d'ensemble : une étiquette par niveau (les bureaux s'affichent en vue d'étage)
  const floorTags = building.floors.map(f => {
    const t = document.createElement('div');
    t.className = 'lbl';
    t.textContent = f.name;
    t.addEventListener('click', () => showFloor(f.level));
    labels.append(t);
    return { level: f.level, el: t, pos: new THREE.Vector3(-LEN / 2 - 0.5, f.level * FLOOR_H + FLOOR_H / 2, DEPTH / 2) };
  });

  // Caméra orbitale (souris/tactile)
  const state = { yaw: 0.75, pitch: 0.55, dist: Math.max(46, LEN * 1.25), target: new THREE.Vector3(0, FLOOR_H * 1.5, 0), floor: 'all' };
  const goal = { ...state, target: state.target.clone() };
  let cabinGoal = 1.6;
  function place() {
    camera.position.set(state.target.x + Math.sin(state.yaw) * Math.cos(state.pitch) * state.dist,
      state.target.y + Math.sin(state.pitch) * state.dist, state.target.z + Math.cos(state.yaw) * Math.cos(state.pitch) * state.dist);
    camera.lookAt(state.target);
  }
  let drag = null, moved = false;
  const cv = renderer.domElement;
  cv.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY }; moved = false; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
    goal.yaw -= dx * 0.006; goal.pitch = Math.min(1.35, Math.max(0.12, goal.pitch + dy * 0.004));
    drag = { x: e.clientX, y: e.clientY };
  });
  cv.addEventListener('pointerup', e => {
    drag = null;
    if (moved) return;
    const r = cv.getBoundingClientRect();
    const ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1), camera);
    const hit = ray.intersectObjects(pickables.filter(p => p.parent.visible))[0];
    if (hit) onOffice?.(hit.object.userData.office);
  });
  cv.addEventListener('wheel', e => { e.preventDefault(); goal.dist = Math.min(140, Math.max(12, goal.dist * (1 + e.deltaY * 0.001))); }, { passive: false });

  function showFloor(f) {
    state.floor = f;
    levelGroups.forEach((g, i) => { g.visible = f === 'all' || i <= f; });
    roof.visible = f === 'all';
    goal.target.set(0, f === 'all' ? FLOOR_H * 1.5 : f * FLOOR_H + 1.2, 0);
    goal.dist = f === 'all' ? Math.max(46, LEN * 1.25) : Math.max(30, LEN * 0.9);
    goal.pitch = f === 'all' ? 0.55 : 0.85;
    cabinGoal = (f === 'all' ? 0 : f) * FLOOR_H + 1.6;
    onFloorChange?.(f);
  }

  const v = new THREE.Vector3();
  function resize() {
    camera.aspect = width() / Math.max(1, height());
    camera.updateProjectionMatrix();
    renderer.setSize(width(), height());
  }
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  resize();
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  renderer.setAnimationLoop(() => {
    const k = reduce ? 1 : 0.12;
    state.yaw += (goal.yaw - state.yaw) * k; state.pitch += (goal.pitch - state.pitch) * k; state.dist += (goal.dist - state.dist) * k;
    state.target.lerp(goal.target, k);
    cabin.position.y += (cabinGoal - cabin.position.y) * (reduce ? 1 : 0.06);
    place();
    renderer.render(scene, camera);
    const w = width(), h = height();
    for (const t of [...tags, ...floorTags]) {
      const visible = state.floor === 'all' ? floorTags.includes(t) : (t.level === state.floor && !floorTags.includes(t));
      v.copy(t.pos).project(camera);
      const show = visible && v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05;
      t.el.style.display = show ? '' : 'none';
      if (show) { t.el.style.left = `${(v.x + 1) / 2 * w}px`; t.el.style.top = `${(1 - v.y) / 2 * h}px`; }
    }
  });

  return {
    showFloor,
    reset() { goal.yaw = 0.75; showFloor('all'); },
    dispose() {
      renderer.setAnimationLoop(null); ro.disconnect(); renderer.dispose();
      scene.traverse(o => { o.geometry?.dispose?.(); });
      labels.remove(); cv.remove();
    },
  };
}
