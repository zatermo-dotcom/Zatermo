import type { ProjectData } from '../types';
import { StatusBadge } from './Panels';

interface Props { data: ProjectData; onFace: (id: string) => void; onSheet: (id: string) => void }

/** Les 26 faces de l'annexe C : vue frontale dans le modèle et planche d'élévation du PDF. */
export function WallsPanel({ data, onFace, onSheet }: Props) {
  const groups: [string, string][] = [['M', 'Murs M01-M16'], ['P', 'Trumeaux et angle P01-P06'], ['C', 'Poteau central C01-C04']];
  const P = data.walls.profiles; const hz = data.geometry.heights;
  return (
    <div>
      <p className="hint">
        Cadres en partie haute uniquement ({hz.basCadres.value.toFixed(2)} → {hz.hautCadres.value.toFixed(2)} m), cimaise à +{hz.axeCimaise.value.toFixed(2)} m, partie basse lisse.
        Double encadrement : profil 01 {P.cadre01.width * 1000} mm, profil 02 {P.cadre02.width * 1000} mm en retrait de {P.cadre02.offset * 1000} mm.
        « Vue 3D » place la caméra face au mur ; « Élévation » ouvre la planche cotée du PDF pour comparer.
      </p>
      {groups.map(([k, title]) => (
        <div key={k}>
          <h4>{title}</h4>
          <table className="src faces">
            <thead><tr><th>Face</th><th>Largeur</th><th>Cadres (mm)</th><th>Statut</th><th /></tr></thead>
            <tbody>
              {data.walls.faces.filter((f) => f.id.startsWith(k)).map((f) => {
                const L = Math.hypot(f.b[0] - f.a[0], f.b[1] - f.a[1]);
                return (
                  <tr key={f.id}>
                    <td><b>{f.id}</b><div className="file">{f.label}</div></td>
                    <td className="nowrap">{L.toFixed(2)} m</td>
                    <td>{f.frames.length ? f.frames.join(' / ') : 'cimaise seule'}</td>
                    <td><StatusBadge s={f.status} /></td>
                    <td className="nowrap">
                      <button className="mini" onClick={() => onFace(f.id)}>Vue 3D</button>
                      <button className="mini" onClick={() => onSheet(f.id)}>Élévation p.{f.page}</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
