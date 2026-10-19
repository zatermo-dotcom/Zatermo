// Vues métier génériques : un tableau + un formulaire par ressource, regroupés en onglets par module.
// L'interface masque ce qui n'est pas autorisé, mais c'est l'API qui contrôle chaque requête.
import { api, clear, day, el, field, guard, money, num, pill, table } from './core.js';

const refCache = new Map();
async function refList(path) {
  if (!refCache.has(path)) refCache.set(path, api(path).catch(() => []));
  return refCache.get(path);
}
export function invalidateRefs() { refCache.clear(); }

const REFS = {
  company: { path: '/org', pick: d => d.companies, label: c => c.name },
  project: { path: '/projects', label: p => `${p.code} — ${p.name}` },
  party: { path: '/parties', label: p => `${p.name} (${p.kind})` },
  supplier: { path: '/parties', label: p => `${p.name} (${p.kind})`, filter: p => ['fournisseur', 'sous-traitant'].includes(p.kind) },
  site: { path: '/sites', label: s => s.name },
  contract: { path: '/contracts', label: c => `${c.reference} — ${c.title}` },
  invoice: { path: '/invoices', label: i => `${i.number} (${i.direction})` },
  item: { path: '/stock-items', label: i => `${i.code} — ${i.name}` },
  employee: { path: '/employees', label: e => `${e.matricule} — ${e.full_name}` },
  unit: { path: '/org', pick: d => d.units.filter(u => u.modules.length), label: u => u.name, value: u => u.code },
};

async function refOptions(kind) {
  const r = REFS[kind];
  let data = await refList(r.path);
  if (r.pick) data = r.pick(data);
  if (r.filter) data = data.filter(r.filter);
  return data.map(x => ({ value: r.value ? r.value(x) : x.id, label: r.label(x) }));
}

async function refLabel(kind, id) {
  if (id === null || id === undefined) return '—';
  const opts = await refOptions(kind);
  return opts.find(o => String(o.value) === String(id))?.label ?? `#${id}`;
}

const opt = (...values) => values.map(v => ({ value: v, label: v.replaceAll('_', ' ') }));

