import { useAnalysisStore } from '../stores/analysisStore';
import { useSpikeStore } from '../stores/spikeStore';
import SegmentationViewer from './SegmentationViewer';
import SpikeResultViewer from './SpikeResultViewer';
import FindingsList from './FindingsList';
import ConfidenceCard from './ConfidenceCard';
import DiseaseCard from './DiseaseCard';
import SeverityCard from './SeverityCard';
import RecommendationsPanel from './RecommendationsPanel';
import riceLeafIcon from '../assets/rice_leaf_icon.svg';

export default function DashboardPanel() {

  const { result, stage, error } = useAnalysisStore();
  const spike = useSpikeStore((s) => s.result);
  const primary = result?.primaryDisease ?? null;

  return (

    <section aria-label="Analysis results" className="hud-panel hud-corners p-5 h-full flex flex-col gap-3 overflow-y-auto rg-scroll">
      <span className="corner-tl" /><span className="corner-tr" /><span className="corner-bl" /><span className="corner-br" />

      <header className="flex items-center gap-2">
        <span className="w-7 h-7 rounded-md border border-rg-border flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
        </span>
        <h2 className="font-display neon-text-green tracking-widest text-base">3. ANALYSIS RESULTS</h2>
      </header>

      {!result && !spike && stage === 'IDLE' && <EmptyState />}

      {error && (
        <div className="hud-panel px-3 py-2 border-rg-accent/60 text-rg-accent font-hud tracking-[0.15em] text-xs">
          {error}
        </div>
      )}

      {/* Independent of the leaf analysis: a farmer can check panicles without
          ever uploading a leaf. */}
      {spike && (
        <div className="flex flex-col gap-3 fade-in">
          <SpikeResultViewer />

          {/* An answer from the model's own knowledge is labelled, never
              presented as if it came from the corpus. */}
          {spike.grounded === false && (
            <div className="hud-panel px-3 py-2 border-rg-accent/60 text-rg-accent font-hud tracking-[0.1em] text-xs">
              ⚠ NOT FROM THE ORYZAMIND SOURCES — general agronomic knowledge.
              Confirm with your local extension service before spraying.
            </div>
          )}

          {spike.recommendations && spike.recommendations.length > 0 && (
            <RecommendationsPanel items={spike.recommendations} title="PANICLE MANAGEMENT" />
          )}

          {spike.citations && spike.citations.length > 0 && (
            <details className="hud-panel px-3 py-2">
              <summary className="font-hud text-sm text-rg-muted tracking-[0.25em] cursor-pointer hover:text-rg-neon">
                PANICLE SOURCES ({new Set(spike.citations.map((c) => c.documentTitle)).size})
              </summary>
              <ul className="mt-2 flex flex-col gap-1">
                {/* One line per document: several passages from one handbook
                    page would otherwise repeat the same title. */}
                {[...new Map(spike.citations.map((c) => [c.documentTitle, c])).values()].map((c) => (
                  <li key={c.chunkId} className="text-sm text-rg-muted leading-snug">
                    {c.documentTitle}
                    {c.organization ? ` (${c.organization})` : ''}
                    {c.pageStart ? `, p. ${c.pageStart}` : ''}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-3 fade-in">
          <SegmentationViewer />

          {/* An empty findings list is a healthy result, not a failure. */}
          {result.diseases.length === 0 ? (
            <div className="hud-panel p-4 text-center">
              <div className="font-display neon-text-green tracking-widest text-sm">
                NO DISEASE DETECTED
              </div>
              <p className="text-sm text-rg-muted mt-1">
                No lesions were found above the detection thresholds.
              </p>
            </div>
          ) : (
            <>
              <FindingsList findings={result.diseases} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {primary && <ConfidenceCard confidence={primary.confidence} />}
                {primary && (
                  <DiseaseCard disease={primary} othersCount={result.diseases.length - 1} />
                )}
              </div>
              <SeverityCard
                severity={result.overallSeverity}
                affectedRatio={result.overallAffectedRatio}
              />
              {result.recommendations && <RecommendationsPanel items={result.recommendations} />}
            </>
          )}
        </div>
      )}

      {!result && !spike && stage !== 'IDLE' && (
        
        <div className="flex-1 flex items-center justify-center py-10">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto rounded-full border-2 border-rg-neon/40 border-t-rg-accent animate-spin" />
            <div className="mt-4 font-hud tracking-[0.25em] text-xs neon-text-green">PROCESSING...</div>
            <div className="mt-1 text-sm text-rg-muted">This may take a few seconds</div>
          </div>
        </div>
      )}
    </section>
  );
}

function EmptyState() {

  return (

    <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 py-10">
      <div className="relative w-24 h-24">
        <div className="absolute inset-0 border border-rg-neon/40 rounded-lg rotate-45" />
        <div className="absolute inset-2 border border-rg-neon/25 rounded-lg rotate-45" />
        <div className="absolute inset-0 flex items-center justify-center">
          <img src={riceLeafIcon} alt="" width={40} height={40} className="opacity-80" />
        </div>
      </div>
      <div className="font-display neon-text-green tracking-widest text-sm">AWAITING ANALYSIS</div>
      <p className="text-xs text-rg-muted max-w-[260px] leading-relaxed">
        Upload up to 3 rice leaf photos and press <span className="neon-text">ANALYZE</span> for a
        full diagnosis.
      </p>
      <div className="grid grid-cols-2 gap-2 w-full mt-2">
        <StubCard label="SEGMENTATION" />
        <StubCard label="FINDINGS" />
        <StubCard label="CONFIDENCE" />
        <StubCard label="SEVERITY" />
      </div>
    </div>
  );
}

function StubCard({ label }: { label: string }) {

  return (

    <div className="hud-panel px-3 py-2 opacity-60">
      <div className="font-hud text-xs tracking-[0.2em] text-rg-muted">{label}</div>
      <div className="font-display text-xs neon-text-green mt-1">—</div>
    </div>
  );
}
