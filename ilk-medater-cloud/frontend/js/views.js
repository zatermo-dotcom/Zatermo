// Vues spécifiques : tableau de bord, études et calculs, documents et BIM, base juridique, assistant IA.
import { api, clear, day, el, field, guard, money, num, pill, stamp, table } from './core.js';
import { invalidateRefs, renderResource } from './modules.js';

// ------------------------------------------------------------------ Tableau de bord
export async function dashboard(host) {
  const d = await api('/dashboard');
  const blocks = [];
  if (d.consolidated_finance) {
    const f = d.consolidated_finance;
    blocks.push(el('div', { class: 'card' }, el('h2', {}, 'Consolidation groupe (finances)'), el('div', { class: 'grid g4' },
      kpi('Créances clients', money(f.receivables)), kpi('dont échues', money(f.receivables_overdue)),
      kpi('Dettes fournisseurs', money(f.payables)), kpi('dont échues', money(f.payables_overdue)))));
  }
  for (const c of d.companies) {
    const k = c.kpis;
    const tiles = [];
    if (k.projects) tiles.push(kpi('Projets actifs', k.projects.active), kpi('Projets en retard', k.projects.late, k.projects.late ? 'crit' : ''), kpi('Budget actif', money(k.projects.active_budget)));
    if (k.sites) tiles.push(kpi('Chantiers actifs', k.sites.active), kpi('Avancement moyen', `${num(k.sites.avg_progress)} %`), kpi('Risques élevés ouverts', k.sites.high_risks_open, k.sites.high_risks_open ? 'crit' : ''));
    if (k.finance) tiles.push(kpi('Créances', money(k.finance.receivables)), kpi('Créances échues', money(k.finance.receivables_overdue), k.finance.receivables_overdue ? 'warn' : ''));
    if (k.contracts) tiles.push(kpi('Marchés en cours', k.contracts.active), kpi('Marchés en retard', k.contracts.late, k.contracts.late ? 'crit' : ''), kpi('Pénalités théoriques', money(k.contracts.theoretical_penalties)));
    if (k.studies) tiles.push(kpi('Livrables à valider', k.studies.to_validate), kpi('Conflits MEP ouverts', k.studies.open_issues));
    if (k.procurement) tiles.push(kpi('Articles sous le seuil', k.procurement.stock_below_min), kpi('Commandes à valider', k.procurement.orders_to_validate));
    if (k.hr) tiles.push(kpi('Effectif actif', k.hr.active_employees), kpi('Congés en attente', k.hr.leave_pending));
    if (k.qhse) tiles.push(kpi('Événements QHSE ouverts', k.qhse.open), kpi('Accidents (30 j)', k.qhse.accidents_30d, k.qhse.accidents_30d ? 'crit' : ''));
    blocks.push(el('div', { class: 'card' }, el('h2', {}, c.name), el('div', { class: 'grid g4' }, tiles)));
  }
  if (!d.companies.length) blocks.push(el('div', { class: 'card empty' }, 'Aucun module autorisé. Les accès sont attribués par le Directeur général.'));
  blocks.push(el('p', { class: 'muted' }, d.note));
  clear(host, el('div', { class: 'stack' }, blocks));
}
function kpi(label, value, tone = '') {
  return el('div', { class: 'kpi' }, el('small', {}, label), el('b', { style: tone ? `color:var(--${tone})` : null }, String(value ?? '—')));
}

