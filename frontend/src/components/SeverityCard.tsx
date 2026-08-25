import type { SeverityLevel } from '../types';
import { formatPct } from '../utils/formatters';

const CONFIG: Record<SeverityLevel, { label: string; fill: number; warn: boolean }> = {

  LOW: { label: 'LOW', fill: 2, warn: false },
  MODERATE: { label: 'MODERATE', fill: 4, warn: true },
  HIGH: { label: 'HIGH', fill: 6, warn: true },
  CRITICAL: { label: 'CRITICAL', fill: 8, warn: true },
};

export default function SeverityCard({

  severity,
  affectedRatio,
}: {
  severity: SeverityLevel;
  affectedRatio?: number;
}) {
  const cfg = CONFIG[severity];
  const total = 8;

  return (
    
    <div className="hud-panel p-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-md border border-rg-accent/60 flex items-center justify-center bg-rg-accent/10 shrink-0">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#C7F000" strokeWidth="2" strokeLinejoin="round">
            <path d="M12 3l10 18H2z"/><path d="M12 10v5"/><circle cx="12" cy="18" r="0.8" fill="#C7F000"/>
          </svg>
        </div>
        <div className="flex-1">
          <div className="font-hud text-sm tracking-[0.25em] text-rg-muted">
            ESTIMATED SEVERITY LEVEL
          </div>
          <div className="font-display text-xl neon-text tracking-widest mt-1">{cfg.label}</div>
          {affectedRatio !== undefined && (
            // Share of the photo showing lesions, not share of the plant.
            <div className="font-hud text-xs tracking-[0.15em] text-rg-muted mt-0.5">
              {formatPct(affectedRatio, 1)} OF IMAGE SHOWS LESIONS
            </div>
          )}
        </div>
        <div className="w-40 seg">
          {Array.from({ length: total }).map((_, i) => (
            <span key={i} className={i < cfg.fill ? (cfg.warn ? 'warn' : 'on') : ''} />
          ))}
        </div>
      </div>
    </div>
  );
}
