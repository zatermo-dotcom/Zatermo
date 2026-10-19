# Audit des sources reçues (V0.7 et V0.8)

Date : 19 octobre 2026. Archives examinées intégralement :
`ilk_medater_CRM_V0.8_pilote.zip` (20 fichiers, ~400 lignes de code) et `ILK_GROUP_Organigramme_CRM_V0.7.zip` (5 fichiers de données).

## 1. Inventaire

| Élément | Contenu réel | Verdict |
|---|---|---|
| `backend/app/main.py` (243 lignes) | API FastAPI : login JWT, `/me`, `/companies`, `/projects`, `/admin/*` (comptes, droits par filiale, audit), `/assistant/ask` (règles), `/studies/*` (canevas), `/organization` (dictionnaire en dur) | **Prototype fonctionnel minimal** |
| `backend/app/seed.py` | Crée les 2 filiales et le compte direction ; tables créées par `create_all` | Prototype |
| `frontend/index.html` | Siège 3D V0.3 (Three.js via CDN) + pages de démonstration stockées dans `localStorage` | **Démo non reliée à l'API** |
| `frontend/cloud.html` | Console V0.4 : login, liste JSON, création de projet | Prototype |
| `frontend/directeur.html` | **Fichier vide (0 octet)** | Absent — la « console direction » annoncée dans le README n'existe pas |
| `frontend/studies.html` | **Fichier vide (0 octet)** | Absent |
| `frontend/assistant.html` | **Fichier vide (0 octet)** | Absent — le bouton « ILK AI » de l'accueil mène à une page blanche |
| `docker-compose.yml`, `Dockerfile` | PostgreSQL 16, API, nginx statique | Fonctionnel en principe, non sécurisé |
| `ARCHITECTURE_IA.md`, `ETUDES_V06.md` | Intentions ; indiquent eux-mêmes que LLM, calculs et juridique ne sont pas implémentés | Documentation d'intention |
| V0.7 `schema.sql` / `organisation.json` / CSV | Organigramme validé (26 unités) et 11 rôles | **Données non intégrées** au CRM ; `user_id uuid` incompatible avec les `id int` de la V0.8 |
| `__pycache__/main.cpython-313.pyc` | Artefact compilé pour Python 3.13 alors que l'image utilise 3.12 | À supprimer |

## 2. Fonctionnalités : existantes, partielles, absentes

**Existantes (V0.8)** : connexion par mot de passe (Argon2), jeton JWT 30 min, création de compte par le Directeur sans droit, attribution/révocation d'un rôle `viewer`/`manager` par filiale, journal d'audit lisible par le Directeur, liste/création de projets filtrée par filiale.

**Partielles** : siège 3D (3 étages génériques, non relié aux droits ni aux modules réels) ; assistant (règles sur la liste des projets) ; études (liste de livrables types, rien n'est enregistré) ; organigramme (dictionnaire figé dans le code).

**Absentes** : autorisations par département/projet/document/action, expiration, suspension ; MFA ; sessions révocables ; chantiers, finances, marchés, achats, stocks, matériel, RH, QHSE, documents/BIM ; moteurs de calcul ; base juridique ; IA locale/cloud ; migrations ; sauvegardes ; tests.

## 3. Défauts et problèmes de sécurité relevés

| # | Gravité | Constat |
|---|---|---|
| S1 | Élevée | L'application se connecte à PostgreSQL avec le compte propriétaire/superutilisateur : une faille applicative donne tous les droits sur la base, y compris effacer l'audit. |
| S2 | Élevée | Journal d'audit modifiable et supprimable (table ordinaire, aucune protection) ; les connexions et échecs ne sont pas journalisés. |
| S3 | Élevée | Aucune MFA, aucun verrouillage ni limitation des tentatives : force brute possible sur le compte du Directeur. |
| S4 | Moyenne | Jetons JWT non révocables (pas de déconnexion serveur, pas de table de sessions) ; un compte désactivé garde un jeton valide jusqu'à 30 min. |
| S5 | Moyenne | Énumération des comptes : pour un email inconnu, le hachage n'est pas calculé (temps de réponse différent). |
| S6 | Moyenne | `cloud.html` conserve le jeton dans une variable JS et appelle l'API sur une autre origine ; aucune politique CSP. |
| S7 | Moyenne | Droits uniquement par filiale (`viewer`/`manager`), pas de granularité ; règle « seul le DG attribue » contrôlée uniquement dans le code, pas dans la base. |
| S8 | Faible | Route héritée `POST /admin/users` acceptant un paramètre `role` sans effet (doublon de `/admin/accounts`), source de confusion. |
| S9 | Faible | `ADMIN_PASSWORD` reste dans l'environnement après l'initialisation. |
| S10 | Faible | Le siège 3D dépend d'un CDN : ne fonctionne pas hors ligne. |
| F1 | Bloquant | Trois pages vides (`directeur.html`, `studies.html`, `assistant.html`) alors que la documentation les présente comme livrées. |
| F2 | Élevé | `index.html` simule projets et comptes dans le navigateur (`localStorage`) : un utilisateur peut croire ses données enregistrées sur le serveur. |
| F3 | Élevé | Pas de migrations : impossible de faire évoluer la base sans perte (le README le reconnaît). |
| F4 | Moyen | Identifiants de filiale codés en dur (1 et 2) dans `cloud.html`. |

Points positifs conservés : hachage Argon2, refus de démarrer avec un secret JWT court, contrôle serveur `director_only`, comptes créés sans accès, IA cloud volontairement désactivée, aucune requête SQL générée par un modèle.

## 4. Décision de stack

Le backend existant est en **Python/FastAPI**, pas NestJS. Il est conservé et restructuré (pas de réécriture inutile) :
- **Backend** : FastAPI + SQLAlchemy 2 + psycopg 3, migrations SQL versionnées (la base est la source de vérité, les protections critiques y sont codées).
- **Base** : PostgreSQL 16, rôle applicatif restreint `ilk_app`.
- **Frontend** : modules JavaScript natifs sans étape de compilation (aucune chaîne Node.js à maintenir sur le PC Windows), Three.js 0.160.1 servi localement.
- Next.js / React Three Fiber restent possibles plus tard : l'API est documentée en OpenAPI (`/api/docs`) et indépendante de l'interface.

## 5. Ce qui a été repris de la V0.7

Les 26 codes d'unités validés (GROUP, ARCH, CONST, ARCH-MEP-CFO…, SHARED-…) sont repris tels quels dans la migration `002_organisation.sql`, complétés par les directions de filiale et les services complémentaires d'eurl medater demandés (RH, parc matériel, documentation, juridique des marchés). Les 11 rôles de `roles.csv` sont remplacés par la matrice périmètre × action décrite dans `03_AUTORISATIONS.md`, plus fine et conforme à la règle « seul le DG attribue ».