// ------------------------------------------------------------------ Études, MEP et calculs
const ENGINE_EXAMPLES = {
  'cfo.power_balance': { loads: [{ label: 'Éclairage bureaux', quantity: 120, unit_power_w: 36, ku: 1, cos_phi: 0.95 }, { label: 'Prises PC', quantity: 80, unit_power_w: 250, ku: 0.6, cos_phi: 0.8 }], ks: 0.8, reserve: 1.2, voltage_v: 400, phases: 3 },
  'cfo.cable_drop': { power_w: 20000, voltage_v: 400, phases: 3, cos_phi: 0.85, length_m: 80, section_mm2: 10, material: 'cuivre', max_drop_pct: 5 },
  'cfa.vdi': { workstations: 40, outlets_per_workstation: 2, wifi_area_m2: 600, m2_per_access_point: 150, cameras: 12, reserve_pct: 20, ports_per_switch: 48, longest_run_m: 85 },
  'fire.extinguishers': { levels: [450, 450, 300], m2_per_extinguisher: 200, max_travel_m: 15, detector_coverage_m2: null, special_risk_rooms: 2 },
  'plumb.cold_water': { fixtures: { lavabo: 12, wc_reservoir: 10, douche: 4, evier: 2 }, max_velocity_ms: 1.5 },
  'plumb.rainwater': { area_m2: 800, runoff_coefficient: 1, intensity_mm_h: 'à renseigner (donnée du site)' },
  'hvac.cooling': { floor_area_m2: 120, walls: [{ label: 'Façade sud', u_w_m2k: 0.8, area_m2: 40, delta_t_k: 12 }], glazing: [{ area_m2: 18, shgc: 0.4, irradiance_w_m2: 'à renseigner' }], occupants: 12, lighting_w_m2: 10, equipment_w_m2: 15, fresh_air_m3h: 300, outdoor_indoor_dt_k: 12, humidity_diff_g_kg: 6, safety_factor: 1.1 },
  'air.duct': { flow_m3h: 2500, velocity_ms: 5, length_m: 25, singular_losses_zeta: 2.5, roughness_mm: 0.09, rectangular_aspect: 2 },
  'air.renewal': { occupants: 30, m3h_per_person: 25, volume_m3: 450, air_changes_per_h: 2 },
  'gc.column': { floors: 6, tributary_area_m2: 20, g_kn_m2: 6.5, q_kn_m2: 2.5, extra_g_kn: 0, fc28_mpa: 25, fe_mpa: 400, slenderness: 35, steel_ratio: 0.01, seismic_zone: 'IIa' },
};
const DISC_LABEL = { ARCH: 'Architecture', GC: 'Génie civil', CFO: 'MEP 01 · Courant fort', CFA: 'MEP 02 · Courants faibles', FIRE: 'MEP 03 · Incendie',
  PLUMB: 'MEP 04 · Plomberie', HVAC: 'MEP 05 · HVAC', AIR: 'MEP 06 · Aéraulique', COORD: 'Coordination MEP', LEGAL: 'Juridique' };

