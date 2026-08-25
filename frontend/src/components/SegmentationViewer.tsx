import { useState } from 'react';
import { useAnalysisStore } from '../stores/analysisStore';
import { VISION_MODEL_LABEL } from '../utils/constants';

// this is my favorite component in the app for computer vision stuff
export default function SegmentationViewer() {

  const { result, activeImageIndex, setActiveImageIndex } = useAnalysisStore();
  const [zoom, setZoom] = useState(false);

  const segs = result?.segmentations ?? [];
  const active = segs[activeImageIndex];
  const total = segs.length;

  return (
    <div className="hud-panel p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="font-hud text-sm tracking-[0.25em] text-rg-muted">
          SEGMENTATION MASK <span className="neon-text-green">({VISION_MODEL_LABEL})</span>
        </span>
      </div>

      <div className="relative rounded-lg overflow-hidden border border-rg-neon/40 aspect-[16/9] bg-black">
        {active ? (
          <>
            <img src={active.overlayUrl} alt="Segmented rice leaf" className="w-full h-full object-cover" />
            <SegOverlay />
            <div className="absolute top-2 right-2 chip !text-rg-text !bg-black/70">
              IMAGE {activeImageIndex + 1} OF {total}
            </div>
            <button
              onClick={() => setZoom(true)}
              aria-label="Enlarge image"
              className="absolute bottom-2 right-2 w-8 h-8 rounded bg-black/70 border border-rg-neon/50 text-rg-neon flex items-center justify-center hover:bg-rg-neon hover:text-black transition"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>
            </button>
          </>
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-center gap-2 p-4">
            <svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="#7FAF78" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 15l5-5 4 4 4-4 5 5"/></svg>
            <span className="font-hud text-xs text-rg-muted tracking-[0.2em]">NO ANALYSIS YET</span>
            <span className="text-sm text-rg-muted/80">Upload images and press ANALYZE</span>
          </div>
        )}
      </div>

      {total > 1 && (
        <div className="flex items-center justify-center gap-2 mt-2">
          {segs.map((_, i) => (
            <button
              key={i}
              onClick={() => setActiveImageIndex(i)}
              aria-label={`View image ${i + 1}`}
              className={`w-2 h-2 rounded-full transition ${i === activeImageIndex ? 'bg-rg-neon shadow-[0_0_8px_#8CFF4D]' : 'bg-rg-muted/40'}`}
            />
          ))}
        </div>
      )}

      {zoom && active && (
        <div
          role="dialog"
          onClick={() => setZoom(false)}
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-6"
        >
          <img src={active.overlayUrl} alt="Enlarged" className="max-w-full max-h-full rounded border border-rg-neon/50 shadow-[0_0_40px_rgba(140,255,77,0.5)]" />
        </div>
      )}
    </div>
  );
}

function SegOverlay() {
  // Decorative HUD scanning overlay
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 60" preserveAspectRatio="none">
      <defs>
        <linearGradient id="scanG" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#8CFF4D" stopOpacity="0"/>
          <stop offset="0.5" stopColor="#8CFF4D" stopOpacity="0.35"/>
          <stop offset="1" stopColor="#8CFF4D" stopOpacity="0"/>
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="98" height="58" fill="none" stroke="#8CFF4D" strokeOpacity="0.35" strokeWidth="0.2" strokeDasharray="1 1" />
      {/* Corner brackets */}
      <path d="M2 6 V2 H6" stroke="#C7F000" strokeWidth="0.35" fill="none"/>
      <path d="M94 2 H98 V6" stroke="#C7F000" strokeWidth="0.35" fill="none"/>
      <path d="M2 54 V58 H6" stroke="#C7F000" strokeWidth="0.35" fill="none"/>
      <path d="M94 58 H98 V54" stroke="#C7F000" strokeWidth="0.35" fill="none"/>
    </svg>
  );
}
