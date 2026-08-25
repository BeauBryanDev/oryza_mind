import { confidenceLabel, formatPct } from '../utils/formatters';

export default function ConfidenceCard({ confidence }: { confidence: number }) {

  return (
    
    <div className="hud-panel p-4 flex-1">
      <div className="font-hud text-sm tracking-[0.25em] text-rg-muted">MODEL CONFIDENCE</div>
      <div className="flex items-center gap-3 mt-2">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="1.5" className="shrink-0 drop-shadow-[0_0_8px_rgba(140,255,77,0.6)]">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <div className="font-display text-4xl neon-text-green tabular-nums leading-none">{formatPct(confidence, 1)}</div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span className="font-hud text-sm tracking-[0.25em] neon-text-green">{confidenceLabel(confidence)}</span>
      </div>
      <div className="progress-track mt-2">
        <div className="progress-fill" style={{ width: `${Math.round(confidence * 100)}%` }} />
      </div>
    </div>
  );
}