export async function studies(host, me) {
  const [cat, projects] = await Promise.all([api('/studies/catalog'), api('/projects')]);
  const projSel = el('select', {}, projects.map(p => el('option', { value: p.id }, `${p.code} — ${p.name}`)));
  const deliv = el('div'), calc = el('div'), issues = el('div');
  const canEdit = me.modules.studies?.edit, canValidate = me.modules.studies?.validate;

  async function loadDeliverables() {
    if (!projSel.value) return clear(deliv, el('div', { class: 'card empty' }, 'Aucun projet accessible.'));
    const rows = await api(`/studies/deliverables?project_id=${projSel.value}`);
    const actions = r => el('span', { class: 'row' },
      canEdit && ['brouillon', 'rejete'].includes(r.status) ? el('button', { class: 'btn sm', onclick: () => guard(() => api(`/studies/deliverables/${r.id}/submit`, { method: 'POST' }), 'Soumis').then(loadDeliverables) }, 'Soumettre') : null,
      canValidate && r.status === 'soumis' ? el('button', { class: 'btn sm', onclick: () => review(r.id, 'valide') }, 'Valider') : null,
      canValidate && r.status === 'soumis' ? el('button', { class: 'btn sm danger', onclick: () => review(r.id, 'rejete') }, 'Rejeter') : null);
    const form = el('form', { class: 'form-grid' },
      field('Spécialité', el('select', { name: 'discipline' }, Object.entries(DISC_LABEL).map(([k, v]) => el('option', { value: k }, v)))),
      field('Phase', el('select', { name: 'phase' }, cat.phases.map(p => el('option', { value: p }, p)))),
      field('Livrable', el('input', { name: 'title', required: true, list: 'tpl' })), field('Échéance', el('input', { name: 'due_date', type: 'date' })),
      el('datalist', { id: 'tpl' }, Object.values(cat.templates).flat().map(t => el('option', { value: t }))),
      el('button', { class: 'btn' }, 'Ajouter'));
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const body = { project_id: Number(projSel.value), discipline: form.discipline.value, phase: form.phase.value, title: form.title.value };
      if (form.due_date.value) body.due_date = form.due_date.value;
      await guard(() => api('/studies/deliverables', { method: 'POST', body }), 'Livrable ajouté'); loadDeliverables();
    });
    clear(deliv, el('div', { class: 'card stack' }, el('h2', {}, 'Livrables APS · APD · DCE · EXE'), canEdit ? el('details', {}, el('summary', {}, 'Nouveau livrable'), form) : null,
      table([{ label: 'Phase', render: r => pill(r.phase) }, { label: 'Spécialité', render: r => DISC_LABEL[r.discipline] || r.discipline }, { label: 'Livrable', key: 'title' },
        { label: 'Échéance', render: r => day(r.due_date) }, { label: 'Statut', render: r => pill(r.status) }, { label: 'Commentaire', key: 'review_comment' }, { label: '', render: actions }], rows)));
  }
  async function review(id, decision) {
    const comment = decision === 'rejete' ? window.prompt('Motif du rejet (obligatoire)') : '';
    if (decision === 'rejete' && !comment) return;
    await guard(() => api(`/studies/deliverables/${id}/review`, { method: 'POST', body: { decision, comment: comment || '' } }), decision === 'valide' ? 'Validé' : 'Rejeté');
    loadDeliverables();
  }

  // Calculateurs
  const engSel = el('select', {}, cat.engines.map(e => el('option', { value: e.code }, `${DISC_LABEL[e.discipline] || e.discipline} — ${e.name}`)));
  const inputs = el('textarea', { rows: 12, class: 'code-box', spellcheck: 'false', 'aria-label': 'Données d\'entrée (JSON)' });
  const meta = el('div', { class: 'muted' });
  const out = el('div');
  const setEngine = () => {
    const e = cat.engines.find(x => x.code === engSel.value);
    inputs.value = JSON.stringify(ENGINE_EXAMPLES[e.code] || {}, null, 2);
    clear(meta, el('div', {}, el('b', {}, 'Méthode : '), e.method), e.references.length ? el('div', {}, 'Références : ' + e.references.join(' ; ')) : null,
      el('div', {}, `Version du moteur : ${e.version}`));
    clear(out);
  };
  engSel.addEventListener('change', setEngine);
  const run = async save => {
    let data;
    try { data = JSON.parse(inputs.value); } catch { return guard(() => Promise.reject(new Error('JSON invalide'))); }
    const r = await guard(() => api(`/studies/calc/${engSel.value}`, { method: 'POST', body: { project_id: Number(projSel.value), inputs: data, save } }), save ? 'Calcul enregistré' : null);
    clear(out, el('div', { class: 'stack' }, el('h3', {}, 'Résultats'),
      table([{ label: 'Grandeur', key: 'k' }, { label: 'Valeur', render: x => typeof x.v === 'object' ? JSON.stringify(x.v) : String(x.v) }],
        Object.entries(r.outputs).map(([k, v]) => ({ k, v }))),
      r.warnings.map(w => el('div', { class: 'notice' }, w))));
  };
  setEngine();
  clear(calc, el('div', { class: 'card stack' }, el('h2', {}, 'Moteurs de pré-dimensionnement'),
    el('div', { class: 'notice info' }, 'Calculs déterministes et tracés (entrées, version, auteur). Aucun résultat n\'est produit par l\'IA. Les valeurs « à renseigner » sont des données du site à fournir.'),
    field('Moteur', engSel), meta, inputs,
    el('div', { class: 'row' }, el('button', { class: 'btn ghost', type: 'button', onclick: () => run(false) }, 'Calculer'),
      canEdit ? el('button', { class: 'btn', type: 'button', onclick: () => run(true) }, 'Calculer et enregistrer') : null), out));

  projSel.addEventListener('change', () => { loadDeliverables(); renderResource(issues, 'coordination-issues', me); });
  clear(host, el('div', { class: 'stack' }, el('div', { class: 'card row' }, field('Projet', projSel)), deliv, calc, issues));
  await loadDeliverables();
  await renderResource(issues, 'coordination-issues', me);
}