// --- Définition des ressources -----------------------------------------------------------------
export const RES = {
  parties: { path: '/parties', title: 'Clients et fournisseurs', module: 'crm',
    cols: [{ key: 'name', label: 'Nom' }, { key: 'kind', label: 'Type', pill: 1 }, { key: 'company_id', label: 'Filiale', ref: 'company' },
      { key: 'wilaya', label: 'Wilaya' }, { key: 'phone', label: 'Téléphone' }, { key: 'nif', label: 'NIF' }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'kind', label: 'Type', options: opt('client', 'fournisseur', 'sous-traitant', 'partenaire', 'administration') },
      { key: 'name', label: 'Raison sociale', req: 1 }, { key: 'nif', label: 'NIF' }, { key: 'rc', label: 'RC' }, { key: 'wilaya', label: 'Wilaya' },
      { key: 'address', label: 'Adresse' }, { key: 'phone', label: 'Téléphone' }, { key: 'email', label: 'Email' }] },

  projects: { path: '/projects', title: 'Projets', module: 'projects',
    cols: [{ key: 'code', label: 'Code' }, { key: 'name', label: 'Projet' }, { key: 'company_id', label: 'Filiale', ref: 'company' },
      { key: 'phase', label: 'Phase', pill: 1, edit: opt('ESQ', 'APS', 'APD', 'DCE', 'EXE', 'CHANTIER', 'RECEPTION', 'CLOS') },
      { key: 'status', label: 'Statut', pill: 1, edit: opt('prospect', 'en_cours', 'suspendu', 'receptionne', 'clos') },
      { key: 'planned_end_date', label: 'Fin prévue', date: 1 }, { key: 'budget_amount', label: 'Budget', money: 1 },
      { key: 'late', label: 'Alerte', render: r => r.late ? pill('en_retard') : '' }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'code', label: 'Code', req: 1 }, { key: 'name', label: 'Intitulé', req: 1 },
      { key: 'kind', label: 'Nature', options: opt('etude', 'realisation', 'mixte') }, { key: 'org_unit_code', label: 'Département responsable', ref: 'unit' },
      { key: 'client_id', label: 'Client', ref: 'party' }, { key: 'wilaya', label: 'Wilaya' }, { key: 'start_date', label: 'Début', type: 'date' },
      { key: 'planned_end_date', label: 'Fin prévue', type: 'date' }, { key: 'budget_amount', label: 'Budget (DA)', type: 'number' },
      { key: 'description', label: 'Description', type: 'textarea' }] },

  milestones: { path: '/milestones', title: 'Jalons', module: 'projects',
    cols: [{ key: 'project_id', label: 'Projet', ref: 'project' }, { key: 'name', label: 'Jalon' }, { key: 'planned_date', label: 'Prévu', date: 1 },
      { key: 'status', label: 'Statut', pill: 1, edit: opt('a_faire', 'en_cours', 'fait', 'en_retard') }],
    form: [{ key: 'project_id', label: 'Projet', ref: 'project', req: 1 }, { key: 'name', label: 'Jalon', req: 1 }, { key: 'planned_date', label: 'Date prévue', type: 'date' }] },

  sites: { path: '/sites', title: 'Chantiers', module: 'sites',
    cols: [{ key: 'name', label: 'Chantier' }, { key: 'project_id', label: 'Projet', ref: 'project' },
      { key: 'physical_progress', label: 'Avancement %', num: 1, editNum: 1 }, { key: 'planned_end_date', label: 'Fin prévue', date: 1 },
      { key: 'status', label: 'Statut', pill: 1, edit: opt('installation', 'en_cours', 'arrete', 'receptionne') }],
    form: [{ key: 'project_id', label: 'Projet', ref: 'project', req: 1 }, { key: 'name', label: 'Nom du chantier', req: 1 }, { key: 'address', label: 'Adresse' },
      { key: 'start_date', label: 'Début', type: 'date' }, { key: 'planned_end_date', label: 'Fin prévue', type: 'date' }] },

  'daily-reports': { path: '/daily-reports', title: 'Journal de chantier', module: 'sites',
    cols: [{ key: 'report_date', label: 'Date', date: 1 }, { key: 'site_id', label: 'Chantier', ref: 'site' }, { key: 'workforce', label: 'Effectif', num: 1 },
      { key: 'work_done', label: 'Travaux réalisés' }, { key: 'incidents', label: 'Incidents' }],
    form: [{ key: 'site_id', label: 'Chantier', ref: 'site', req: 1 }, { key: 'report_date', label: 'Date', type: 'date', req: 1 }, { key: 'weather', label: 'Météo' },
      { key: 'workforce', label: 'Effectif', type: 'number' }, { key: 'equipment', label: 'Matériel présent' }, { key: 'work_done', label: 'Travaux réalisés', type: 'textarea', req: 1 },
      { key: 'incidents', label: 'Incidents', type: 'textarea' }, { key: 'hse_notes', label: 'Observations HSE', type: 'textarea' }] },

  'site-risks': { path: '/site-risks', title: 'Risques', module: 'sites',
    cols: [{ key: 'title', label: 'Risque' }, { key: 'site_id', label: 'Chantier', ref: 'site' }, { key: 'level', label: 'Niveau', pill: 1 },
      { key: 'status', label: 'Statut', pill: 1, edit: opt('ouvert', 'maitrise', 'clos') }, { key: 'due_date', label: 'Échéance', date: 1 }],
    form: [{ key: 'site_id', label: 'Chantier', ref: 'site', req: 1 }, { key: 'title', label: 'Risque', req: 1 }, { key: 'level', label: 'Niveau', options: opt('faible', 'moyen', 'eleve', 'critique') },
      { key: 'mitigation', label: 'Mesures', type: 'textarea' }, { key: 'due_date', label: 'Échéance', type: 'date' }] },

  contracts: { path: '/contracts', title: 'Marchés et contrats', module: 'contracts',
    cols: [{ key: 'reference', label: 'Référence' }, { key: 'title', label: 'Objet' }, { key: 'company_id', label: 'Filiale', ref: 'company' },
      { key: 'amount_ht', label: 'Montant HT', money: 1 }, { key: 'status', label: 'Statut', pill: 1, edit: opt('en_preparation', 'en_cours', 'suspendu', 'receptionne', 'clos', 'resilie') },
      { key: 'schedule', label: 'Fin recalculée', render: r => day(r.schedule?.planned_end_date) },
      { key: 'schedule', label: 'Retard / pénalités', render: r => r.schedule?.delay_days ? el('span', {}, pill('en_retard'), ` ${r.schedule.delay_days} j · ${money(r.schedule.theoretical_penalty)}`) : '—' }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'project_id', label: 'Projet', ref: 'project' }, { key: 'party_id', label: 'Maître d\'ouvrage / tiers', ref: 'party' },
      { key: 'reference', label: 'Référence', req: 1 }, { key: 'title', label: 'Objet', req: 1 }, { key: 'kind', label: 'Type', options: opt('marche_public', 'marche_prive', 'sous_traitance', 'etudes', 'fourniture') },
      { key: 'amount_ht', label: 'Montant HT (DA)', type: 'number' }, { key: 'tva_rate', label: 'TVA %', type: 'number', value: 19 },
      { key: 'retention_rate', label: 'Retenue de garantie %', type: 'number', value: 5 }, { key: 'penalty_per_day_rate', label: 'Pénalité % / jour', type: 'number' },
      { key: 'penalty_cap_rate', label: 'Plafond pénalités %', type: 'number', value: 10 }, { key: 'signed_date', label: 'Signature', type: 'date' },
      { key: 'ods_start_date', label: 'ODS de démarrage', type: 'date' }, { key: 'duration_days', label: 'Délai (jours)', type: 'number' }] },

  'contract-events': { path: '/contract-events', title: 'ODS, avenants, réclamations', module: 'contracts',
    cols: [{ key: 'event_date', label: 'Date', date: 1 }, { key: 'contract_id', label: 'Marché', ref: 'contract' }, { key: 'kind', label: 'Événement', pill: 1 },
      { key: 'reference', label: 'Référence' }, { key: 'days_delta', label: 'Δ jours', num: 1 }, { key: 'amount_delta', label: 'Δ montant', money: 1 }],
    form: [{ key: 'contract_id', label: 'Marché', ref: 'contract', req: 1 }, { key: 'kind', label: 'Type', options: opt('ods_demarrage', 'ods_arret', 'ods_reprise', 'avenant', 'reclamation', 'mise_en_demeure', 'reception_provisoire', 'reception_definitive', 'autre') },
      { key: 'reference', label: 'Référence' }, { key: 'event_date', label: 'Date', type: 'date', req: 1 }, { key: 'days_delta', label: 'Δ délai (jours)', type: 'number' },
      { key: 'amount_delta', label: 'Δ montant (DA)', type: 'number' }, { key: 'description', label: 'Description', type: 'textarea' }] },

  situations: { path: '/situations', title: 'Situations de travaux', module: 'contracts',
    cols: [{ key: 'contract_id', label: 'Marché', ref: 'contract' }, { key: 'number', label: 'N°', num: 1 }, { key: 'period_end', label: 'Arrêtée au', date: 1 },
      { key: 'cumulative_amount_ht', label: 'Cumul HT', money: 1 }, { key: 'period_ht', label: 'Période HT', money: 1 }, { key: 'retention', label: 'Retenue', money: 1 },
      { key: 'net_to_pay', label: 'Net à payer TTC', money: 1 }, { key: 'financial_progress_pct', label: 'Avancement financier %', num: 1 },
      { key: 'status', label: 'Statut', pill: 1, edit: opt('brouillon', 'soumise', 'validee', 'payee', 'rejetee') }],
    form: [{ key: 'contract_id', label: 'Marché', ref: 'contract', req: 1 }, { key: 'number', label: 'Numéro', type: 'number', req: 1 },
      { key: 'period_end', label: 'Arrêtée au', type: 'date', req: 1 }, { key: 'cumulative_amount_ht', label: 'Cumul HT (DA)', type: 'number', req: 1 }] },

  invoices: { path: '/invoices', title: 'Factures', module: 'finance',
    cols: [{ key: 'number', label: 'N°' }, { key: 'direction', label: 'Sens', pill: 1 }, { key: 'party_id', label: 'Tiers', ref: 'party' },
      { key: 'issue_date', label: 'Émise', date: 1 }, { key: 'due_date', label: 'Échéance', date: 1 }, { key: 'amount_ttc', label: 'TTC', money: 1 },
      { key: 'balance', label: 'Solde', money: 1 }, { key: 'payment_status', label: 'Règlement', render: r => el('span', {}, pill(r.payment_status), r.overdue ? ` +${r.days_overdue} j` : '') },
      { key: 'status', label: 'Statut', pill: 1, edit: opt('brouillon', 'emise', 'annulee') }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'direction', label: 'Sens', options: opt('vente', 'achat') }, { key: 'party_id', label: 'Tiers', ref: 'party', req: 1 },
      { key: 'project_id', label: 'Projet', ref: 'project' }, { key: 'contract_id', label: 'Marché', ref: 'contract' }, { key: 'number', label: 'Numéro', req: 1 },
      { key: 'issue_date', label: 'Date', type: 'date', req: 1 }, { key: 'due_date', label: 'Échéance', type: 'date' }, { key: 'amount_ht', label: 'Montant HT (DA)', type: 'number', req: 1 },
      { key: 'tva_rate', label: 'TVA %', type: 'number', value: 19 }, { key: 'description', label: 'Libellé', type: 'textarea' }] },

  payments: { path: '/payments', title: 'Encaissements et paiements', module: 'finance',
    cols: [{ key: 'paid_date', label: 'Date', date: 1 }, { key: 'invoice_id', label: 'Facture', ref: 'invoice' }, { key: 'amount', label: 'Montant', money: 1 },
      { key: 'method', label: 'Mode', pill: 1 }, { key: 'reference', label: 'Référence' }],
    form: [{ key: 'invoice_id', label: 'Facture', ref: 'invoice', req: 1 }, { key: 'paid_date', label: 'Date', type: 'date', req: 1 }, { key: 'amount', label: 'Montant TTC (DA)', type: 'number', req: 1 },
      { key: 'method', label: 'Mode', options: opt('virement', 'cheque', 'especes', 'compensation') }, { key: 'reference', label: 'Référence' }] },

  'purchase-orders': { path: '/purchase-orders', title: 'Bons de commande', module: 'procurement',
    cols: [{ key: 'number', label: 'N°' }, { key: 'supplier_id', label: 'Fournisseur', ref: 'party' }, { key: 'project_id', label: 'Projet', ref: 'project' },
      { key: 'order_date', label: 'Date', date: 1 }, { key: 'total_ht', label: 'Total HT', money: 1 }, { key: 'status', label: 'Statut', pill: 1, edit: opt('brouillon', 'validee', 'livree', 'annulee') }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'supplier_id', label: 'Fournisseur', ref: 'supplier', req: 1 }, { key: 'project_id', label: 'Projet', ref: 'project' },
      { key: 'number', label: 'Numéro', req: 1 }, { key: 'order_date', label: 'Date', type: 'date', req: 1 }, { key: 'total_ht', label: 'Total HT (DA)', type: 'number' },
      { key: 'description', label: 'Désignation', type: 'textarea' }] },

  'stock-items': { path: '/stock-items', title: 'Articles en stock', module: 'procurement',
    cols: [{ key: 'code', label: 'Code' }, { key: 'name', label: 'Article' }, { key: 'quantity', label: 'Quantité', num: 1 }, { key: 'unit', label: 'Unité' },
      { key: 'min_quantity', label: 'Seuil', num: 1 }, { key: 'below_min', label: 'Alerte', render: r => r.below_min ? pill('critique') : '' }, { key: 'location', label: 'Magasin' }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'code', label: 'Code', req: 1 }, { key: 'name', label: 'Désignation', req: 1 },
      { key: 'unit', label: 'Unité', value: 'u' }, { key: 'min_quantity', label: 'Seuil d\'alerte', type: 'number' }, { key: 'location', label: 'Magasin' }] },

  'stock-movements': { path: '/stock-movements', title: 'Mouvements de stock', module: 'procurement',
    cols: [{ key: 'moved_at', label: 'Date', date: 1 }, { key: 'item_id', label: 'Article', ref: 'item' }, { key: 'kind', label: 'Type', pill: 1 },
      { key: 'quantity', label: 'Quantité', num: 1 }, { key: 'site_id', label: 'Chantier', ref: 'site' }, { key: 'reference', label: 'Référence' }],
    form: [{ key: 'item_id', label: 'Article', ref: 'item', req: 1 }, { key: 'kind', label: 'Type', options: opt('entree', 'sortie', 'ajustement') },
      { key: 'quantity', label: 'Quantité', type: 'number', req: 1 }, { key: 'site_id', label: 'Chantier', ref: 'site' }, { key: 'reference', label: 'Bon / référence' }] },

  equipment: { path: '/equipment', title: 'Parc matériel', module: 'equipment',
    cols: [{ key: 'code', label: 'Code' }, { key: 'name', label: 'Matériel' }, { key: 'category', label: 'Catégorie' },
      { key: 'status', label: 'Statut', pill: 1, edit: opt('disponible', 'affecte', 'maintenance', 'hors_service') }, { key: 'site_id', label: 'Chantier', ref: 'site' },
      { key: 'next_maintenance_date', label: 'Prochaine maintenance', date: 1 }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'code', label: 'Code', req: 1 }, { key: 'name', label: 'Désignation', req: 1 },
      { key: 'category', label: 'Catégorie' }, { key: 'site_id', label: 'Chantier', ref: 'site' }, { key: 'next_maintenance_date', label: 'Prochaine maintenance', type: 'date' }] },

  employees: { path: '/employees', title: 'Personnel', module: 'hr',
    cols: [{ key: 'matricule', label: 'Matricule' }, { key: 'full_name', label: 'Nom' }, { key: 'job_title', label: 'Fonction' },
      { key: 'org_unit_code', label: 'Département', ref: 'unit' }, { key: 'contract_type', label: 'Contrat', pill: 1 }, { key: 'status', label: 'Statut', pill: 1, edit: opt('actif', 'suspendu', 'sorti') }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'org_unit_code', label: 'Département', ref: 'unit' }, { key: 'matricule', label: 'Matricule', req: 1 },
      { key: 'full_name', label: 'Nom et prénom', req: 1 }, { key: 'job_title', label: 'Fonction' }, { key: 'contract_type', label: 'Contrat', options: opt('CDI', 'CDD', 'stage', 'journalier', 'consultant') },
      { key: 'hire_date', label: 'Embauche', type: 'date' }, { key: 'phone', label: 'Téléphone' }, { key: 'email', label: 'Email' }] },

  'leave-requests': { path: '/leave-requests', title: 'Congés', module: 'hr',
    cols: [{ key: 'employee_id', label: 'Salarié', ref: 'employee' }, { key: 'kind', label: 'Type', pill: 1 }, { key: 'start_date', label: 'Du', date: 1 },
      { key: 'end_date', label: 'Au', date: 1 }, { key: 'status', label: 'Décision', pill: 1, edit: opt('demandee', 'acceptee', 'refusee', 'annulee') }],
    form: [{ key: 'employee_id', label: 'Salarié', ref: 'employee', req: 1 }, { key: 'kind', label: 'Type', options: opt('conge_annuel', 'maladie', 'recuperation', 'sans_solde', 'autre') },
      { key: 'start_date', label: 'Du', type: 'date', req: 1 }, { key: 'end_date', label: 'Au', type: 'date', req: 1 }] },

  'qhse-events': { path: '/qhse-events', title: 'Qualité et HSE', module: 'qhse',
    cols: [{ key: 'found_date', label: 'Date', date: 1 }, { key: 'kind', label: 'Type', pill: 1 }, { key: 'title', label: 'Constat' }, { key: 'site_id', label: 'Chantier', ref: 'site' },
      { key: 'severity', label: 'Gravité', pill: 1 }, { key: 'status', label: 'Statut', pill: 1, edit: opt('ouvert', 'action_en_cours', 'clos') }],
    form: [{ key: 'company_id', label: 'Filiale', ref: 'company', req: 1 }, { key: 'site_id', label: 'Chantier', ref: 'site' }, { key: 'project_id', label: 'Projet', ref: 'project' },
      { key: 'kind', label: 'Type', options: opt('non_conformite', 'inspection', 'incident', 'accident', 'observation') }, { key: 'title', label: 'Constat', req: 1 },
      { key: 'severity', label: 'Gravité', options: opt('mineure', 'majeure', 'critique') }, { key: 'found_date', label: 'Date', type: 'date', req: 1 },
      { key: 'description', label: 'Description', type: 'textarea' }, { key: 'action', label: 'Action corrective', type: 'textarea' }] },

  'coordination-issues': { path: '/coordination-issues', title: 'Synthèse et conflits MEP', module: 'studies',
    cols: [{ key: 'project_id', label: 'Projet', ref: 'project' }, { key: 'title', label: 'Point' }, { key: 'disciplines', label: 'Spécialités', render: r => r.disciplines.join(' · ') },
      { key: 'kind', label: 'Type', pill: 1 }, { key: 'priority', label: 'Priorité', pill: 1 }, { key: 'status', label: 'Statut', pill: 1, edit: opt('ouvert', 'en_cours', 'resolu', 'clos') }],
    form: [{ key: 'project_id', label: 'Projet', ref: 'project', req: 1 }, { key: 'title', label: 'Description courte', req: 1 }, { key: 'location', label: 'Localisation (niveau, axe)' },
      { key: 'disciplines', label: 'Spécialités (ex. CFO,HVAC)', list: 1, req: 1 }, { key: 'kind', label: 'Type', options: opt('conflit', 'reservation', 'incoherence', 'question') },
      { key: 'priority', label: 'Priorité', options: opt('basse', 'normale', 'haute', 'bloquante') }] },
};

