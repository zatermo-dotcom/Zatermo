import { useState } from 'react';

/** Superposition rendu du PDF / capture du modèle, séparées par un curseur. */
export function Compare({ render, model, title }: { render: string; model: string; title: string }) {
  const [pos, setPos] = useState(50);
  return (
    <div className="compare">
      <div className="cmp-stage">
        <img src={model} alt={`Modèle 3D – ${title}`} />
        <img src={render} alt={`Rendu du PDF – ${title}`} className="cmp-top" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} />
        <div className="cmp-line" style={{ left: `${pos}%` }} />
        <span className="cmp-tag left">Rendu du PDF</span><span className="cmp-tag right">Modèle 3D</span>
      </div>
      <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(Number(e.target.value))} aria-label="Curseur de comparaison" />
    </div>
  );
}