// ------------------------------------------------------------------ Documents et BIM
export async function documents(host, me) {
  const [docs, projects] = await Promise.all([api('/documents'), api('/projects')]);
  const canEdit = me.modules.documents?.edit;
  const form = el('form', { class: 'form-grid' },
    field('Fichier *', el('input', { type: 'file', name: 'file', required: true, accept: '.pdf,.dwg,.dxf,.ifc,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.csv,.txt' })),
    field('Titre *', el('input', { name: 'title', required: true })),
    field('Projet', el('select', { name: 'project_id' }, projects.map(p => el('option', { value: p.id }, `${p.code} — ${p.name}`)))),
    field('Type', el('select', { name: 'doc_type' }, ['plan', 'maquette_ifc', 'note_calcul', 'rapport', 'cctp', 'contrat', 'courrier', 'photo', 'autre'].map(t => el('option', { value: t }, t.replace('_', ' '))))),
    field('Spécialité', el('select', { name: 'discipline' }, ['GEN', 'ARCH', 'GC', 'CFO', 'CFA', 'FIRE', 'PLUMB', 'HVAC', 'AIR', 'COORD', 'LEGAL'].map(t => el('option', { value: t }, t)))),
    field('Confidentialité', el('select', { name: 'confidentiality' }, ['interne', 'confidentiel', 'secret'].map(t => el('option', { value: t }, t)))),
    field('Indice de révision', el('input', { name: 'revision_label', maxlength: 20 })),
    el('button', { class: 'btn' }, 'Téléverser'));
  form.addEventListener('submit', async e => {
    e.preventDefault();
    await guard(() => api('/documents', { method: 'POST', form: new FormData(form) }), 'Document enregistré');
    documents(host, me);
  });
  const rows = docs.map(d => ({ ...d, latest: d.versions[0] }));
  const ifcInfo = v => v?.metadata?.schema ? `${v.metadata.schema} · ` + Object.entries(v.metadata.counts || {}).map(([k, n]) => `${k.replace('IFC', '')} ${n}`).join(', ') : '';
  clear(host, el('div', { class: 'stack' },
    canEdit ? el('div', { class: 'card' }, el('h2', {}, 'Nouveau document'), el('p', { class: 'muted' }, 'Types contrôlés (signature du fichier), 200 Mo maximum, empreinte SHA-256 conservée. Une nouvelle version conserve l\'historique.'), form) : null,
    table([{ label: 'Titre', key: 'title' }, { label: 'Type', render: r => pill(r.doc_type) }, { label: 'Spécialité', key: 'discipline' },
      { label: 'Confidentialité', render: r => pill(r.confidentiality) }, { label: 'Version', render: r => `v${r.current_version}${r.latest?.revision_label ? ' (ind. ' + r.latest.revision_label + ')' : ''}` },
      { label: 'Fichier', render: r => r.latest ? el('a', { href: `/api/documents/${r.id}/versions/${r.latest.version}/download` }, r.latest.filename) : '—' },
      { label: 'IFC', render: r => ifcInfo(r.latest) || '—' }, { label: 'Déposé le', render: r => stamp(r.latest?.uploaded_at) },
      { label: 'SHA-256', render: r => el('code', { title: r.latest?.sha256 }, (r.latest?.sha256 || '').slice(0, 12)) },
      { label: '', render: r => canEdit ? versionButton(r, host, me) : '' }], rows),
    el('p', { class: 'muted' }, 'Visualisation 3D des maquettes IFC : prévue dans une version ultérieure (moteur web-ifc à intégrer localement). Les métadonnées et le comptage des éléments sont déjà extraits.')));
}
function versionButton(doc, host, me) {
  const input = el('input', { type: 'file', hidden: true });
  input.addEventListener('change', async () => {
    const fd = new FormData();
    fd.append('file', input.files[0]);
    fd.append('revision_label', window.prompt('Indice de révision (ex. B)') || '');
    await guard(() => api(`/documents/${doc.id}/versions`, { method: 'POST', form: fd }), 'Nouvelle version enregistrée');
    documents(host, me);
  });
  return el('span', {}, input, el('button', { class: 'btn sm ghost', onclick: () => input.click() }, 'Nouvelle version'));
}

