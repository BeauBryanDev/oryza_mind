import { useRef, useState } from 'react';
import { useUpload } from '../hooks/useUpload';
import { useAnalysis } from '../hooks/useAnalysis';
import { useAnalysisStore } from '../stores/analysisStore';
import { MAX_IMAGES } from '../utils/constants';
import PipelineStatus from './PipelineStatus';

export default function UploadPanel() {

  const { images, error, handleFiles, removeImage } = useUpload();
  const { run } = useAnalysis();
  const stage = useAnalysisStore((s) => s.stage);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const isRunning = stage !== 'IDLE' && stage !== 'COMPLETED' && stage !== 'ERROR';

  return (

    // No h-full: this column now stacks two panels and scrolls, so filling the
    // column height would push the spike panel out of view.
    <section aria-label="Upload panel" className="hud-panel hud-corners p-5 flex flex-col gap-4">
      <span className="corner-tl" /><span className="corner-tr" /><span className="corner-bl" /><span className="corner-br" />

      <header className="flex items-center gap-2">
        <span className="w-7 h-7 rounded-md border border-rg-border flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="2"><path d="M4 16l4-4 4 4 8-8"/><path d="M14 4h6v6"/></svg>
        </span>
        <h2 className="font-display neon-text-green tracking-widest text-lg">1. RICE LEAVE DETECTION</h2>
      </header>

      {/* Drop zone */}
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
        aria-label="Drag and drop image area"
        className={`relative cursor-pointer rounded-xl border-2 border-dashed transition-all
          ${dragOver ? 'border-rg-accent bg-rg-accent/5' : 'border-rg-neon/40 hover:border-rg-neon/70 hover:bg-rg-neon/[0.03]'}
          p-6 flex flex-col items-center justify-center text-center min-h-[220px]`}
      >
        <div className="relative w-24 h-24 mb-3">
          <div className="absolute inset-0 border border-rg-neon/50 rotate-45 rounded-md" />
          <div className="absolute inset-3 border border-rg-neon/30 rotate-45 rounded-md" />
          <div className="absolute inset-0 flex items-center justify-center">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="1.5" className="drop-shadow-[0_0_10px_rgba(140,255,77,0.7)]">
              <path d="M12 15V3"/><path d="M7 8l5-5 5 5"/><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"/>
            </svg>
          </div>
        </div>
        <div className="font-display neon-text-green tracking-[0.2em] text-lg">DRAG AND DROP</div>
        <div className="font-hud text-rg-muted tracking-[0.2em] text-xs mt-1">YOUR LEAF PHOTOS HERE</div><p>this is only for leaf detection</p>
        <div className="mt-4 chip">UP TO {MAX_IMAGES} IMAGES</div>

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

      {/* Thumbnails */}
      {images.length > 0 && (
        <div>
          <div className="font-hud text-sm text-rg-muted tracking-[0.25em] mb-2">
            SELECTED IMAGES ({images.length}/{MAX_IMAGES})
          </div>
          <div className="grid grid-cols-3 gap-2">
            {images.map((img) => (
              <div key={img.id} className="relative aspect-square rounded-md overflow-hidden border border-rg-neon/40 group">
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

      {/* Pipeline status */}
      <PipelineStatus />

      <div className="sticky bottom-0 bg-rg-panel/95 backdrop-blur-sm pt-3 pb-1 mt-auto z-10 border-t border-rg-border/20">
        <button
          className="neon-btn w-full py-4 relative"
          onClick={run}
          disabled={images.length === 0 || isRunning}
          aria-label="Analyze images"
        >
          <div className="flex flex-col items-center gap-0.5">
            <span className="flex items-center gap-2 text-lg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="4"/></svg>
              {isRunning ? 'ANALYZING...' : 'ANALYZE'}
            </span>
            <span className="text-sm tracking-[0.3em] font-hud opacity-80">YOLO SEGMENTATION</span>
          </div>
        </button>
      </div>
    </section>
  );
}
