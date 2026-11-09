# Restaurant ibis · Oran — visite 3D interactive

Visite web du restaurant de l'hôtel ibis d'Oran, construite à partir du dossier
« ILK_Portfolio_Restaurant_Ibis_modifie.pdf » (109 pages). Le modèle 3D est **paramétrique** :
il est généré dans le navigateur à partir de fichiers JSON modifiables (`public/data/`), et
peut être exporté en **GLB**.

- Géométrie : plan état des lieux vectoriel (p.33 / p.98), recalé à 45 pt/m. Toutes les cotes
  du plan ont été vérifiées sur le dessin : 18,30 · 12,80 · 11,45 · 8,70 · 6,15 · 5,80 · 5,65 / 5,29 · 6,40 · 4,10 · 5,10 / 2,85 / 3,95 · 1,10 / 1,75 / 4,00 · poteau 0,51 × 0,53.
  Surface du contour modélisé hors poteau : **161,66 m²** (inscrite : 161,68 m²).
- Altimétrie : plafond existant +4,00 · sous-face BA13 +3,60 · dessous des gorges +3,30 ·
  cadres +1,28 → +3,15 · cimaise +1,10 (statut « proposé », p.39 / p.67).
- Plafond R07 : 6 caissons G1-G6, 7 rosaces/lustres, 19 appliques, 30 spots aux coordonnées
  des p.99-100.
- Murs : 26 faces de l'annexe C (p.39-69), cadres en partie haute uniquement, partie basse lisse.
- Mobilier (annexe F, p.102-107) : 15 tables (10 rect. + 5 carrées), 40 chaises (26 ivoire,
  10 bordeaux, 4 noires), 6 banquettes (3 droites + 3 en L), 2 buffets périphériques à portes,
  îlot central 2,20 × 1,80 × 0,90 à niches ouvertes (aucune porte).

## Lancer l'application

Prérequis : Node.js ≥ 20 (testé avec Node 22) et npm.

```bash
cd ibis-oran-visite
npm install
npm run dev          # http://localhost:5173
```

Version de présentation (fichiers statiques optimisés) :

```bash
npm run build        # vérifie les types et produit dist/
npm run preview      # http://localhost:4173
```

Le dossier `dist/` peut être copié tel quel sur n'importe quel serveur web statique
(chemins relatifs). Il ne s'ouvre pas en double-cliquant sur `index.html` (le navigateur
bloque le chargement des JSON en `file://`) : utilisez `npm run preview` ou un serveur web.

Paramètres d'URL utiles : `?vue=buffet-central` (vue de départ, identifiant de `cameras.json`),
`?qualite=elevee` (19 appliques éclairantes en plus des 7 lustres).

### Vérification automatique et export GLB

```bash
npm run build
npm run check        # ouvre la visite dans Chromium (Playwright), contrôle quantités,
                     # vues, plan, rendus, double-clic au sol, variantes, mobile ;
                     # captures dans docs/captures/
npm run export:glb   # écrit model/restaurant-ibis-oran_amenagement-02_sol-A_abat-jour.glb
npm run export:glb -- amenagement-01 sol-B vasque   # export d'une variante
npm run docs         # régénère docs/*.md depuis les JSON
```

Les scripts `check` et `export:glb` utilisent Playwright et Chromium : `npm install -D playwright`
puis `npx playwright install chromium` si ces outils ne sont pas déjà présents sur le poste.
Le bouton « Exporter le GLB » de l'onglet Réglages fait le même export depuis le navigateur.

## Utilisation

| Action | Souris / clavier | Tactile |
|---|---|---|
| Regarder autour | glisser | glisser un doigt |
| Se déplacer à un point | double-clic au sol | double-tap au sol |
| Avancer / reculer / tourner | molette, flèches, Z Q S D | pavé ▲ ◀ ▼ ▶ |
| Vue générale | molette = zoom, clic droit = déplacer | pincer, deux doigts |
| Changer d'espace | barre de vues en bas, onglet **Vues**, ou clic sur le **Plan** | idem |
| Rendus de référence | vignettes en bas à gauche ou onglet **Rendus** → « Voir la position dans le modèle 3D » / « Retour au modèle » | idem |
| Présentation client | bouton **Plein écran** (masque les panneaux) | idem |

Onglets : **Plan** (zones et points de vue cliquables, position de la caméra) · **Vues** ·
**Rendus** (33 images extraites du PDF + planches techniques) · **Sources** (sources et
hypothèses avec page et statut, et table de correspondance des 109 pages) · **Réglages**
(variantes, contrôle des quantités, export GLB, rechargement des données).

## Variantes (jamais mélangées dans un même modèle)

| Réglage | Version principale | Variante |
|---|---|---|
| Implantation | Aménagement 02 – 15 tables (p.6 + annexe F) | Aménagement 01 – 12 tables (p.5) |
| Sol | Sol A – calepinage p.22, cadres noirs larges alignés sur les caissons | Sol B – filet noir étroit des perspectives p.7 / p.14 / p.21 |
| Lustres | 6 bras à abat-jour (p.1, 7-9, 14) | Suspension vasque (variante de rendu p.11) |