// ------------------------------------------------------------------ Base juridique
export async function legal(host, me) {
  const rows = await api('/legal/sources');
  const canEdit = me.modules.legal?.edit, canValidate = me.modules.legal?.validate;
  const f = el('form', { class: 'form-grid' },
    field('Type de texte', el('select', { name: 'text_type' }, ['loi', 'ordonnance', 'decret_presidentiel', 'decret_executif', 'arrete', 'instruction', 'circulaire', 'cahier_des_charges', 'jurisprudence', 'autre'].map(t => el('option', { value: t }, t.replaceAll('_', ' '))))),
    field('Intitulé officiel *', el('input', { name: 'title', required: true })), field('Numéro *', el('input', { name: 'reference_number', required: true })),
    field('Article', el('input', { name: 'article' })), field('Date de publication', el('input', { name: 'publication_date', type: 'date' })),
    field('Journal officiel (n°, date)', el('input', { name: 'jo_reference' })), field('Version applicable', el('input', { name: 'version_label' })),
    field('En vigueur depuis', el('input', { name: 'valid_from', type: 'date' })), field('Abrogé le', el('input', { name: 'valid_to', type: 'date' })),
    field('URL source officielle', el('input', { name: 'source_url', type: 'url' })), field('Mots-clés (séparés par des virgules)', el('input', { name: 'keywords' })),
    field('Extrait copié de la source officielle', el('textarea', { name: 'excerpt' })), el('button', { class: 'btn' }, 'Enregistrer'));
  f.addEventListener('submit', async e => {
    e.preventDefault();
    const body = {};
    for (const k of ['text_type', 'title', 'reference_number', 'article', 'publication_date', 'jo_reference', 'version_label', 'valid_from', 'valid_to', 'source_url', 'excerpt']) {
      if (f[k].value.trim()) body[k] = f[k].value.trim();
    }
    body.keywords = f.keywords.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
    await guard(() => api('/legal/sources', { method: 'POST', body }), 'Référence enregistrée (à faire vérifier)'); legal(host, me);
  });
  clear(host, el('div', { class: 'stack' },
    el('div', { class: 'notice' }, 'Le logiciel n\'embarque aucun texte de loi. Chaque référence est saisie depuis la source officielle puis vérifiée par une autre personne. L\'assistant juridique ne cite que les références vérifiées et en vigueur.'),
    canEdit ? el('details', { class: 'card' }, el('summary', {}, 'Nouvelle référence'), el('div', { style: 'margin-top:10px' }, f)) : null,
    table([{ label: 'Texte', render: r => `${r.text_type.replaceAll('_', ' ')} n° ${r.reference_number}` }, { label: 'Article', key: 'article' }, { label: 'Intitulé', key: 'title' },
      { label: 'Publication', render: r => day(r.publication_date) }, { label: 'JO', key: 'jo_reference' }, { label: 'Version', key: 'version_label' },
      { label: 'Source', render: r => r.source_url ? el('a', { href: r.source_url, target: '_blank', rel: 'noopener noreferrer' }, 'ouvrir') : '—' },
      { label: 'Statut', render: r => pill(r.status) },
      { label: '', render: r => canValidate && r.status === 'non_verifiee' ? el('button', { class: 'btn sm', onclick: () => guard(() => api(`/legal/sources/${r.id}/verify`, { method: 'POST' }), 'Référence vérifiée').then(() => legal(host, me)) }, 'Marquer vérifiée') : '' }], rows)));
}

