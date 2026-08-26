import { useState } from 'react';
import { useSpikeStore } from '../stores/spikeStore';
import { SPIKE_MODEL_LABEL } from '../utils/constants';
import type { SpikePrediction } from '../types';

// Green for a healthy panicle, red for an unhealthy one. Unlike the leaf
// findings there is no severity band to colour by no segementation
// the model is binary, sothe verdict itself is the colour.
export const UNHEALTHY = '#FF5A47';
export const HEALTHY = '#8CFF4D';

function colorFor(p: SpikePrediction): string {

  return p.label === 'UNHEALTHY' ? UNHEALTHY : HEALTHY;
}

export default function SpikeResultViewer() {

  const { result, resultPreviews } = useSpikeStore();
  const [active, setActive] = useState(0);
  const [zoom, setZoom] = useState(false);

  if (!result) return null;

  const predictions = result.predictions ?? [];
  const current = predictions[active] ?? predictions[0];

  if (!current) return null;

  // Absent after a refresh: previews are blob: URLs and die with the document.
  const preview = resultPreviews[current.imageIndex];
  const color = colorFor(current);

  return (

    <div className="hud-panel p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="font-hud text-sm tracking-[0.25em] text-rg-muted">
          SPIKE CHECK <span className="neon-text-green">({SPIKE_MODEL_LABEL})</span>
        </span>
      </div>

      <div
        className="relative rounded-lg overflow-hidden border-2 aspect-[16/9] bg-black"
        style={{ borderColor: color, boxShadow: `0 0 14px ${color}55` }}>
        {preview ? (
          <>
            <img src={preview} alt={`Rice panicle, ${current.label}`} className="w-full h-full object-cover" />
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
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#7FAF78" strokeWidth="1.5"><path d="M12 21V9"/><path d="M12 9c0-3.5 2.5-6 6-6 0 3.5-2.5 6-6 6z"/><path d="M12 15c0-3.5-2.5-6-6-6 0 3.5 2.5 6 6 6z"/></svg>
            <span className="font-hud text-xs text-rg-muted tracking-[0.2em]">PHOTO NOT AVAILABLE</span>
            <span className="text-sm text-rg-muted/80">Re-upload to see the image</span>
          </div>
        )}

        <div
          className="absolute top-2 left-2 px-2 py-1 rounded font-display tracking-[0.15em] text-sm bg-black/75"
          style={{ color, border: `1px solid ${color}` }}
        >
          {current.label} {(current.confidence * 100).toFixed(1)}%
        </div>

        {predictions.length > 1 && (
          <div className="absolute top-2 right-2 chip !text-rg-text !bg-black/70">
            IMAGE {active + 1} OF {predictions.length}
          </div>
        )}

        {current.uncertain && (
          <div className="absolute bottom-2 left-2 px-2 py-1 rounded bg-black/75 border border-rg-muted/50 font-hud text-xs tracking-[0.15em] text-rg-muted">
            BORDERLINE — NEAR THRESHOLD
          </div>
        )}
      </div>

      {predictions.length > 1 && (
        <div className="flex items-center justify-center gap-2 mt-2">
          {predictions.map((p, i) => (
            <button
              key={p.imageIndex}
              onClick={() => setActive(i)}
              aria-label={`View spike image ${i + 1}`}
              className="w-2.5 h-2.5 rounded-full transition"
              style={{
                backgroundColor: i === active ? colorFor(p) : 'transparent',
                border: `1px solid ${colorFor(p)}`,
                boxShadow: i === active ? `0 0 8px ${colorFor(p)}` : 'none',
              }}
            />
          ))}
        </div>
      )}

      {/* Every confidence, not just the active image: the batch verdict is the
          worst case, so the others must stay visible to justify it. */}
      <ul className="mt-3 flex flex-col gap-1.5">
        {predictions.map((p, i) => {
          const c = colorFor(p);
          return (
            <li key={p.imageIndex}>
              <button
                onClick={() => setActive(i)}
                className={`w-full text-left rounded-md px-2 py-1.5 transition ${i === active ? 'bg-rg-panel2/60' : 'hover:bg-rg-panel2/30'}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-hud text-xs text-rg-muted truncate">
                    {p.filename ?? `IMAGE ${p.imageIndex + 1}`}
                  </span>
                  <span className="font-display text-sm tabular-nums whitespace-nowrap" style={{ color: c }}>
                    {p.label} {(p.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                {/* One independent gauge per image. These are separate binary
                    decisions and do not sum to anything. */}
                <div className="mt-1 h-1.5 rounded-full bg-rg-panel2 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${Math.round(p.confidence * 100)}%`, backgroundColor: c }}
                  />
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="mt-2 flex items-center justify-between font-hud text-xs tracking-[0.2em] text-rg-muted">
        <span>OVERALL</span>
        <span style={{ color: result.overallLabel === 'UNHEALTHY' ? UNHEALTHY : HEALTHY }}>
          {result.overallLabel} — {result.unhealthyCount}/{result.totalCount} UNHEALTHY
        </span>
      </div>

      {zoom && preview && (
        <div
          role="dialog"
          onClick={() => setZoom(false)}
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-6"
        >
          <img
            src={preview}
            alt="Enlarged rice panicle"
            className="max-w-full max-h-full rounded border-2"
            style={{ borderColor: color, boxShadow: `0 0 40px ${color}88` }}
          />
        </div>
      )}
    </div>
  );
}
