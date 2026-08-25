import { useAnalysisStore } from '../stores/analysisStore';
import type { PipelineStage } from '../types';
import { VISION_MODEL_LABEL } from '../utils/constants';

 
const ORDER: { key: PipelineStage; label: string }[] = [
  { key: 'UPLOADING', label: 'Uploading images' },
  { key: 'ANALYZING', label: `${VISION_MODEL_LABEL} + knowledge base` },
  { key: 'COMPLETED', label: 'Result ready' },
];
// It is talkking long from from backend to process,  I  might enfornce  betteer scan annimation
function stageIndex(s: PipelineStage): number {

  return ORDER.findIndex((o) => o.key === s);
}

export default function PipelineStatus() {

  const { stage, progress, error } = useAnalysisStore();
  if (stage === 'IDLE') return null;

  const currentIdx = stageIndex(stage);
  const indeterminate = stage === 'ANALYZING' || stage === 'GENERATING_DIAGNOSIS';

  return (
                     
    <div className={`hud-panel px-3 py-3 fade-in ${stage !== 'COMPLETED' && stage !== 'ERROR' ? 'scanner' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-hud text-sm tracking-[0.25em] neon-text-green">
          {error
            ? 'PIPELINE ERROR'
            : stage === 'COMPLETED'
              ? 'ANALYSIS COMPLETE'
              : indeterminate
                ? 'ANALYZING...'
                : 'UPLOADING...'}
        </span>
        {!indeterminate && (
          <span className="font-display text-xs neon-text tabular-nums">
            {Math.round(progress)}%
          </span>
        )}
      </div>

      <div className="progress-track mb-3">
        <div
          className={`progress-fill ${indeterminate ? 'animate-pulse' : ''}`}
          style={{ width: indeterminate ? '100%' : `${progress}%` }}
        />
      </div>

      <ul className="space-y-1">
        {ORDER.map((s, i) => {
          const done = currentIdx > i || stage === 'COMPLETED';
          const active = currentIdx === i && stage !== 'COMPLETED' && stage !== 'ERROR';

          return (

            <li key={s.key} className="flex items-center gap-2 text-sm font-hud tracking-[0.15em]">
              <span className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center
                ${done ? 'bg-rg-neon/80 border-rg-neon text-black' : active ? 'border-rg-accent' : 'border-rg-neon/25'}`}>
                {done ? '✓' : active ? <span className="w-1.5 h-1.5 bg-rg-accent rounded-full animate-pulse" /> : ''}
              </span>
              <span className={`${done ? 'text-rg-text' : active ? 'neon-text' : 'text-rg-muted'}`}>
                {s.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
