import type { DiseaseFinding } from '../types';
import { diseaseLabel } from '../utils/constants';
import { formatPct } from '../utils/formatters';

export default function DiseaseCard({
  disease,
  othersCount = 0,
}: {
  disease: DiseaseFinding;
  othersCount?: number;
}) {
  return (
    
    <div className="hud-panel p-4 flex-1">
      <div className="font-hud text-sm tracking-[0.25em] text-rg-muted">PRIMARY DISEASE</div>
      <div className="flex items-center gap-3 mt-2">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#C7F000" strokeWidth="1.5" className="shrink-0 drop-shadow-[0_0_8px_rgba(199,240,0,0.6)]">
          <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="#C7F000"/>
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>
        </svg>
        <div className="min-w-0">
          <div className="font-display text-xl neon-text tracking-widest leading-tight uppercase truncate">
            {diseaseLabel(disease.name)}
          </div>
          {disease.scientificName && (
            <div className="font-body italic text-xs text-rg-muted mt-0.5 truncate">
              ({disease.scientificName})
            </div>
          )}
        </div>
      </div>

      <div className="mt-2 font-hud text-sm tracking-[0.15em] text-rg-muted">
        {formatPct(disease.confidence, 1)} CONFIDENCE
        {/* Largest lesion area, not a ranking of importance. */}
        {othersCount > 0 && ` · +${othersCount} MORE DETECTED`}
      </div>
    </div>
  );
}
