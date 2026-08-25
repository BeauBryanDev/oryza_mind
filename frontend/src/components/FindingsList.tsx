import type { DiseaseFinding } from '../types';
import { DISEASE_COLOR_BY_CLASS, diseaseLabel, severityLabel } from '../utils/constants';
import { formatPct } from '../utils/formatters';

 
export default function FindingsList({ findings }: { findings: DiseaseFinding[] }) {

  if (!findings.length) return null;

  return (

    <div className="hud-panel p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="font-hud text-sm tracking-[0.25em] text-rg-muted">
          DETECTED DISEASES
        </span>
        <span className="font-display text-base neon-text tabular-nums">{findings.length}</span>
      </div>

      {findings.length > 1 && (
        <div className="mb-2 px-2 py-1.5 rounded border border-rg-accent/50 bg-rg-accent/10">
          <span className="font-hud text-sm tracking-[0.15em] text-rg-accent">
            CO-INFECTION — each disease needs its own management
          </span>  
        </div>
      )}

      <div className="space-y-2.5">
        {findings.map((f) => (
          <div key={f.name}>
            <div className="flex items-center gap-2 text-base">
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ background: DISEASE_COLOR_BY_CLASS[f.name] }}
              />
              <span className="text-rg-text font-body flex-1 truncate">
                {diseaseLabel(f.name)}
              </span>
              <span className="chip !text-xs">{severityLabel(f.severity)}</span>
              <span className="font-display neon-text tabular-nums w-14 text-right text-base">
                {formatPct(f.confidence, 0)}
              </span>
            </div>

            <div className="progress-track mt-1">
              <div
                className="progress-fill"
                style={{
                  width: `${Math.round(f.confidence * 100)}%`,
                  background: DISEASE_COLOR_BY_CLASS[f.name],
                }}
              />
            </div>

            <div className="flex items-center gap-3 mt-1 font-hud text-xs tracking-[0.15em] text-rg-muted">
              {f.scientificName && <span className="italic truncate">{f.scientificName}</span>}
              <span className="ml-auto shrink-0">
                {f.lesionCount} LESION{f.lesionCount === 1 ? '' : 'S'}
              </span>
              <span className="shrink-0">{formatPct(f.affectedRatio, 1)} AREA</span>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-2.5 text-xs font-hud tracking-[0.1em] text-rg-muted/70 leading-relaxed">
        CONFIDENCE IS PER DETECTION AND DOES NOT SUM TO 100%. AREA IS LESION
        PIXELS OVER THE WHOLE IMAGE.
      </p>
    </div>
  );
}
