# Sources et hypothèses

Généré depuis `public/data/sources.json` (même contenu que le panneau « Sources » de l'application).

Statuts : **coté** = lu sur le plan officiel ; **déduit** = mesuré sur le vecteur du PDF ; **proposé** = valeur de projet du dossier ; **à confirmer** = valeur de travail éditable.

| Élément | Valeur retenue | Pages | Statut | Fichier |
|---|---|---|---|---|
| Contour, murs, baies, poteau | Plan état des lieux vectoriel, échelle 45 pt/m | 33, 98, 4 | coté | `geometry.json` |
| Largeur totale / profondeur totale | 18,30 m (O→nu est self) / 12,80 m (O→nu sud alcôve) – vérifiées sur le dessin | 33, 98 | coté | `geometry.json` |
| Surface | 161,68 m² inscrits ; contour modélisé = 161,66 m² hors poteau (hypothèse 180 m² abandonnée) | 33, 98 | coté | `geometry.json` |
| Poteau central | 0,51 × 0,53 m, à 5,65 m de O en X et Y | 33, 98 | coté | `geometry.json` |
| Petites faces (M04, M05, M11-M13, P01-P06) | Largeurs déduites du vecteur ; M04/M05 = 1,20 m à vérifier | 40, 44, 45, 51, 52, 53, 61, 62, 69 | à confirmer | `walls.json` |
| Épaisseur des murs | ≈ 0,30 m lue sur le vecteur | 98 | déduit | `geometry.json` |
| Plafond existant | +4,00 m — _Coupes V01 : H plafond / H structure « à relever »_ | 39, 67, 30 | proposé | `geometry.json` |
| Sous-face BA13 | +3,60 m | 39, 67 | proposé | `geometry.json` |
| Dessous des gorges | +3,30 m (retombée 300 mm) | 39, 67 | proposé | `geometry.json` |
| Section de gorge P / O / R | 180 / 80 / 60 mm – réservations, largeur horizontale de gorge non cotée | 67, 73 | à confirmer | `ceiling.json` |
| Caissons G1-G6 | Cadres R07 en coordonnées ; LED 91,40 m | 99, 71 | proposé | `ceiling.json` |
| Caisson G4 (forme) | Rectangle R07 retenu ; redent visible p.22-23 non repris | 22, 23, 99 | à confirmer | `ceiling.json` |
| Rosaces / lustres L01-L07 | Positions R07 ; diamètre rosace 0,90 m et lustre de travail — _Positions = proposé ; diamètre et modèle = à confirmer_ | 75, 99 | à confirmer | `ceiling.json / lighting.json` |
| Corniches et moulures du plafond | Profil schématique en gradins ; motif feuillagé non inventé | 28, 73, 76 | à confirmer | `ceiling.json` |
| Poutres au droit du poteau | Traces du plan, retombée inconnue (masquée par bandeau +3,30) | 33, 36, 37 | à confirmer | `geometry.json` |
| Hauteur des baies / portes | Baies 3,00 m, porte cuisine 2,20 m, accès 2,40 m (valeurs de travail) — _« Aucune hauteur de baie n'est inventée » dans le dossier : valeurs à relever_ | 36, 39 | à confirmer | `geometry.json` |
| Cadres muraux (26 faces) | Largeurs hors tout par face, h 1,87 m entre +1,28 et +3,15 ; cadre 02 à 70 mm | 39, 41, 42, 56, 69 | proposé | `walls.json` |
| Cimaise 03 et partie basse | Axe +1,10 m, 60 × 20 mm ; partie basse lisse sans cadre | 39, 67, 68 | proposé | `walls.json` |
| Profils 01 / 02 | 35 × 14 et 20 × 10 mm (enveloppes, galbe à relever) | 68 | proposé | `walls.json` |
| Plinthe | 120 mm | 67 | à confirmer | `geometry.json` |
| Calepinage du sol – Sol A | Cadres noirs alignés sur les caissons ; dalle 0,80 m et bande 0,30 m de travail | 22 | à confirmer | `materials.json` |
| Calepinage du sol – Sol B | Filet noir étroit (0,14 m) des perspectives | 7, 14, 21 | à confirmer | `materials.json` |
| Appliques A01-A19 | Coordonnées R07 sur supports pleins ; hauteur 2,15 m de travail — _Position = proposé ; hauteur et modèle = à confirmer_ | 99, 24 | proposé | `lighting.json` |
| Spots (30) | Coordonnées R07, groupes 9/5/6/10 | 100, 76 | proposé | `lighting.json` |
| Chaises | 40 : 26 ivoire / 10 bordeaux / 4 noires ; 500 × 560 × 900, assise 450 ; Chesterfield dossier intérieur | 102 | proposé | `furniture.json` |
| Tables | 15 : 10 rect. 1200 × 800 + 5 carrées 900 × 900, H 750, plateau 30 marbre crème, pied central noir/laiton | 103 | proposé | `furniture.json` |
| Banquettes | 6 ensembles (3 droits, 3 en L), 28,40 ml bruts, P 650, H 900 | 104, 107 | proposé | `furniture.json` |
| Buffets périphériques | C01 5,80 + 4,80 × 0,65 ; C02 2,20 × 0,60 ; H 0,90 ; portes + plateau clair | 105, 107 | proposé | `furniture.json` |
| Îlot central | 2,20 × 1,80 × 0,90 ; 8 travées ouvertes, 16 niches, sans portes | 106, 107 | proposé | `furniture.json` |
| Implantation du mobilier | Aménagement 02 (15 tables) recalé sur la géométrie cotée ; Aménagement 01 en variante — _Vues de principe sans échelle ; aucun plan de mobilier coté fourni_ | 5, 6, 18, 36 | à confirmer | `furniture.json` |
| Palette et matériaux | Crème, ivoire, bordeaux, bois sombre, doré | 12, 13 | proposé | `materials.json` |
| Vues extérieures | Non modélisées (fond neutre derrière les vitrages) | 7, 10 | à confirmer | `—` |
