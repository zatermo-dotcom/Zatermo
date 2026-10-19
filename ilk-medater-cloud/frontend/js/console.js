// Console du Directeur général : comptes, autorisations, IA, sessions, journal d'audit.
import { api, clear, el, field, guard, pill, stamp, table } from './core.js';

const SCOPE_LABEL = { company: 'Filiale', org_unit: 'Département', module: 'Module', project: 'Projet', document: 'Document' };
const ACTION_LABEL = { view: 'consulter', edit: 'modifier', validate: 'valider', export: 'exporter' };

export async function directorConsole(host) {
  const [users, cat] = await Promise.all([api('/admin/users'), api('/admin/catalog')]);
  const companyName = id => cat.companies.find(c => c.id === id)?.name ?? '—';
  const scopeText = g => {
    if (g.scope_type === 'company') return companyName(Number(g.scope_ref));
    if (g.scope_type === 'org_unit') return `${cat.org_units.find(u => u.code === g.scope_ref)?.name ?? g.scope_ref} (${companyName(g.company_id)})`;
    if (g.scope_type === 'module') return `${cat.modules.find(m => m.code === g.scope_ref)?.name ?? g.scope_ref} (${companyName(g.company_id)})`;
    if (g.scope_type === 'project') { const p = cat.projects.find(x => String(x.id) === g.scope_ref); return p ? `${p.code} — ${p.name}` : `#${g.scope_ref}`; }
    return `Document #${g.scope_ref}`;
  };
  const reload = () => directorConsole(host);

  // Nouveau compte
  const accForm = el('form', { class: 'form-grid' },
    field('Email *', el('input', { name: 'email', type: 'email', required: true })), field('Nom et prénom *', el('input', { name: 'full_name', required: true })),
    field('Fonction', el('input', { name: 'job_title' })),
    field('Département', el('select', { name: 'org_unit_code' }, el('option', { value: '' }, '—'), cat.org_units.map(u => el('option', { value: u.code }, u.name)))),
    field('Mot de passe temporaire *', el('input', { name: 'temporary_password', type: 'text', minlength: 12, required: true, autocomplete: 'off' })),
    el('button', { class: 'btn' }, 'Créer le compte (sans aucun droit)'));
  accForm.addEventListener('submit', async e => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(accForm));
    if (!body.org_unit_code) delete body.org_unit_code;
    await guard(() => api('/admin/users', { method: 'POST', body }), 'Compte créé : aucun droit tant que vous n\'en attribuez pas');
    reload();
  });

  // Attribution d'autorisation
  const others = users.filter(u => !u.is_group_director);
  const gUser = el('select', { name: 'user_id' }, others.map(u => el('option', { value: u.id }, `${u.full_name} <${u.email}>`)));
  const gType = el('select', { name: 'scope_type' }, Object.entries(SCOPE_LABEL).map(([k, v]) => el('option', { value: k }, v)));
  const gRef = el('select', { name: 'scope_ref' });
  const gRefDoc = el('input', { name: 'scope_doc', type: 'number', min: 1, placeholder: 'N° du document', hidden: true });
  const gCompany = el('select', { name: 'company_id' }, cat.companies.map(c => el('option', { value: c.id }, c.name)));
  const companyField = field('Filiale des données', gCompany);
  const actions = el('div', { class: 'row' }, Object.entries(ACTION_LABEL).map(([k, v]) =>
    el('label', { class: 'row' }, el('input', { type: 'checkbox', name: 'actions', value: k, checked: k === 'view' }), v)));
  const gExp = el('input', { name: 'expires_at', type: 'datetime-local' });
  const gNote = el('input', { name: 'note', maxlength: 300, placeholder: 'Motif, référence de la décision…' });
  const refreshRef = () => {
    const t = gType.value;
    gRefDoc.hidden = t !== 'document'; gRef.hidden = t === 'document';
    let opts = [];
    if (t === 'company') opts = cat.companies.map(c => [c.code, c.name]);
    if (t === 'org_unit') opts = cat.org_units.map(u => [u.code, `${u.name}${u.company_code === 'GROUP' ? ' (service commun)' : ''}`]);
    if (t === 'module') opts = cat.modules.map(m => [m.code, m.name]);
    if (t === 'project') opts = cat.projects.map(p => [p.id, `${p.code} — ${p.name} (${companyName(p.company_id)})`]);
    gRef.replaceChildren(...opts.map(([v, l]) => el('option', { value: v }, l)));
    const unit = cat.org_units.find(u => u.code === gRef.value);
    companyField.hidden = !(t === 'module' || (t === 'org_unit' && unit?.company_code === 'GROUP'));
  };
  gType.addEventListener('change', refreshRef); gRef.addEventListener('change', refreshRef); refreshRef();
  const grantForm = el('form', { class: 'stack' }, el('div', { class: 'form-grid' }, field('Collaborateur', gUser), field('Périmètre', gType),
    field('Élément', el('div', {}, gRef, gRefDoc)), companyField, field('Expiration (facultatif)', gExp), field('Note', gNote)),
    el('div', {}, el('div', { class: 'muted' }, 'Actions autorisées (toute action implique la consultation) :'), actions),
    el('div', {}, el('button', { class: 'btn', disabled: !others.length }, 'Attribuer l\'autorisation')));
  grantForm.addEventListener('submit', async e => {
    e.preventDefault();
    const acts = [...grantForm.querySelectorAll('input[name=actions]:checked')].map(i => i.value);
    const body = { user_id: Number(gUser.value), scope_type: gType.value, scope_ref: gType.value === 'document' ? gRefDoc.value : String(gRef.value), actions: acts, note: gNote.value };
    if (!companyField.hidden) body.company_id = Number(gCompany.value);
    if (gExp.value) body.expires_at = new Date(gExp.value).toISOString();
    await guard(() => api('/admin/grants', { method: 'POST', body }), 'Autorisation attribuée'); reload();
  });

  // Tableau des comptes
  const userCard = u => {
    const grantRows = u.grants.map(g => el('tr', {},
      el('td', {}, SCOPE_LABEL[g.scope_type]), el('td', {}, scopeText(g)), el('td', {}, g.actions.map(a => ACTION_LABEL[a]).join(', ')),
      el('td', {}, g.expires_at ? stamp(g.expires_at) : 'sans'), el('td', {}, pill(g.status)),
      el('td', {}, el('span', { class: 'row' },
        g.status === 'active' ? el('button', { class: 'btn sm ghost', onclick: () => patchGrant(g.id, { status: 'suspended' }, 'Suspendue') }, 'Suspendre') : null,
        g.status === 'suspended' ? el('button', { class: 'btn sm ghost', onclick: () => patchGrant(g.id, { status: 'active' }, 'Réactivée') }, 'Réactiver') : null,
        el('button', { class: 'btn sm danger', onclick: () => confirmRevoke(g.id) }, 'Révoquer')))));
    const aiLocal = el('input', { type: 'checkbox', checked: u.ai.local }), aiCloud = el('input', { type: 'checkbox', checked: u.ai.cloud });
    const saveAi = () => guard(() => api(`/admin/users/${u.id}/ai`, { method: 'PUT', body: { local_enabled: aiLocal.checked, cloud_enabled: aiCloud.checked } }), 'Réglage IA enregistré');
    aiLocal.addEventListener('change', saveAi); aiCloud.addEventListener('change', saveAi);
    return el('div', { class: 'card stack' },
      el('div', { class: 'row between' },
        el('div', {}, el('b', {}, u.full_name), ' ', el('span', { class: 'muted' }, `<${u.email}> ${u.job_title || ''}`), ' ',
          u.is_group_director ? pill('Directeur général') : pill(u.enabled ? 'actif' : 'désactivé'), u.locked ? pill('verrouillé') : null,
          u.mfa_enabled ? pill('MFA') : null, el('span', { class: 'muted' }, ` · dernière connexion ${stamp(u.last_login_at)} · sessions ${u.active_sessions}`)),
        u.is_group_director ? null : el('span', { class: 'row' },
          el('label', { class: 'row' }, aiLocal, 'IA locale'), el('label', { class: 'row' }, aiCloud, 'IA cloud'),
          el('button', { class: 'btn sm ghost', onclick: () => guard(() => api(`/admin/users/${u.id}/revoke-sessions`, { method: 'POST' }), 'Sessions fermées').then(reload) }, 'Fermer les sessions'),
          el('button', { class: 'btn sm ghost', onclick: () => resetPw(u.id) }, 'Réinitialiser le mot de passe'),
          el('button', { class: 'btn sm ' + (u.enabled ? 'danger' : ''), onclick: () => guard(() => api(`/admin/users/${u.id}`, { method: 'PATCH', body: { enabled: !u.enabled } }), u.enabled ? 'Compte désactivé' : 'Compte réactivé').then(reload) }, u.enabled ? 'Désactiver' : 'Réactiver'))),
      u.is_group_director ? el('div', { class: 'muted' }, 'Tous les droits sur les deux filiales. Seul compte habilité à attribuer des autorisations.')
        : grantRows.length ? el('div', { class: 'table-wrap' }, el('table', {}, el('thead', {}, el('tr', {}, ['Type', 'Périmètre', 'Actions', 'Expire', 'État', ''].map(h => el('th', {}, h)))), el('tbody', {}, grantRows)))
          : el('div', { class: 'muted' }, 'Aucun droit métier (refus par défaut).'));
  };
  async function patchGrant(id, body, msg) { await guard(() => api(`/admin/grants/${id}`, { method: 'PATCH', body }), msg); reload(); }
  async function confirmRevoke(id) { if (window.confirm('Révoquer définitivement cette autorisation ?')) patchGrant(id, { status: 'revoked' }, 'Révoquée'); }
  async function resetPw(id) {
    const pw = window.prompt('Mot de passe temporaire (12 caractères min., changement imposé à la connexion)');
    if (pw) { await guard(() => api(`/admin/users/${id}/reset-password`, { method: 'POST', body: { temporary_password: pw } }), 'Mot de passe réinitialisé'); reload(); }
  }

  // Journal d'audit
  const auditBox = el('div');
  const loadAudit = async () => {
    const [rows, verify] = await Promise.all([api('/admin/audit?limit=150'), api('/admin/audit/verify')]);
    const who = id => users.find(u => u.id === id)?.email ?? (id ? `#${id}` : 'système');
    clear(auditBox, el('div', { class: verify.intact ? 'notice info' : 'notice' },
      verify.intact ? `Journal intègre : ${verify.events} événements, chaînage SHA-256 vérifié.` : `ALERTE : chaînage rompu à l'événement ${verify.broken_id} (${verify.reason}).`),
      table([{ label: 'Date', render: r => stamp(r.at) }, { label: 'Auteur', render: r => who(r.actor_id) }, { label: 'Action', key: 'action' },
        { label: 'Ressource', key: 'resource' }, { label: 'Détails', render: r => Object.keys(r.details).length ? JSON.stringify(r.details).slice(0, 160) : '' },
        { label: 'IP', key: 'ip' }, { label: 'Empreinte', render: r => el('code', {}, r.hash) }], rows));
  };

  clear(host, el('div', { class: 'stack' },
    el('div', { class: 'notice info' }, 'Règle du groupe : seul le Directeur général attribue les droits. Un compte créé n\'a aucun droit métier. La base de données refuse toute autorisation dont l\'auteur n\'est pas le Directeur.'),
    el('div', { class: 'grid g2' }, el('div', { class: 'card stack' }, el('h2', {}, 'Nouveau compte'), accForm), el('div', { class: 'card stack' }, el('h2', {}, 'Attribuer une autorisation'), grantForm)),
    el('h3', {}, `Comptes (${users.length})`), users.map(userCard),
    el('details', { class: 'card' }, el('summary', {}, 'Journal d\'audit'), el('div', { style: 'margin-top:10px' }, auditBox))));
  host.querySelector('details:last-child').addEventListener('toggle', e => e.target.open && loadAudit(), { once: true });
}