Les cadres en partie basse, rideaux, tableaux, plantes et pupitre visibles sur certains rendus
sont des **intentions d'image** : ils ne sont pas modélisés (la V3 prescrit une partie basse lisse).
Les rendus sont présentés comme images de référence : ce ne sont ni des panoramas ni des vues
calculées du modèle.

## Modifier le modèle (bureau d'études)

Tout est dans `public/data/` ; après modification, cliquez sur **Réglages → Recharger les données**
(ou rechargez la page). Repère commun : origine O = angle intérieur nord-ouest (haut/gauche du
plan, comme R07 p.99), **X** vers la droite, **Y** vers le bas, en mètres ; la hauteur est en mètres
depuis le sol fini.

| Fichier | Contenu |
|---|---|
| `geometry.json` | contour intérieur, épaisseur des murs, hauteurs, poteau, baies et portes (hauteurs « à confirmer »), zones du plan |
| `walls.json` | 26 faces : extrémités, normale vers la salle, largeurs hors tout des cadres (mm), profils 01/02/03 |
| `ceiling.json` | caissons G1-G6, section de gorge (P, O, R, retrait LED), rosaces (positions, diamètre) |
| `lighting.json` | lustres, appliques A01-A19, spots, intensités et teintes (réglages visuels) |
| `furniture.json` | gabarits, implantations (tables + chaises par côté et couleur), banquettes et buffets par branches, îlot |
| `materials.json` | couleurs PBR de la palette, variantes de sol (dalle, largeur de bande) et de lustres |
| `cameras.json` | positions de caméra `pos` / `target` = [X, Y, hauteur], champ de vision, pages associées |
| `renders.json` | rendus extraits (fichier, page, zone, vue associée, remarque) |
| `sources.json`, `pdf-index.json` | panneau Sources et correspondance des pages |

Astuce : placez-vous dans la visite puis **Réglages → Copier la vue (JSON)** pour obtenir une
entrée prête à coller dans `cameras.json`.

## Architecture technique

Le poste de génération ne disposant pas de Blender, la chaîne « Blender + script Python → GLB »
est remplacée par un équivalent : **générateur Three.js paramétrique** (TypeScript) qui lit les
JSON, construit la scène, et l'exporte en GLB (`GLTFExporter`). Le GLB s'importe dans Blender,
3ds Max, SketchUp (via extension) ou tout viewer glTF.

```
src/engine/
  architecture.ts  sol (texture de calepinage), murs percés, baies, portes, poteau
  wallDecor.ts     cadres doubles, cimaise, plinthe, corniche (26 faces)
  ceiling.ts       bandeau +3,30, caissons BA13 +3,60, gorges LED, moulures, rosaces, spots
  furniture.ts     chaises, tables, banquettes, buffets, îlot
  lighting.ts      lustres (2 styles), appliques orientées vers la salle, sources lumineuses
  Tour.ts          rendu, navigation, vols de caméra, export GLB
src/components/    plan interactif SVG, galerie de rendus, sources, réglages
public/renders/    rendus extraits du PDF (pages 1-23, 28, 39, 102-106)
public/plans/      planches techniques de référence
docs/              correspondance des pages, sources et hypothèses, captures de contrôle
model/             export GLB de la version principale
```

## Points à valider pour améliorer la fidélité

1. **Altimétrie réelle** : hauteur sous dalle, épaisseur et retombées des poutres au droit du
   poteau, plénum (les coupes V01 les laissent « à relever » ; +4,00 / +3,60 / +3,30 viennent de la V3).
2. **Baies et portes** : hauteurs des portes-fenêtres, des baies fixes, de la porte cuisine et de
   l'accès (valeurs de travail 3,00 / 2,20 / 2,40 m) ; allèges, linteaux, menuiseries.
3. **Petites faces déduites** : M04/M05 (1,20 m), M11-M13, angle nord-ouest P05/P06, joue de
   l'accès ; et l'écart M10 (2,55 m de parement + 0,30 m de joue = 2,85 m coté).
4. **Section de gorge et moulures** : saillie, ouverture, profil de corniche réel, motif des
   frises (non inventé ici) ; diamètre et relief des rosaces (0,90 m provisoire).
5. **Caisson G4** : rectangle R07 retenu, alors que les planches p.22-23 montrent un redent.
6. **Calepinage du sol** : format de dalle (0,80 m provisoire), largeur des bandes noires, choix
   entre Sol A et Sol B, cadre autour du poteau.
7. **Implantation du mobilier** : un plan de mobilier coté manque ; banquettes B01/B03 placées
   devant PF1/PF2 comme sur p.6 (dégagement des portes-fenêtres à vérifier) ; branche sud du
   buffet C01 alignée sur M10 (0,15 m devant M08) ; position de C02 et de l'îlot.
8. **Luminaires** : modèles, diamètres et hauteur de suspension des lustres, hauteur de pose des
   appliques (2,15 m provisoire).