// ------------------------------------------------------------------ Assistant IA
export async function assistant(host, me) {
  const [status, list, projects] = await Promise.all([api('/ai/status'), api('/ai/assistants'), api('/projects').catch(() => [])]);
  if (!status.local_enabled_for_you && !status.cloud_enabled_for_you) {
    return clear(host, el('div', { class: 'card empty' }, 'ilk.medater AI n\'est pas activée pour votre compte. Seul le Directeur général peut l\'activer.'));
  }
  const sel = el('select', {}, list.filter(a => a.available).map(a => el('option', { value: a.code }, a.name)));
  const proj = el('select', {}, el('option', { value: '' }, 'Tous les projets autorisés'), projects.map(p => el('option', { value: p.id }, `${p.code} — ${p.name}`)));
  const engine = el('select', {}, el('option', { value: 'auto' }, 'Automatique'), el('option', { value: 'local' }, 'Local uniquement'),
    status.cloud_enabled_for_you && status.cloud_configured ? el('option', { value: 'cloud' }, 'Cloud (si autorisé)') : null);
  const consent = el('input', { type: 'checkbox' });
  const q = el('textarea', { rows: 4, maxlength: 2000, placeholder: 'Ex. : Quels chantiers ont un risque élevé ouvert ? Quelles factures clients sont échues ?' });
  const out = el('div', { class: 'stack' });
  const ask = async () => {
    if (q.value.trim().length < 3) return;
    if (engine.value !== 'local' && consent.checked) await api('/ai/consent', { method: 'POST' }).catch(() => null);
    clear(out, el('div', { class: 'muted' }, 'Analyse en cours…'));
    const r = await guard(() => api('/ai/ask', { method: 'POST', body: { assistant: sel.value, question: q.value, engine: engine.value, cloud_consent: consent.checked, project_id: proj.value ? Number(proj.value) : null } }))
      .catch(() => clear(out));
    if (!r) return;
    clear(out, el('div', { class: 'row' }, pill(`moteur : ${r.engine}`)), el('div', { class: 'chat-answer' }, r.answer),
      r.notices.map(n => el('div', { class: 'notice' }, n)),
      r.missing_information.length ? el('div', { class: 'notice info' }, el('b', {}, 'Informations manquantes : '), r.missing_information.join(' ')) : null,
      r.sources.length ? table([{ label: 'Réf.', key: 'id' }, { label: 'Type', key: 'type' }, { label: 'Source', key: 'label' }, { label: 'Identifiant', key: 'ref' }], r.sources) : null);
  };
  clear(host, el('div', { class: 'grid g2' },
    el('div', { class: 'card stack' }, el('h2', {}, 'Poser une question'), field('Assistant', sel), field('Projet', proj), field('Moteur', engine),
      status.cloud_enabled_for_you ? el('label', { class: 'row' }, consent, el('span', { class: 'muted' }, 'J\'accepte l\'envoi au fournisseur cloud pour cette demande (voir conditions)')) : null,
      q, el('button', { class: 'btn', onclick: ask }, 'Demander'), out),
    el('div', { class: 'card stack' }, el('h2', {}, 'État des moteurs'),
      el('div', {}, 'IA locale : ', pill(status.local_model_available ? 'disponible' : 'non disponible'), status.local_model ? ` (${status.local_model})` : ''),
      el('div', {}, 'IA cloud : ', pill(status.cloud_configured ? 'configurée' : 'non configurée'), status.cloud_model ? ` (${status.cloud_model})` : ''),
      el('p', { class: 'muted' }, 'Sans modèle local, l\'assistant répond par règles à partir des données autorisées, sans générer de texte.'),
      el('h3', {}, 'Conditions d\'usage du cloud'), el('p', { class: 'muted' }, status.policy_text),
      el('h3', {}, 'Assistants'), table([{ label: 'Assistant', key: 'name' }, { label: 'Domaine', key: 'focus' }, { label: 'Accès', render: a => pill(a.available ? 'actif' : 'non autorisé') }], list))));
}

export { invalidateRefs };
