// Régénère docs/correspondance-pdf.md et docs/sources-hypotheses.md depuis public/data/*.json
import { readFileSync, writeFileSync } from 'node:fs';
const rd = (f) => JSON.parse(readFileSync(new URL(`../public/data/${f}.json`, import.meta.url)));
const idx = rd('pdf-index'); const src = rd('sources'); const walls = rd('walls'); const ren = rd('renders'); const cams = rd('cameras');
const esc = (s) => String(s).replace(/\|/g, '\\|');
let md = `# Correspondance des 109 pages du PDF\n\nSource : « ILK_Portfolio_Restaurant_Ibis_modifie.pdf » (109 pages A3). Fichier généré depuis \`public/data/pdf-index.json\`.\n\n`;
md += `Règle appliquée : les plans cotés et dossiers techniques (p.33-107) établissent la géométrie ; les perspectives (p.1-23) servent à vérifier l'ambiance et les matériaux. Les images qui présentent des variantes ne sont pas mélangées au modèle principal.\n\n`;
md += `| Pages | Type | Contenu | Usage dans le modèle | Zone |\n|---|---|---|---|---|\n`;
for (const r of idx.rows) md += `| ${r.pages} | ${esc(r.category)} | ${esc(r.content)} | ${esc(r.usage)} | ${esc(r.zone)} |\n`;
md += `\n## Faces murales (annexe C)\n\n| Face | Localisation | Page | Cadres hors tout (mm) | Statut |\n|---|---|---|---|---|\n`;
for (const f of walls.faces) md += `| ${f.id} | ${esc(f.label)} | ${f.page} | ${f.frames.join(' / ') || '— (cimaise seule)'} | ${f.status} |\n`;
md += `\n## Rendus extraits et vues 3D associées\n\n| Page | Rendu | Zone | Vue 3D associée | Remarque |\n|---|---|---|---|---|\n`;
const lab = Object.fromEntries(cams.views.map((v) => [v.id, v.label]));
for (const r of ren.items) md += `| ${r.page} | ${esc(r.title)} (\`${r.file}\`) | ${r.zone} | ${lab[r.camera] ?? r.camera} | ${esc(r.note ?? '')} |\n`;
writeFileSync(new URL('../docs/correspondance-pdf.md', import.meta.url), md);
let s = `# Sources et hypothèses\n\nGénéré depuis \`public/data/sources.json\` (même contenu que le panneau « Sources » de l'application).\n\nStatuts : **coté** = lu sur le plan officiel ; **déduit** = mesuré sur le vecteur du PDF ; **proposé** = valeur de projet du dossier ; **à confirmer** = valeur de travail éditable.\n\n| Élément | Valeur retenue | Pages | Statut | Fichier |\n|---|---|---|---|---|\n`;
for (const i of src.items) s += `| ${esc(i.element)} | ${esc(i.value)}${i.note ? ` — _${esc(i.note)}_` : ''} | ${i.pages.join(', ')} | ${i.status} | \`${i.file}\` |\n`;
writeFileSync(new URL('../docs/sources-hypotheses.md', import.meta.url), s);
console.log('docs régénérées');
