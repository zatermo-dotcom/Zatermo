// Point d'entrée : connexion (mot de passe + MFA), navigation, routage des vues.
import { api, ApiError, clear, el, field, guard, toast } from './core.js';
import { directorConsole } from './console.js';
import { invalidateRefs, tabs } from './modules.js';
import { assistant, dashboard, directivesView, documents, legal, perCompany, studies } from './views.js';

const $ = id => document.getElementById(id);
let me = null;
let hq = null;

// ------------------------------------------------------------------ Connexion
function loginStep(...nodes) { clear($('login-step'), ...nodes); $('login-error').textContent = ''; }
function showLogin() {
  me = null; hq?.dispose(); hq = null;
  $('app').hidden = true; $('login').hidden = false;
  const email = el('input', { type: 'email', autocomplete: 'username', required: true });
  const pw = el('input', { type: 'password', autocomplete: 'current-password', required: true });
  loginStep(field('Email', email), field('Mot de passe', pw), el('button', { class: 'btn', type: 'submit' }, 'Se connecter'));
  $('login-form').onsubmit = async e => {
    e.preventDefault();
    try {
      const r = await api('/auth/login', { method: 'POST', body: { email: email.value, password: pw.value } });
      if (r.mfa_setup_required) return mfaSetup(r);
      if (r.mfa_required) return mfaStep(r);
      if (r.must_change_password) return passwordStep(pw.value);
      boot();
    } catch (err) { $('login-error').textContent = err.message; }
  };
  email.focus();
}

function mfaStep(loginResult) {
  const code = el('input', { inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: 6, placeholder: '123456' });
  const rec = el('input', { placeholder: 'xxxxxx-xxxxxx-xxxxxx', autocomplete: 'off' });
  loginStep(el('p', {}, 'Saisissez le code à 6 chiffres de votre application d\'authentification.'), field('Code MFA', code),
    el('details', {}, el('summary', { class: 'muted' }, 'Téléphone perdu : utiliser un code de récupération'), field('Code de récupération', rec)),
    el('button', { class: 'btn', type: 'submit' }, 'Vérifier'));
  $('login-form').onsubmit = async e => {
    e.preventDefault();
    try {
      const r = await api('/auth/mfa/verify', { method: 'POST', body: rec.value ? { recovery_code: rec.value } : { code: code.value } });
      if (rec.value) toast(`Code de récupération utilisé. Il en reste ${r.recovery_codes_remaining}.`);
      if (r.must_change_password || loginResult.must_change_password) return passwordStep();
      boot();
    } catch (err) { $('login-error').textContent = err.message; }
  };
  code.focus();
}

async function mfaSetup(loginResult) {
  const s = await api('/auth/mfa/setup', { method: 'POST' });
  const code = el('input', { inputmode: 'numeric', maxlength: 6, placeholder: '123456' });
  loginStep(el('p', {}, 'Activation de la double authentification. Ajoutez ce compte dans votre application (Google Authenticator, Aegis, Microsoft Authenticator) avec la clé :'),
    el('div', { class: 'code-box' }, s.secret), el('details', {}, el('summary', { class: 'muted' }, 'Lien de configuration'), el('div', { class: 'code-box' }, s.otpauth_uri)),
    field('Code affiché par l\'application', code), el('button', { class: 'btn', type: 'submit' }, 'Activer'));
  $('login-form').onsubmit = async e => {
    e.preventDefault();
    try {
      const r = await api('/auth/mfa/confirm', { method: 'POST', body: { code: code.value } });
      loginStep(el('p', {}, 'Conservez ces codes de récupération hors ligne (usage unique). Ils ne seront plus affichés :'),
        el('div', { class: 'code-box' }, r.recovery_codes.join('  ·  ')), el('button', { class: 'btn', type: 'submit' }, 'J\'ai noté mes codes'));
      $('login-form').onsubmit = ev => { ev.preventDefault(); loginResult.must_change_password ? passwordStep() : boot(); };
    } catch (err) { $('login-error').textContent = err.message; }
  };
}

