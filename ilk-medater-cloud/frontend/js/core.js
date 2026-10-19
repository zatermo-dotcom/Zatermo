// Utilitaires communs : appels API (cookie de session + en-tête anti-CSRF), construction DOM sûre, formats.

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : formatDetail(detail));
    this.status = status;
  }
}

function formatDetail(detail) {
  if (Array.isArray(detail)) return detail.map(d => `${(d.loc || []).slice(1).join('.')} : ${d.msg}`).join(' ; ');
  return 'Erreur inattendue';
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = { 'x-ilk-csrf': '1' };
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  const r = await fetch('/api' + path, { method, headers, body: payload, credentials: 'same-origin' });
  const isJson = (r.headers.get('content-type') || '').includes('application/json');
  const data = isJson ? await r.json() : null;
  if (!r.ok) {
    const err = new ApiError(r.status, data?.detail ?? `Erreur ${r.status}`);
    if (r.status === 401) document.dispatchEvent(new CustomEvent('ilk:unauthorized', { detail: err.message }));
    throw err;
  }
  return data;
}

// el('div', {class: 'card', onclick: fn}, 'texte', autreNoeud) — le texte passe toujours par textContent.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else if (k === 'class') node.className = v;
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else if (v === true) node.setAttribute(k, '');
    else node.setAttribute(k, String(v));
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function clear(node, ...children) { node.replaceChildren(); children.flat().forEach(c => c && node.append(c)); return node; }

let toastTimer;
export function toast(message, isError = false) {
  const t = document.getElementById('toast');
  t.textContent = message;
  t.className = 'toast show' + (isError ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = 'toast'), 3800);
}

export async function guard(fn, okMessage) {
  try { const r = await fn(); if (okMessage) toast(okMessage); return r; }
  catch (e) { toast(e.message || String(e), true); throw e; }
}

const nf = new Intl.NumberFormat('fr-DZ', { maximumFractionDigits: 2 });
export const money = v => (v === null || v === undefined || v === '') ? '—' : `${nf.format(Number(v))} DA`;
export const num = v => (v === null || v === undefined || v === '') ? '—' : nf.format(Number(v));
export const day = v => v ? new Date(v).toLocaleDateString('fr-DZ') : '—';
export const stamp = v => v ? new Date(v).toLocaleString('fr-DZ') : '—';

const TONES = {
  ok: ['valide', 'validee', 'payee', 'fait', 'receptionne', 'clos', 'resolu', 'livree', 'acceptee', 'actif', 'disponible', 'verifiee', 'active', 'maitrise'],
  warn: ['soumis', 'soumise', 'en_cours', 'partielle', 'brouillon', 'demandee', 'suspendu', 'suspended', 'maintenance', 'moyen', 'majeure', 'action_en_cours', 'installation', 'non_verifiee', 'haute', 'expired'],
  crit: ['rejete', 'rejetee', 'en_retard', 'impayee', 'critique', 'eleve', 'bloquante', 'resilie', 'hors_service', 'revoked', 'annulee', 'refusee', 'abrogee_ou_expiree', 'ouvert', 'arrete'],
};
export function pill(value) {
  const v = String(value ?? '');
  const tone = Object.entries(TONES).find(([, list]) => list.includes(v))?.[0] || '';
  return el('span', { class: `pill ${tone}` }, v.replaceAll('_', ' ') || '—');
}

export function field(label, input) { return el('label', { class: 'field' }, label, input); }

export function table(columns, rows, { empty = 'Aucun enregistrement dans votre périmètre.' } = {}) {
  if (!rows.length) return el('div', { class: 'card empty' }, empty);
  return el('div', { class: 'table-wrap' }, el('table', {},
    el('thead', {}, el('tr', {}, columns.map(c => el('th', {}, c.label)))),
    el('tbody', {}, rows.map(r => el('tr', {}, columns.map(c => {
      const v = c.render ? c.render(r) : r[c.key];
      return el('td', { class: c.num ? 'num' : '' }, v instanceof Node ? v : (v ?? '—'));
    }))))));
}
