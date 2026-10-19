-- ilk.medater Cloud — schéma initial (V1.0)
-- Exécuté par le rôle propriétaire (migrations). L'application se connecte avec le rôle ilk_app (droits restreints, cf. 003).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------- Organisation
CREATE TABLE companies (
  id          serial PRIMARY KEY,
  code        text NOT NULL UNIQUE CHECK (code IN ('CONST','ARCH')),
  name        text NOT NULL,
  legal_name  text,
  nif         text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE org_units (
  code          text PRIMARY KEY,
  parent_code   text REFERENCES org_units(code),
  company_code  text NOT NULL CHECK (company_code IN ('GROUP','CONST','ARCH')),
  name          text NOT NULL,
  kind          text NOT NULL CHECK (kind IN ('group','subsidiary','direction','department','specialty','coordination','shared_service','service')),
  floor         int  CHECK (floor BETWEEN 0 AND 2),
  modules       text[] NOT NULL DEFAULT '{}',
  sort          int NOT NULL DEFAULT 0,
  active        boolean NOT NULL DEFAULT true
);

-- ---------------------------------------------------------------- Identité et sécurité
CREATE TABLE users (
  id                  serial PRIMARY KEY,
  email               text NOT NULL,
  full_name           text NOT NULL DEFAULT '',
  job_title           text NOT NULL DEFAULT '',
  org_unit_code       text REFERENCES org_units(code),
  password_hash       text NOT NULL,
  enabled             boolean NOT NULL DEFAULT true,
  is_group_director   boolean NOT NULL DEFAULT false,
  mfa_enabled         boolean NOT NULL DEFAULT false,
  mfa_secret_enc      text,
  failed_logins       int NOT NULL DEFAULT 0,
  locked_until        timestamptz,
  must_change_password boolean NOT NULL DEFAULT true,
  password_changed_at timestamptz,
  last_login_at       timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_lower ON users (lower(email));
-- Un seul Directeur général du groupe.
CREATE UNIQUE INDEX users_single_director ON users ((is_group_director)) WHERE is_group_director;

CREATE TABLE recovery_codes (
  id         serial PRIMARY KEY,
  user_id    int NOT NULL REFERENCES users(id),
  code_hash  text NOT NULL,
  used_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       int NOT NULL REFERENCES users(id),
  token_hash    text NOT NULL UNIQUE,
  mfa_verified  boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL,
  revoked_at    timestamptz,
  ip            text,
  user_agent    text
);
CREATE INDEX sessions_user ON sessions(user_id);

-- Autorisations granulaires. Seul le Directeur général peut en créer (trigger en 003).
CREATE TABLE grants (
  id          serial PRIMARY KEY,
  user_id     int NOT NULL REFERENCES users(id),
  company_id  int REFERENCES companies(id),
  scope_type  text NOT NULL CHECK (scope_type IN ('company','org_unit','module','project','document')),
  scope_ref   text NOT NULL,
  actions     text[] NOT NULL CHECK (array_length(actions,1) >= 1 AND actions <@ ARRAY['view','edit','validate','export']::text[]),
  status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','revoked')),
  expires_at  timestamptz,
  note        text NOT NULL DEFAULT '',
  granted_by  int NOT NULL REFERENCES users(id),
  changed_by  int NOT NULL REFERENCES users(id),
  granted_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  revoked_at  timestamptz,
  CHECK (scope_type NOT IN ('company','module') OR company_id IS NOT NULL)
);
CREATE INDEX grants_user ON grants(user_id) WHERE status = 'active';

CREATE TABLE ai_settings (
  user_id        int PRIMARY KEY REFERENCES users(id),
  local_enabled  boolean NOT NULL DEFAULT false,
  cloud_enabled  boolean NOT NULL DEFAULT false,
  updated_by     int NOT NULL REFERENCES users(id),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_consents (
  id              serial PRIMARY KEY,
  user_id         int NOT NULL REFERENCES users(id),
  policy_version  text NOT NULL,
  accepted_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_requests (
  id              bigserial PRIMARY KEY,
  user_id         int NOT NULL REFERENCES users(id),
  assistant_code  text NOT NULL,
  engine          text NOT NULL,
  company_id      int REFERENCES companies(id),
  project_id      int,
  question        text NOT NULL,
  answer          text NOT NULL,
  sources         jsonb NOT NULL DEFAULT '[]',
  redactions      int NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Journal d'audit chaîné (hash). Écriture uniquement via audit_append() (003).
CREATE TABLE audit_events (
  id          bigserial PRIMARY KEY,
  at          timestamptz NOT NULL DEFAULT clock_timestamp(),
  actor_id    int REFERENCES users(id),
  action      text NOT NULL,
  resource    text NOT NULL DEFAULT '',
  company_id  int REFERENCES companies(id),
  details     jsonb NOT NULL DEFAULT '{}',
  ip          text,
  prev_hash   text NOT NULL,
  hash        text NOT NULL UNIQUE
);

-- ---------------------------------------------------------------- CRM
CREATE TABLE parties (
  id          serial PRIMARY KEY,
  company_id  int NOT NULL REFERENCES companies(id),
  kind        text NOT NULL CHECK (kind IN ('client','fournisseur','sous-traitant','partenaire','administration')),
  name        text NOT NULL,
  nif         text NOT NULL DEFAULT '',
  rc          text NOT NULL DEFAULT '',
  wilaya      text NOT NULL DEFAULT '',
  address     text NOT NULL DEFAULT '',
  phone       text NOT NULL DEFAULT '',
  email       text NOT NULL DEFAULT '',
  notes       text NOT NULL DEFAULT '',
  created_by  int REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX parties_company ON parties(company_id);

-- ---------------------------------------------------------------- Projets
CREATE TABLE projects (
  id                 serial PRIMARY KEY,
  company_id         int NOT NULL REFERENCES companies(id),
  org_unit_code      text REFERENCES org_units(code),
  code               text NOT NULL,
  name               text NOT NULL,
  kind               text NOT NULL DEFAULT 'etude' CHECK (kind IN ('etude','realisation','mixte')),
  phase              text NOT NULL DEFAULT 'ESQ' CHECK (phase IN ('ESQ','APS','APD','DCE','EXE','CHANTIER','RECEPTION','CLOS')),
  status             text NOT NULL DEFAULT 'en_cours' CHECK (status IN ('prospect','en_cours','suspendu','receptionne','clos')),
  client_id          int REFERENCES parties(id),
  wilaya             text NOT NULL DEFAULT '',
  start_date         date,
  planned_end_date   date,
  actual_end_date    date,
  budget_amount      numeric(16,2) NOT NULL DEFAULT 0 CHECK (budget_amount >= 0),
  manager_user_id    int REFERENCES users(id),
  description        text NOT NULL DEFAULT '',
  created_by         int REFERENCES users(id),
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, code)
);

CREATE TABLE milestones (
  id            serial PRIMARY KEY,
  project_id    int NOT NULL REFERENCES projects(id),
  company_id    int NOT NULL REFERENCES companies(id),
  name          text NOT NULL,
  planned_date  date,
  done_date     date,
  status        text NOT NULL DEFAULT 'a_faire' CHECK (status IN ('a_faire','en_cours','fait','en_retard'))
);

-- ---------------------------------------------------------------- Chantiers
CREATE TABLE sites (
  id                 serial PRIMARY KEY,
  project_id         int NOT NULL REFERENCES projects(id),
  company_id         int NOT NULL REFERENCES companies(id),
  name               text NOT NULL,
  address            text NOT NULL DEFAULT '',
  conducteur_user_id int REFERENCES users(id),
  start_date         date,
  planned_end_date   date,
  physical_progress  numeric(5,2) NOT NULL DEFAULT 0 CHECK (physical_progress BETWEEN 0 AND 100),
  status             text NOT NULL DEFAULT 'en_cours' CHECK (status IN ('installation','en_cours','arrete','receptionne')),
  created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE site_daily_reports (
  id           serial PRIMARY KEY,
  site_id      int NOT NULL REFERENCES sites(id),
  project_id   int NOT NULL REFERENCES projects(id),
  company_id   int NOT NULL REFERENCES companies(id),
  report_date  date NOT NULL,
  weather      text NOT NULL DEFAULT '',
  workforce    int NOT NULL DEFAULT 0 CHECK (workforce >= 0),
  equipment    text NOT NULL DEFAULT '',
  work_done    text NOT NULL,
  incidents    text NOT NULL DEFAULT '',
  hse_notes    text NOT NULL DEFAULT '',
  author_id    int REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (site_id, report_date)
);

CREATE TABLE site_risks (
  id          serial PRIMARY KEY,
  site_id     int NOT NULL REFERENCES sites(id),
  project_id  int NOT NULL REFERENCES projects(id),
  company_id  int NOT NULL REFERENCES companies(id),
  title       text NOT NULL,
  level       text NOT NULL DEFAULT 'moyen' CHECK (level IN ('faible','moyen','eleve','critique')),
  status      text NOT NULL DEFAULT 'ouvert' CHECK (status IN ('ouvert','maitrise','clos')),
  mitigation  text NOT NULL DEFAULT '',
  due_date    date,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- Contrats et marchés
CREATE TABLE contracts (
  id                    serial PRIMARY KEY,
  company_id            int NOT NULL REFERENCES companies(id),
  project_id            int REFERENCES projects(id),
  party_id              int REFERENCES parties(id),
  reference             text NOT NULL,
  title                 text NOT NULL,
  kind                  text NOT NULL DEFAULT 'marche_public' CHECK (kind IN ('marche_public','marche_prive','sous_traitance','etudes','fourniture')),
  amount_ht             numeric(16,2) NOT NULL DEFAULT 0 CHECK (amount_ht >= 0),
  tva_rate              numeric(5,2) NOT NULL DEFAULT 19 CHECK (tva_rate BETWEEN 0 AND 100),
  retention_rate        numeric(5,2) NOT NULL DEFAULT 5 CHECK (retention_rate BETWEEN 0 AND 100),
  advance_rate          numeric(5,2) NOT NULL DEFAULT 0 CHECK (advance_rate BETWEEN 0 AND 100),
  penalty_per_day_rate  numeric(7,4) NOT NULL DEFAULT 0 CHECK (penalty_per_day_rate >= 0),
  penalty_cap_rate      numeric(5,2) NOT NULL DEFAULT 10 CHECK (penalty_cap_rate BETWEEN 0 AND 100),
  signed_date           date,
  ods_start_date        date,
  duration_days         int CHECK (duration_days > 0),
  status                text NOT NULL DEFAULT 'en_cours' CHECK (status IN ('en_preparation','en_cours','suspendu','receptionne','clos','resilie')),
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, reference)
);

CREATE TABLE contract_events (
  id           serial PRIMARY KEY,
  contract_id  int NOT NULL REFERENCES contracts(id),
  company_id   int NOT NULL REFERENCES companies(id),
  kind         text NOT NULL CHECK (kind IN ('ods_demarrage','ods_arret','ods_reprise','avenant','reclamation','mise_en_demeure','reception_provisoire','reception_definitive','autre')),
  reference    text NOT NULL DEFAULT '',
  event_date   date NOT NULL,
  amount_delta numeric(16,2) NOT NULL DEFAULT 0,
  days_delta   int NOT NULL DEFAULT 0,
  description  text NOT NULL DEFAULT '',
  created_by   int REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE situations (
  id                   serial PRIMARY KEY,
  contract_id          int NOT NULL REFERENCES contracts(id),
  company_id           int NOT NULL REFERENCES companies(id),
  number               int NOT NULL CHECK (number >= 1),
  period_end           date NOT NULL,
  cumulative_amount_ht numeric(16,2) NOT NULL CHECK (cumulative_amount_ht >= 0),
  status               text NOT NULL DEFAULT 'brouillon' CHECK (status IN ('brouillon','soumise','validee','payee','rejetee')),
  created_by           int REFERENCES users(id),
  validated_by         int REFERENCES users(id),
  validated_at         timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (contract_id, number)
);

-- ---------------------------------------------------------------- Finances
CREATE TABLE invoices (
  id           serial PRIMARY KEY,
  company_id   int NOT NULL REFERENCES companies(id),
  party_id     int NOT NULL REFERENCES parties(id),
  project_id   int REFERENCES projects(id),
  contract_id  int REFERENCES contracts(id),
  direction    text NOT NULL CHECK (direction IN ('vente','achat')),
  number       text NOT NULL,
  issue_date   date NOT NULL,
  due_date     date,
  amount_ht    numeric(16,2) NOT NULL CHECK (amount_ht >= 0),
  tva_rate     numeric(5,2) NOT NULL DEFAULT 19 CHECK (tva_rate BETWEEN 0 AND 100),
  status       text NOT NULL DEFAULT 'emise' CHECK (status IN ('brouillon','emise','annulee')),
  description  text NOT NULL DEFAULT '',
  created_by   int REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, direction, number)
);

CREATE TABLE payments (
  id          serial PRIMARY KEY,
  invoice_id  int NOT NULL REFERENCES invoices(id),
  company_id  int NOT NULL REFERENCES companies(id),
  paid_date   date NOT NULL,
  amount      numeric(16,2) NOT NULL CHECK (amount > 0),
  method      text NOT NULL DEFAULT 'virement' CHECK (method IN ('virement','cheque','especes','compensation')),
  reference   text NOT NULL DEFAULT '',
  created_by  int REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- Achats, stocks, matériel
CREATE TABLE purchase_orders (
  id           serial PRIMARY KEY,
  company_id   int NOT NULL REFERENCES companies(id),
  supplier_id  int NOT NULL REFERENCES parties(id),
  project_id   int REFERENCES projects(id),
  number       text NOT NULL,
  order_date   date NOT NULL,
  total_ht     numeric(16,2) NOT NULL DEFAULT 0 CHECK (total_ht >= 0),
  status       text NOT NULL DEFAULT 'brouillon' CHECK (status IN ('brouillon','validee','livree','annulee')),
  description  text NOT NULL DEFAULT '',
  created_by   int REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, number)
);

CREATE TABLE stock_items (
  id            serial PRIMARY KEY,
  company_id    int NOT NULL REFERENCES companies(id),
  code          text NOT NULL,
  name          text NOT NULL,
  unit          text NOT NULL DEFAULT 'u',
  quantity      numeric(14,3) NOT NULL DEFAULT 0,
  min_quantity  numeric(14,3) NOT NULL DEFAULT 0,
  location      text NOT NULL DEFAULT '',
  UNIQUE (company_id, code)
);

CREATE TABLE stock_movements (
  id          serial PRIMARY KEY,
  item_id     int NOT NULL REFERENCES stock_items(id),
  company_id  int NOT NULL REFERENCES companies(id),
  kind        text NOT NULL CHECK (kind IN ('entree','sortie','ajustement')),
  quantity    numeric(14,3) NOT NULL,
  site_id     int REFERENCES sites(id),
  reference   text NOT NULL DEFAULT '',
  author_id   int REFERENCES users(id),
  moved_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE equipment (
  id                     serial PRIMARY KEY,
  company_id             int NOT NULL REFERENCES companies(id),
  code                   text NOT NULL,
  name                   text NOT NULL,
  category               text NOT NULL DEFAULT '',
  status                 text NOT NULL DEFAULT 'disponible' CHECK (status IN ('disponible','affecte','maintenance','hors_service')),
  site_id                int REFERENCES sites(id),
  next_maintenance_date  date,
  hours                  numeric(10,1) NOT NULL DEFAULT 0,
  UNIQUE (company_id, code)
);

-- ---------------------------------------------------------------- RH
CREATE TABLE employees (
  id             serial PRIMARY KEY,
  company_id     int NOT NULL REFERENCES companies(id),
  org_unit_code  text REFERENCES org_units(code),
  matricule      text NOT NULL,
  full_name      text NOT NULL,
  job_title      text NOT NULL DEFAULT '',
  contract_type  text NOT NULL DEFAULT 'CDI' CHECK (contract_type IN ('CDI','CDD','stage','journalier','consultant')),
  hire_date      date,
  end_date       date,
  status         text NOT NULL DEFAULT 'actif' CHECK (status IN ('actif','suspendu','sorti')),
  user_id        int REFERENCES users(id),
  phone          text NOT NULL DEFAULT '',
  email          text NOT NULL DEFAULT '',
  UNIQUE (company_id, matricule)
);

CREATE TABLE leave_requests (
  id           serial PRIMARY KEY,
  employee_id  int NOT NULL REFERENCES employees(id),
  company_id   int NOT NULL REFERENCES companies(id),
  kind         text NOT NULL DEFAULT 'conge_annuel' CHECK (kind IN ('conge_annuel','maladie','recuperation','sans_solde','autre')),
  start_date   date NOT NULL,
  end_date     date NOT NULL,
  status       text NOT NULL DEFAULT 'demandee' CHECK (status IN ('demandee','acceptee','refusee','annulee')),
  decided_by   int REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date >= start_date)
);

-- ---------------------------------------------------------------- Qualité / HSE
CREATE TABLE qhse_events (
  id           serial PRIMARY KEY,
  company_id   int NOT NULL REFERENCES companies(id),
  project_id   int REFERENCES projects(id),
  site_id      int REFERENCES sites(id),
  kind         text NOT NULL CHECK (kind IN ('non_conformite','inspection','incident','accident','observation')),
  title        text NOT NULL,
  severity     text NOT NULL DEFAULT 'mineure' CHECK (severity IN ('mineure','majeure','critique')),
  status       text NOT NULL DEFAULT 'ouvert' CHECK (status IN ('ouvert','action_en_cours','clos')),
  found_date   date NOT NULL,
  closed_date  date,
  description  text NOT NULL DEFAULT '',
  action       text NOT NULL DEFAULT '',
  created_by   int REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- Documents et BIM
CREATE TABLE documents (
  id               serial PRIMARY KEY,
  company_id       int NOT NULL REFERENCES companies(id),
  project_id       int REFERENCES projects(id),
  title            text NOT NULL,
  doc_type         text NOT NULL DEFAULT 'autre' CHECK (doc_type IN ('plan','maquette_ifc','note_calcul','rapport','cctp','contrat','courrier','photo','autre')),
  discipline       text NOT NULL DEFAULT 'GEN',
  confidentiality  text NOT NULL DEFAULT 'interne' CHECK (confidentiality IN ('interne','confidentiel','secret')),
  current_version  int NOT NULL DEFAULT 0,
  created_by       int REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE document_versions (
  id              serial PRIMARY KEY,
  document_id     int NOT NULL REFERENCES documents(id),
  company_id      int NOT NULL REFERENCES companies(id),
  version         int NOT NULL CHECK (version >= 1),
  revision_label  text NOT NULL DEFAULT '',
  filename        text NOT NULL,
  content_type    text NOT NULL,
  size_bytes      bigint NOT NULL CHECK (size_bytes > 0),
  sha256          text NOT NULL,
  storage_path    text NOT NULL,
  metadata        jsonb NOT NULL DEFAULT '{}',
  comment         text NOT NULL DEFAULT '',
  uploaded_by     int REFERENCES users(id),
  uploaded_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, version)
);

-- ---------------------------------------------------------------- Études
CREATE TABLE deliverables (
  id              serial PRIMARY KEY,
  project_id      int NOT NULL REFERENCES projects(id),
  company_id      int NOT NULL REFERENCES companies(id),
  discipline      text NOT NULL,
  phase           text NOT NULL CHECK (phase IN ('ESQ','APS','APD','DCE','EXE','DOE')),
  title           text NOT NULL,
  status          text NOT NULL DEFAULT 'brouillon' CHECK (status IN ('brouillon','soumis','valide','rejete')),
  due_date        date,
  document_id     int REFERENCES documents(id),
  author_id       int REFERENCES users(id),
  submitted_at    timestamptz,
  validator_id    int REFERENCES users(id),
  validated_at    timestamptz,
  review_comment  text NOT NULL DEFAULT '',
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE calc_runs (
  id          serial PRIMARY KEY,
  project_id  int NOT NULL REFERENCES projects(id),
  company_id  int NOT NULL REFERENCES companies(id),
  engine      text NOT NULL,
  engine_version text NOT NULL,
  inputs      jsonb NOT NULL,
  outputs     jsonb NOT NULL,
  warnings    jsonb NOT NULL DEFAULT '[]',
  author_id   int REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE coordination_issues (
  id              serial PRIMARY KEY,
  project_id      int NOT NULL REFERENCES projects(id),
  company_id      int NOT NULL REFERENCES companies(id),
  disciplines     text[] NOT NULL,
  title           text NOT NULL,
  location        text NOT NULL DEFAULT '',
  kind            text NOT NULL DEFAULT 'conflit' CHECK (kind IN ('conflit','reservation','incoherence','question')),
  priority        text NOT NULL DEFAULT 'normale' CHECK (priority IN ('basse','normale','haute','bloquante')),
  status          text NOT NULL DEFAULT 'ouvert' CHECK (status IN ('ouvert','en_cours','resolu','clos')),
  assigned_org_code text REFERENCES org_units(code),
  resolution      text NOT NULL DEFAULT '',
  raised_by       int REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- Juridique
-- Références saisies et vérifiées par un juriste ; l'IA ne cite que cette table.
CREATE TABLE legal_sources (
  id                serial PRIMARY KEY,
  text_type         text NOT NULL CHECK (text_type IN ('loi','ordonnance','decret_presidentiel','decret_executif','arrete','instruction','circulaire','cahier_des_charges','jurisprudence','autre')),
  title             text NOT NULL,
  reference_number  text NOT NULL,
  article           text NOT NULL DEFAULT '',
  publication_date  date,
  jo_reference      text NOT NULL DEFAULT '',
  version_label     text NOT NULL DEFAULT '',
  valid_from        date,
  valid_to          date,
  source_url        text NOT NULL DEFAULT '',
  excerpt           text NOT NULL DEFAULT '',
  keywords          text[] NOT NULL DEFAULT '{}',
  verified_by       int REFERENCES users(id),
  verified_at       timestamptz,
  created_by        int REFERENCES users(id),
  created_at        timestamptz NOT NULL DEFAULT now()
);
