# Architecture cible — ilk.medater Cloud 1.0

## Vue d'ensemble

```
 Navigateur (PC DG, puis collaborateurs)                 PC Windows 11 / Docker Desktop (WSL 2)
 ┌──────────────────────────────┐   HTTPS via Tailscale   ┌─────────────────────────────────────────────┐
 │ Interface web (JS natif)     │ ──────────────────────▶ │ web : nginx  (seul port publié, 127.0.0.1)  │
 │ Siège 3D (Three.js local)    │   ou http://localhost   │   CSP, limitation de débit, /api → api      │
 └──────────────────────────────┘                         │ api : FastAPI (rôle SQL restreint ilk_app)  │
                                                          │   sessions, MFA, autorisations, audit       │
                                                          │   moteurs de calcul, IA (routeur)           │
                                                          │ db : PostgreSQL 16 (non exposé)             │
                                                          │ backup : pg_dump + documents, rétention     │
                                                          │ ollama : IA locale (profil facultatif)      │
                                                          └──────────────┬──────────────────────────────┘
                                                                         │ (option, après consentement)
                                                                         ▼  API Claude (masquage préalable)
```

## Couches du backend (`backend/app`)

| Fichier | Rôle |
|---|---|
| `config.py` | Paramètres et secrets (refus de démarrer si un secret fait moins de 32 caractères) |
| `security.py` | Argon2id, jetons de session opaques hachés (HMAC), TOTP chiffré AES-GCM, codes de récupération, limiteur de débit |
| `deps.py` | Session courante, MFA obligatoire pour le DG, changement de mot de passe imposé, garde « Directeur » |
| `authz.py` | **Moteur d'autorisations** : refus par défaut, périmètres et actions, clauses SQL de filtrage |
| `audit.py` | Écriture dans le journal via la fonction SQL `audit_append` |
| `crud.py` + `resources.py` | Routes métier génériques sécurisées (19 ressources), règles de gestion (situations, factures, stock, délais et pénalités) |
| `routers/` | auth, console DG, tableau de bord + plan du siège, études et calculs, documents/BIM, base juridique, IA |
| `engines/calcs.py` | 10 moteurs de pré-dimensionnement déterministes (CFO, CFA, incendie, plomberie, HVAC, aéraulique, génie civil) |
| `ai/` | Catalogue des 15 assistants, collecte des sources autorisées, routeur local/cloud, masquage, fournisseurs |
| `migrate.py`, `cli.py` | Migrations versionnées avec somme de contrôle ; administration hors ligne (création et récupération du DG) |

## Défense en profondeur

1. **Interface** : masque les modules non autorisés (confort uniquement).
2. **API** : chaque route vérifie la session, la MFA, puis l'autorisation (`Principal.require` / `scope_clause`).
3. **Base de données** :
   - le rôle `ilk_app` n'a ni `DELETE`, ni `TRUNCATE`, ni écriture sur `audit_events`, ni droit d'insérer/modifier `is_group_director` ;
   - un trigger refuse toute autorisation ou réglage IA dont l'auteur n'est pas le Directeur actif ;
   - un trigger rend le journal d'audit non modifiable, même pour le propriétaire ; chaque ligne est chaînée par SHA-256 (`audit_verify()`).

## Schéma PostgreSQL (migrations `backend/migrations`)

| Domaine | Tables |
|---|---|
| Organisation | `companies`, `org_units` (codes V0.7, étage du siège, modules couverts) |
| Identité et sécurité | `users`, `sessions`, `recovery_codes`, `grants`, `ai_settings`, `ai_consents`, `ai_requests`, `audit_events` |
| CRM | `parties` (clients, fournisseurs, sous-traitants, partenaires, administrations) |
| Projets | `projects`, `milestones` |
| Chantiers | `sites`, `site_daily_reports`, `site_risks` |
| Marchés | `contracts`, `contract_events` (ODS, avenants, réclamations, réceptions), `situations` |
| Finances | `invoices`, `payments` |
| Achats et logistique | `purchase_orders`, `stock_items`, `stock_movements`, `equipment` |
| RH | `employees`, `leave_requests` |
| QHSE | `qhse_events` |
| Études | `deliverables`, `calc_runs`, `coordination_issues` |
| Documents/BIM | `documents`, `document_versions` (SHA-256, métadonnées IFC) |
| Juridique | `legal_sources` (références saisies et vérifiées) |

La gestion financière est séparée par filiale (migration `004_finances_separees.sql`, voir `03_AUTORISATIONS.md`). Toutes les données métier portent `company_id` : l'isolation entre eurl medater et cabinet ILK est appliquée à chaque requête, et toute référence croisée (ex. facturer un client de l'autre filiale) est refusée.

Évolution du schéma : ajouter un fichier `004_xxx.sql` ; ne jamais modifier une migration déjà appliquée (la somme de contrôle est vérifiée).

## Montée en charge

Le déploiement sur un PC (i5, 16 Go) convient au DG puis à quelques dizaines d'utilisateurs. Pour 60 collaborateurs simultanés : serveur dédié Linux, même `docker-compose.yml`, sauvegardes hors site, limiteur de débit partagé (Redis) si plusieurs instances d'API, et IA locale sur une machine équipée d'un GPU.