// --- Rendu -------------------------------------------------------------------------------------
async function input(f) {
  let node;
  if (f.ref) {
    const opts = await refOptions(f.ref);
    node = el('select', { name: f.key }, f.req ? null : el('option', { value: '' }, '—'), opts.map(o => el('option', { value: o.value }, o.label)));
  } else if (f.options) node = el('select', { name: f.key }, f.options.map(o => el('option', { value: o.value }, o.label)));
  else if (f.type === 'textarea') node = el('textarea', { name: f.key, maxlength: 5000 });
  else node = el('input', { name: f.key, type: f.type || 'text', step: f.type === 'number' ? 'any' : null, required: f.req ? true : null, value: f.value ?? null });
  return field(f.label + (f.req ? ' *' : ''), node);
}

function collect(form, fields) {
  const out = {};
  for (const f of fields) {
    const v = form.elements[f.key].value.trim();
    if (v === '') continue;
    if (f.list) out[f.key] = v.split(/[,;\s]+/).filter(Boolean).map(s => s.toUpperCase());
    else if (f.ref && f.ref !== 'unit') out[f.key] = Number(v);
    else if (f.type === 'number') out[f.key] = f.key === 'number' || f.key.endsWith('_days') || f.key === 'workforce' || f.key === 'days_delta' ? Number(v) : v;
    else out[f.key] = v;
  }
  return out;
}

