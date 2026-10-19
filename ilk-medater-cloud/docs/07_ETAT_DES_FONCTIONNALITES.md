# État réel des fonctionnalités — version 1.0.0-rc1 (19 octobre 2026)

Légende : **Testé** = vérifié par un test automatisé ou une exécution réelle décrite ci-dessous · **Implémenté, non testé en conditions réelles** · **Absent**.

## Vérifications réellement effectuées
- `pytest` : **49 tests réussis** (deux exécutions consécutives), contre un vrai PostgreSQL 16, l'API se connectant avec le rôle restreint `ilk_app`.
- Parcours navigateur (Chromium piloté par Playwright) sur le serveur de développement : connexion DG + MFA, 15 écrans sans erreur JavaScript, siège 3D (29 bureaux, ascenseur), assistant IA en mode règles ; parcours d'un collaborateur limité (mot de passe imposé, un seul chantier visible, finances et console refusées).
- Sauvegarde `pg_dump` + documents, puis test de restauration non destructif : empreintes OK, 35 tables, journal d'audit intègre.
- `docker compose config` : configuration valide (services db, migrate, api, web, backup, ollama).

## Tableau

| Fonction | État |
|---|---|
| Migrations SQL versionnées avec somme de contrôle | Testé |
| Rôle applicatif sans DELETE, sans écriture sur l'audit, sans promotion de Directeur | Testé |
| Seul le DG attribue les droits (API + trigger base) | Testé |
| Compte neuf sans aucun droit ; refus par défaut | Testé |
| Périmètres filiale / département / module / projet / document ; actions view/edit/validate/export | Testé |
| Expiration, suspension, révocation définitive | Testé |
| Isolation inter-filiales (lecture, écriture, références croisées) | Testé |
| MFA TOTP (DG obligatoire, collaborateurs facultative), codes de récupération à usage unique | Testé (avec pyotp ; pas encore avec un téléphone réel) |
| Sessions serveur révocables, expiration, déconnexion, désactivation de compte | Testé |
| Verrouillage après 5 échecs, limitation de débit, protection CSRF | Testé (limiteur en mémoire, une seule instance d'API) |
| Journal d'audit chaîné et non modifiable | Testé |
| CLI : création et récupération du DG, vérification de l'audit | Implémenté, non testé (saisie masquée interactive) |
| Projets, jalons, chantiers, journal, risques | Testé (API) + parcours navigateur |
| Marchés, ODS/avenants, délais et pénalités théoriques, situations et décomptes | Testé |
| Factures, paiements, créances et retards, consolidation | Testé |
| Bons de commande, stock, matériel, RH, congés, QHSE, tiers | Testé pour stock, commandes et isolation ; autres écrans vérifiés en navigateur |
| Livrables APS/APD/DCE/EXE avec validation à quatre yeux | Testé |
| 10 moteurs de pré-dimensionnement | Testé (valeurs recalculées à la main) |
| Documents : contrôle de type et signature, versions, SHA-256, métadonnées IFC, droits d'export | Testé |
| Visualisation 3D des maquettes IFC | **Absent** (métadonnées seulement) |
| Base juridique avec vérification par une seconde personne | Testé |
| IA : activation par le DG, sources limitées aux droits, garde-fou juridique, retrait des citations inventées | Testé |
| IA cloud : consentement, refus si données confidentielles, masquage | Testé avec un fournisseur simulé ; **aucun appel réel** effectué (pas de clé API) |
| IA locale Ollama | Code testé avec un modèle simulé ; **aucun modèle réel exécuté** |
| Siège 3D relié aux droits et aux modules | Testé en navigateur (rendu logiciel) ; performance sur le PC réel à mesurer |
| Docker Compose sur Windows 11 / WSL 2 | **Non exécuté** (pas de démon Docker dans l'environnement de développement) |
| nginx (CSP, limitation de débit) | Configuration écrite, **non exécutée** ; le serveur de développement le remplace |
| Accès distant Tailscale | Procédure documentée, non testée |
| Interface en arabe et en anglais | **Absent** (textes en français ; à prévoir) |
| Planning Gantt, BPU/DQE détaillés, métrés, sous-traitance détaillée, révision des prix, remboursement d'avance | **Absent** |
| Notifications par email, import des 60 collaborateurs, imports comptables | **Absent** |
| Row-Level Security PostgreSQL | **Absent** (isolation appliquée par l'API, défenses critiques en triggers) |
| Tests de charge, audit de sécurité externe | **Absent** — requis avant d'ouvrir l'accès aux 60 collaborateurs |

## Avant la mise en production
1. Démarrer avec Docker sur le PC réel et constater chaque étape du guide d'installation.
2. Enrôler la MFA du DG avec son téléphone et tester un code de récupération.
3. Exécuter `restore-test.ps1` et conserver le résultat.
4. Faire relire par les ingénieurs les valeurs « à confirmer » des moteurs de calcul, et par le juriste la saisie des premières références.
5. Faire réaliser un test d'intrusion avant d'ouvrir les accès au-delà du DG.