function passwordStep(current = '') {
  const cur = el('input', { type: 'password', autocomplete: 'current-password', value: current || null });
  const nw = el('input', { type: 'password', autocomplete: 'new-password', minlength: 12 });
  const nw2 = el('input', { type: 'password', autocomplete: 'new-password', minlength: 12 });
  loginStep(el('p', {}, 'Choisissez un nouveau mot de passe (12 caractères minimum, au moins 3 types parmi minuscules, majuscules, chiffres, symboles).'),
    field('Mot de passe actuel', cur), field('Nouveau mot de passe', nw), field('Confirmer', nw2), el('button', { class: 'btn', type: 'submit' }, 'Enregistrer'));
  $('login-form').onsubmit = async e => {
    e.preventDefault();
    if (nw.value !== nw2.value) { $('login-error').textContent = 'Les mots de passe diffèrent'; return; }
    try { await api('/auth/password', { method: 'POST', body: { current_password: cur.value, new_password: nw.value } }); boot(); }
    catch (err) { $('login-error').textContent = err.message; }
  };
}

document.addEventListener('ilk:unauthorized', () => { if (me) { toast('Session expirée, reconnectez-vous', true); showLogin(); } });
$('logout').addEventListener('click', async () => { await api('/auth/logout', { method: 'POST' }).catch(() => null); showLogin(); });

// ------------------------------------------------------------------ Navigation
const can = m => me?.modules?.[m]?.any;
const ROUTES = [
  { id: 'hq', label: 'Siège virtuel 3D', group: 'Navigation', ok: () => true, render: renderHQ },
  { id: 'dashboard', label: 'Tableau de bord', group: 'Navigation', ok: () => true, render: h => dashboard(h) },
  { id: 'directives', label: 'Directives de la DG', group: 'Navigation', ok: () => me.is_group_director || can('projects'), render: h => directivesView(h, me) },
  { id: 'projects', label: 'Projets', group: 'Métiers', ok: () => can('projects'), render: h => tabs(h, [{ key: 'projects' }, { key: 'milestones' }], me) },
  { id: 'sites', label: 'Chantiers', group: 'Métiers', ok: () => can('sites'), render: h => tabs(h, [{ key: 'sites' }, { key: 'daily-reports' }, { key: 'site-risks' }], me) },
  { id: 'studies', label: 'Études, MEP et calculs', group: 'Métiers', ok: () => can('studies'), render: h => studies(h, me) },
  { id: 'documents', label: 'Documents et BIM', group: 'Métiers', ok: () => can('documents'), render: h => documents(h, me) },
  { id: 'contracts', label: 'Marchés et contrats', group: 'Métiers', ok: () => can('contracts'), render: h => perCompany(h, me, 'contracts', [{ key: 'contracts' }, { key: 'contract-events' }, { key: 'situations' }], 'Marchés de la filiale') },
  { id: 'qhse', label: 'Qualité et HSE', group: 'Métiers', ok: () => can('qhse'), render: h => tabs(h, [{ key: 'qhse-events' }], me) },
  { id: 'finance', label: 'Finances', group: 'Gestion', ok: () => can('finance'), render: h => perCompany(h, me, 'finance', [{ key: 'invoices' }, { key: 'payments' }], 'Comptabilité de la filiale') },
  { id: 'procurement', label: 'Achats et stocks', group: 'Gestion', ok: () => can('procurement'), render: h => tabs(h, [{ key: 'purchase-orders' }, { key: 'stock-items' }, { key: 'stock-movements' }], me) },
  { id: 'equipment', label: 'Parc matériel', group: 'Gestion', ok: () => can('equipment'), render: h => tabs(h, [{ key: 'equipment' }], me) },
  { id: 'hr', label: 'Ressources humaines', group: 'Gestion', ok: () => can('hr'), render: h => tabs(h, [{ key: 'employees' }, { key: 'leave-requests' }], me) },
  { id: 'crm', label: 'Clients et fournisseurs', group: 'Gestion', ok: () => can('crm'), render: h => tabs(h, [{ key: 'parties' }], me) },
  { id: 'legal', label: 'Base juridique', group: 'Gestion', ok: () => can('legal'), render: h => legal(h, me) },
  { id: 'assistant', label: 'ilk.medater AI', group: 'Assistance', ok: () => me.ai_local || me.ai_cloud, render: h => assistant(h, me) },
  { id: 'console', label: 'Console du Directeur', group: 'Direction', ok: () => me.is_group_director, render: h => directorConsole(h) },
];
const OFFICE_ROUTE = { dashboard: 'dashboard', admin: 'console', assistant: 'assistant', direction: 'directives' };

function renderNav(active) {
  const nav = $('nav');
  nav.replaceChildren();
  let group = '';
  for (const r of ROUTES) {
    if (r.id === 'console' && !me.is_group_director) continue;
    if (r.group !== group) { group = r.group; nav.append(el('div', { class: 'group' }, group)); }
    nav.append(el('a', { href: `#/${r.id}`, class: (r.id === active ? 'active ' : '') + (r.ok() ? '' : 'locked'), title: r.ok() ? null : 'Accès non attribué par le Directeur général' }, r.label));
  }
}

