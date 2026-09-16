import { useRef, useState } from 'react';
import { useSpike } from '../hooks/useSpike';
import { MAX_SPIKE_IMAGES, SPIKE_MODEL_LABEL } from '../utils/constants';
import { HEALTHY, UNHEALTHY } from './SpikeResultViewer';
import SpikePipelineStatus from './SpikePipelineStatus';

// The second drop zone. Deliberately a separate panel with its own store and
// its own endpoint: a panicle photo sent to the leaf detector, or the reverse,
// returns a confident answer to the wrong question. wrrong diagnosis.
export default function SpikeUploadPanel() {

  const { images, error, result, running, handleFiles, removeImage, run } = useSpike();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  return (

    <section aria-label="Rice spike panel" className="hud-panel hud-corners p-5 flex flex-col gap-4">
      <span className="corner-tl" /><span className="corner-tr" /><span className="corner-bl" /><span className="corner-br" />

      <header className="flex items-center gap-2">
        <span className="w-7 h-7 rounded-md border border-rg-border flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="2"><path d="M12 22V8"/><path d="M12 8c0-3 2-5 5-5 0 3-2 5-5 5z"/><path d="M12 13c0-3-2-5-5-5 0 3 2 5 5 5z"/></svg>
        </span>
        <h2 className="font-display neon-text-green tracking-widest text-base">RICE SPIKE DETECTION</h2>
      </header>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {

          e.preventDefault(); setDragOver(false);
          if (e.dataTransfer.files) handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}

        role="button"

        tabIndex={0}

        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
        aria-label="Drag and drop rice spike image area"
        className={`relative cursor-pointer rounded-xl border-2 border-dashed transition-all
          ${dragOver ? 'border-rg-accent bg-rg-accent/5' : 'border-rg-neon/40 hover:border-rg-neon/70 hover:bg-rg-neon/[0.03]'}
          p-4 flex flex-col items-center justify-center text-center min-h-[140px] sm:min-h-[170px]`}
      >
        <div className="relative w-14 h-14 sm:w-18 sm:h-18 mb-2">
          <div className="absolute inset-0 border border-rg-neon/50 rotate-45 rounded-md" />
          <div className="absolute inset-2 border border-rg-neon/30 rotate-45 rounded-md" />
          <div className="absolute inset-0 flex items-center justify-center">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="1.5" className="drop-shadow-[0_0_10px_rgba(140,255,77,0.7)]">
              <path d="M12 21V9"/><path d="M12 9c0-3.5 2.5-6 6-6 0 3.5-2.5 6-6 6z"/><path d="M12 15c0-3.5-2.5-6-6-6 0 3.5 2.5 6 6 6z"/>
            </svg>
          </div>
        </div>
        <div className="font-display neon-text-green tracking-[0.2em] text-sm">DRAG AND DROP</div>
        <div className="font-hud text-rg-muted tracking-[0.4em] text-xs mt-0.5">YOUR SPIKE PHOTOS HERE</div><p className="text-xs text-rg-muted mt-0.5">this is only for spike detection</p>
        <div className="mt-3 chip">UP TO {MAX_SPIKE_IMAGES} IMAGES</div>

        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>

      {error && (
        <div className="rounded-md border border-rg-accent/50 bg-rg-accent/10 px-3 py-2 text-rg-accent font-hud tracking-[0.15em] text-xs fade-in">
          ⚠ {error}
        </div>
      )}

      {images.length > 0 && (
        <div>
          <div className="font-hud text-xs text-rg-muted tracking-[0.25em] mb-2">
            SELECTED SPIKES ({images.length}/{MAX_SPIKE_IMAGES})
          </div>
          <div className="grid grid-cols-3 gap-2">
            {images.map((img) => (
              <div key={img.id} className="relative aspect-square rounded-md overflow-hidden border border-rg-neon/40">
                <img src={img.previewUrl} alt={img.name} className="w-full h-full object-cover" />
                <button
                  onClick={(e) => { e.stopPropagation(); removeImage(img.id); }}
                  aria-label={`Remove ${img.name}`}
                  className="absolute top-1 right-1 w-6 h-6 rounded bg-black/70 border border-rg-neon/50 text-rg-neon flex items-center justify-center hover:bg-rg-accent hover:text-black transition"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <SpikePipelineStatus />

      {/* Verdict only. The photos, every confidence, the sources and the
          management plan render in the results panel, like the leaf flow. */}
      {result && (
        <div className="flex flex-col gap-2 fade-in">
          <div className="font-hud text-xs text-rg-muted tracking-[0.25em]">
            RESULT — {result.modelLabel}
          </div>
          {/* Red for unhealthy, green for healthy. rg-accent is the HUD's
              yellow-green and does not read as a warning next to rg-neon. */}
          {result.predictions.map((p) => (
            <div
              key={p.imageIndex}
              className="rounded-md border px-3 py-2 flex items-center justify-between gap-3"
              style={{
                borderColor: p.label === 'UNHEALTHY' ? `${UNHEALTHY}99` : `${HEALTHY}66`,
                backgroundColor: p.label === 'UNHEALTHY' ? `${UNHEALTHY}1A` : `${HEALTHY}0D`,
              }}
            >
              <span className="font-hud text-xs text-rg-muted truncate">
                {p.filename ?? `IMAGE ${p.imageIndex + 1}`}
              </span>
              <span
                className="font-display tracking-[0.15em] text-xs whitespace-nowrap"
                style={{ color: p.label === 'UNHEALTHY' ? UNHEALTHY : HEALTHY }}
              >
                {p.label} {(p.confidence * 100).toFixed(0)}%
                {/* A score near the threshold is shown as provisional rather
                    than rounded up into a clean verdict. */}
                {p.uncertain && <span className="text-rg-muted"> · BORDERLINE</span>}
              </span>
            </div>
          ))}

        </div>
      )}

      <button
        className="neon-btn w-full py-2.5"
        onClick={run}
        disabled={images.length === 0 || running}
        aria-label="Check rice spikes"
      >
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-sm">{running ? 'CHECKING...' : 'CHECK SPIKES'}</span>
          <span className="text-xs tracking-[0.3em] font-hud opacity-80">{SPIKE_MODEL_LABEL}</span>
        </div>
      </button>
    </section>
  );
}
