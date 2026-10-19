# Guide d'utilisation

## Connexion
Email, mot de passe, puis code MFA à 6 chiffres. À la première connexion d'un collaborateur, le changement du mot de passe temporaire est imposé (12 caractères minimum, 3 types de caractères). Après 5 échecs, le compte est verrouillé 15 minutes. Une session expire après 30 minutes d'inactivité (10 heures au maximum).

## Siège virtuel 3D
- **Ascenseur** : choisir un étage (RDC Direction et services communs, R+1 eurl medater, R+2 cabinet ILK) ou la vue d'ensemble.
- **Bureaux** : un clic ouvre le module du département. Bureaux dorés = ouverts ; bureaux gris = non autorisés.
- Souris : glisser pour tourner, molette pour zoomer. Le menu de gauche donne accès aux mêmes modules : le siège ne remplace pas les tableaux de bord.

## Console du Directeur (Direction → Console du Directeur)
1. **Nouveau compte** : email, nom, fonction, **filiale de rattachement** (obligatoire), département de cette filiale, mot de passe temporaire. Le compte n'a aucun droit, et ne pourra jamais en recevoir sur l'autre filiale.
2. **Attribuer une autorisation** : choisir le collaborateur, le périmètre (filiale, département, module, projet, document), les actions (consulter, modifier, valider, exporter), une date d'expiration facultative et une note de motif.
3. Sur chaque compte : suspendre, réactiver ou révoquer une autorisation ; activer l'IA locale ou cloud ; fermer les sessions ; réinitialiser le mot de passe ; désactiver le compte.
4. **Journal d'audit** : toutes les actions sensibles, avec contrôle d'intégrité du chaînage.

Démarche conseillée pour le pilote : rester seul utilisateur, saisir les projets et marchés en cours, puis ouvrir les accès un par un, au plus juste, avec une date d'expiration.

## Modules
| Module | Contenu |
|---|---|
| Tableau de bord | Indicateurs par filiale (projets en retard, avancement, créances échues, marchés en retard, pénalités théoriques, livrables à valider, stock, RH, QHSE), présentés filiale par filiale sans total commun |
| Directives de la DG | La Direction générale émet une directive sur un projet ; l'équipe accuse réception et rend compte ; la DG clôture. Historique complet du suivi |
| Projets | Projets (phase ESQ → CLOS, statut, budget, alerte de retard), jalons |
| Chantiers | Chantiers (avancement physique), journal de chantier quotidien, registre des risques |
| Études, MEP et calculs | Livrables par phase et spécialité avec circuit soumis → validé/rejeté ; 10 moteurs de pré-dimensionnement ; registre de synthèse et conflits MEP |
| Documents et BIM | Dépôt contrôlé (PDF, DWG, DXF, IFC, Office, images), versions et indices, empreinte SHA-256, métadonnées IFC |
| Marchés et contrats | Marchés (TVA, retenue de garantie, pénalités, plafond), ODS, avenants, réclamations, réceptions ; fin contractuelle recalculée, retard et pénalités théoriques ; situations avec décompte (période, retenue, TVA, net à payer, avancement financier) |
| Finances | Choix de la filiale (eurl medater ou cabinet ILK), comptes séparés ; factures clients et fournisseurs (TTC, solde, retard), encaissements et paiements (dépassement du solde refusé) |
| Achats et stocks | Bons de commande, articles, mouvements (stock négatif refusé, alerte sous le seuil) |
| Parc matériel | Engins et matériel, affectation à un chantier, maintenance |
| Ressources humaines | Personnel par département, congés (décision avec l'action « valider ») |
| Qualité et HSE | Non-conformités, inspections, incidents, accidents |
| Clients et fournisseurs | Tiers par filiale (NIF, RC, wilaya) |
| Base juridique | Références officielles saisies puis vérifiées par une seconde personne |
| ilk.medater AI | Question à un assistant spécialisé, réponse sourcée `[S#]`, informations manquantes, moteur utilisé |

Les montants s'entendent en dinars algériens (DA). Les calculs de délais, pénalités et décomptes sont **indicatifs** : ils doivent être confirmés au regard du CCAP/CCAG applicable et des ODS signés.
