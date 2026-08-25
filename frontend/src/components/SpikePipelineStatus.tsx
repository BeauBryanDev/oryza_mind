import { useSpikeStore } from '../stores/spikeStore';
import { SPIKE_MODEL_LABEL } from '../utils/constants';

 
const ORDER = [
  { key: 'UPLOADING', label: 'Uploading spike images' },
  { key: 'ANALYZING', label: `${SPIKE_MODEL_LABEL} + knowledge base` },
  { key: 'COMPLETED', label: 'Result ready' },
] as const;

 
const UPLOAD_CEILING = 45;

export default function SpikePipelineStatus() {

  const { running, progress, result, error } = useSpikeStore();


  if (!running && !result) return null;

  const done = !running && !!result;
  const indeterminate = running && progress >= UPLOAD_CEILING;
  const currentIdx = done ? ORDER.length : indeterminate ? 1 : 0;

  return (

    <div className={`hud-panel px-3 py-3 fade-in ${running ? 'scanner' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-hud text-sm tracking-[0.25em] neon-text-green">
          {error
            ? 'SPIKE CHECK ERROR'
            : done
              ? 'SPIKE CHECK COMPLETE'
              : indeterminate
                ? 'CHECKING...'
                : 'UPLOADING...'}
        </span>
        {!indeterminate && !done && (
          <span className="font-display text-xs neon-text tabular-nums">
            {Math.round(progress)}%
          </span>
        )}
      </div>

      <div className="progress-track mb-3">
        <div
          className={`progress-fill ${indeterminate ? 'animate-pulse' : ''}`}
          style={{ width: indeterminate || done ? '100%' : `${progress}%` }}
        />
      </div>

      <ul className="space-y-1">
        {ORDER.map((s, i) => {

          const isDone = currentIdx > i;
          const active = currentIdx === i && !error;
          
          return (
            <li key={s.key} className="flex items-center gap-2 text-sm font-hud tracking-[0.15em]">
              <span className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center
                ${isDone ? 'bg-rg-neon/80 border-rg-neon text-black' : active ? 'border-rg-accent' : 'border-rg-neon/25'}`}>
                {isDone ? '✓' : active ? <span className="w-1.5 h-1.5 bg-rg-accent rounded-full animate-pulse" /> : ''}
              </span>
              <span className={`${isDone ? 'text-rg-text' : active ? 'neon-text' : 'text-rg-muted'}`}>
                {s.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