async function cell(c, r, res, reload, canEdit) {
  const v = r[c.key];
  if (c.render) return c.render(r);
  if (c.edit && canEdit) {
    const s = el('select', { class: 'sm', 'aria-label': c.label }, c.edit.map(o => el('option', { value: o.value, selected: o.value === v }, o.label)));
    s.addEventListener('change', () => guard(() => api(`${res.path}/${r.id}`, { method: 'PATCH', body: { [c.key]: s.value } }), 'Enregistré').then(reload, reload));
    return s;
  }
  if (c.editNum && canEdit) {
    const i = el('input', { type: 'number', min: 0, max: 100, step: 1, value: v, style: 'width:80px' });
    i.addEventListener('change', () => guard(() => api(`${res.path}/${r.id}`, { method: 'PATCH', body: { [c.key]: i.value } }), 'Enregistré').then(reload, reload));
    return i;
  }
  if (c.ref) return refLabel(c.ref, v);
  if (c.pill) return pill(v);
  if (c.money) return money(v);
  if (c.date) return day(v);
  if (c.num) return num(v);
  return v;
}

export async function renderResource(host, key, me) {
  const res = RES[key];
  const caps = me.modules[res.module] || {};
  const canEdit = caps.edit;
  const list = el('div');
  const reload = async () => {
    const rows = await api(res.path).catch(e => { clear(list, el('div', { class: 'notice' }, e.message)); return null; });
    if (!rows) return;
    const resolved = await Promise.all(rows.map(async r => {
      const o = { ...r };
      for (const c of res.cols) o['__' + res.cols.indexOf(c)] = await cell(c, r, res, reload, canEdit);
      return o;
    }));
    clear(list, table(res.cols.map((c, i) => ({ label: c.label, num: c.num || c.money, render: r => r['__' + i] })), resolved));
  };
  const head = el('div', { class: 'row between' }, el('h2', {}, res.title));
  const box = el('div', { class: 'card stack' }, head);
  if (canEdit) {
    const form = el('form', { class: 'form-grid' });
    for (const f of res.form) form.append(await input(f));
    form.append(el('button', { class: 'btn', type: 'submit' }, 'Enregistrer'));
    form.addEventListener('submit', async e => {
      e.preventDefault();
      await guard(() => api(res.path, { method: 'POST', body: collect(form, res.form) }), 'Créé');
      form.reset(); invalidateRefs(); reload();
    });
    const det = el('details', {}, el('summary', {}, 'Nouveau'), el('div', { style: 'margin-top:10px' }, form));
    box.append(det);
  }
  box.append(list);
  clear(host, box);
  await reload();
}

// Onglets d'un module
export function tabs(host, items, me) {
  const bar = el('div', { class: 'row', role: 'tablist', style: 'margin-bottom:12px' });
  const body = el('div');
  const show = async key => {
    bar.querySelectorAll('button').forEach(b => b.classList.toggle('ghost', b.dataset.k !== key));
    const item = items.find(i => i.key === key);
    if (item.render) await item.render(body, me); else await renderResource(body, key, me);
  };
  for (const it of items) bar.append(el('button', { class: 'btn ghost', type: 'button', dataset: { k: it.key }, onclick: () => show(it.key) }, it.label || RES[it.key].title));
  clear(host, bar, body);
  return show(items[0].key);
}