async function route() {
  if (!me) return;
  const id = (location.hash.replace(/^#\//, '') || 'hq').split('?')[0];
  const r = ROUTES.find(x => x.id === id) || ROUTES[0];
  hq?.dispose(); hq = null;
  renderNav(r.id);
  $('title').textContent = r.label;
  $('crumb').textContent = `ilk.medater groupe · ${r.group}`;
  const view = $('view');
  if (!r.ok()) {
    clear(view, el('div', { class: 'card empty' }, 'Cet espace ne vous est pas ouvert. Les autorisations sont attribuées exclusivement par le Directeur général.'));
    return;
  }
  clear(view, el('div', { class: 'muted' }, 'Chargement…'));
  invalidateRefs();
  try { await r.render(view); }
  catch (e) { if (!(e instanceof ApiError && e.status === 401)) clear(view, el('div', { class: 'notice' }, e.message || String(e))); }
}
window.addEventListener('hashchange', route);

// ------------------------------------------------------------------ Siège 3D
async function renderHQ(host) {
  const building = await api('/building');
  const viewer = el('div', { class: 'viewer', id: 'viewer' },
    el('div', { class: 'hud', id: 'hud' }, 'ILK.MEDATER — SIÈGE VIRTUEL · tous les niveaux'),
    el('div', { class: 'help' }, 'Glisser : tourner · Molette : zoom · Clic sur un bureau : ouvrir le module'));
  const info = el('div', { class: 'stack' });
  const officeList = el('div', { class: 'office-list' });
  const listFor = level => {
    const items = building.offices.filter(o => level === 'all' || o.floor === level);
    clear(officeList, items.map(o => el('button', { type: 'button', onclick: () => openOffice(o) }, el('span', {}, o.name),
      el('span', { class: 'pill ' + (o.accessible ? 'ok' : '') }, o.accessible ? 'ouvert' : 'verrouillé'))));
  };
  const elevator = el('div', { class: 'elevator' },
    [...building.floors].reverse().map(f => el('button', { class: 'btn ghost', type: 'button', onclick: () => hq.showFloor(f.level) }, f.name)),
    el('button', { class: 'btn ghost', type: 'button', onclick: () => hq.reset() }, 'Vue d\'ensemble du bâtiment'));
  function openOffice(o) {
    if (!o.accessible) {
      clear(info, el('div', { class: 'notice' }, `${o.name} : accès non autorisé. Seul le Directeur général peut vous ouvrir ce bureau.`));
      return;
    }
    location.hash = `#/${OFFICE_ROUTE[o.module] || o.module}`;
  }
  clear(host, el('div', { class: 'hq' }, el('div', { class: 'card' }, viewer),
    el('div', { class: 'card stack' }, el('h2', {}, 'Ascenseur'), elevator, el('h3', {}, 'Bureaux'), officeList, info,
      el('p', { class: 'muted' }, 'Le siège et les tableaux de bord classiques fonctionnent en parallèle : le menu de gauche donne accès aux mêmes modules.'))));
  try {
    const { mountHQ } = await import('./siege3d.js');
    hq = mountHQ(viewer, building, {
      onOffice: openOffice,
      onFloorChange: f => { $('hud').textContent = 'ILK.MEDATER — SIÈGE VIRTUEL · ' + (f === 'all' ? 'tous les niveaux' : building.floors[f].name); listFor(f); },
    });
  } catch (e) {
    clear(viewer, el('div', { class: 'empty', style: 'color:#dbe6f5' }, 'Le rendu 3D (WebGL) n\'est pas disponible sur ce poste. Utilisez la liste des bureaux ou le menu.'));
  }
  listFor('all');
}

// ------------------------------------------------------------------ Démarrage
async function boot() {
  try { me = await api('/auth/me'); }
  catch (e) {
    if (e.status === 403 && /mot de passe/i.test(e.message)) { $('login').hidden = false; $('app').hidden = true; return passwordStep(); }
    return showLogin();
  }
  $('login').hidden = true; $('app').hidden = false;
  $('who').textContent = `${me.full_name || me.email}${me.is_group_director ? ' · Directeur général' : ''}`;
  $('side-foot').textContent = `IA : ${me.ai_local ? 'locale' : '—'}${me.ai_cloud ? ' + cloud' : ''} · MFA ${me.mfa_enabled ? 'active' : 'inactive'}`;
  route();
}
boot();
