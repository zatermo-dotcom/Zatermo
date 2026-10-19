# Autorisations — règle absolue du groupe

**Seul le Directeur général du groupe attribue les autorisations.** Cette règle est appliquée à trois niveaux : interface, API et base de données (trigger `grants_director_only`). Aucun responsable, directeur de filiale, administrateur informatique ni assistant IA ne peut s'attribuer ou attribuer un droit.

## Principes
- **Refus par défaut** : un compte créé n'a aucun droit métier (ni module, ni IA).
- **Moindre privilège** : le Directeur ouvre précisément un périmètre et des actions.
- **Contrôle côté serveur** : l'interface n'est jamais l'autorité.
- **Traçabilité** : chaque création, modification, suspension ou révocation est inscrite dans le journal chaîné.
- **IA** : chaque assistant agit avec les droits de l'utilisateur connecté, jamais plus.

## Périmètres

| Périmètre | Effet | Exemple |
|---|---|---|
| Filiale | Tous les modules de la filiale | Directeur d'eurl medater : filiale eurl medater, consulter + valider |
| Département | Modules du département, dans sa filiale ; pour un service commun, la filiale est précisée | Comptable : « Comptabilité et finances » pour cabinet ILK |
| Module | Un module d'une filiale | Juriste : module « Contrats et marchés » d'eurl medater |
| Projet | Le projet et ses chantiers, études, documents, QHSE | Conducteur de travaux : projet MED-2026-01 |
| Document | Un document précis | Bureau de contrôle : un plan, consultation seule |

## Actions
`consulter` (view), `modifier` (edit), `valider` (validate), `exporter` (export). Toute action accordée implique la consultation.
- **Valider** : situations de travaux, factures annulées, bons de commande, congés, livrables d'études (principe des quatre yeux : l'auteur ne valide pas son propre livrable), références juridiques.
- **Exporter** : téléchargement des documents confidentiels ou secrets (les documents internes se téléchargent avec la consultation).

## Cycle de vie
- **Expiration** : date facultative ; au-delà, l'autorisation ne donne plus rien.
- **Suspension** : réversible.
- **Révocation** : définitive (une autorisation révoquée ne peut pas être réactivée ; en créer une nouvelle si besoin).
- Le périmètre d'une autorisation existante ne se modifie pas : révoquer puis recréer (traçabilité).
- Désactiver un compte ferme immédiatement toutes ses sessions.

## IA
Activée par le Directeur, compte par compte : « IA locale » et « IA cloud » séparément. L'IA cloud exige en plus, à chaque demande, le consentement de l'utilisateur (politique versionnée) et ne reçoit jamais de données financières, RH ou de documents confidentiels.

## Compte du Directeur
- Créé uniquement par la commande hors ligne `python -m app.cli create-director` (un seul Directeur possible, contrainte d'unicité en base).
- MFA TOTP obligatoire, 10 codes de récupération à usage unique (à conserver sous enveloppe scellée).
- Récupération en cas de perte du téléphone : un code de récupération, ou, avec un accès administrateur au serveur, `reset-director-mfa` (journalisé, toutes les sessions révoquées).
- Le compte du Directeur ne peut pas être désactivé ni promu/rétrogradé depuis l'application.
