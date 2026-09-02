import Header from '../components/Header';
import Footer from '../components/Footer';
import UploadPanel from '../components/UploadPanel';
import SpikeUploadPanel from '../components/SpikeUploadPanel';
import ChatPanel from '../components/ChatPanel';
import DashboardPanel from '../components/DashboardPanel';
import MobileBottomNav from '../components/MobileBottomNav';
import { useAppStore } from '../stores/appStore';

// Responsive grid: three fluid columns filling the viewport. The results panel
// carries the most content -- findings, cards, recommendations -- so it gets
// the widest share after chat. minmax(0,...) lets a column shrink below its
// content width; without it a long chat line or a wide dosage table pushes the
// grid past the viewport and creates a horizontal scrollbar.
const DESKTOP_COLUMNS = 'minmax(240px, 0.95fr) minmax(0, 1.75fr) minmax(0, 1.75fr)';


const DESKTOP_ROWS = 'minmax(0, 1fr)';  

export default function Home() {

  const { mobileTab, setBottomNav } = useAppStore();

  return (

    // dvh locks the root to exactly the viewport height so the page cannot
    // grow — panels must scroll internally instead of pushing the page down.
    <div className="relative z-10 h-dvh flex flex-col overflow-hidden">
      <div className="w-full flex-1 min-h-0 flex flex-col gap-2 lg:gap-4 px-2 sm:px-4 lg:px-14 xl:px-20 py-2 lg:py-6 pb-20 lg:pb-6 overflow-hidden">
        <Header />

        {/* ── Desktop: 3-column grid filling the viewport ── */}
        <main
          className="hidden lg:grid gap-4 flex-1 min-h-0 overflow-hidden"
          style={{
            gridTemplateColumns: DESKTOP_COLUMNS,
            gridTemplateRows: DESKTOP_ROWS,
          }}
        >
          <div className="min-h-0 overflow-y-auto flex flex-col gap-4">
            <UploadPanel />
            <SpikeUploadPanel />
          </div>

          <div className="min-h-0 min-w-0 h-full flex flex-col overflow-hidden">
            <ChatPanel />
          </div>

          <div className="min-h-0 h-full overflow-hidden">
            <DashboardPanel />
          </div>
        </main>

        {/* Mobile: single-panel view driven by bottom nav ── */}
        <main className="lg:hidden flex-1 min-h-0 overflow-hidden">
          {/* HOME → Chat */}
          {mobileTab === 'chat' && (
            <div className="h-full">
              <ChatPanel />
            </div>
          )}

          {/* SCAN → Upload panels */}
          {mobileTab === 'scan' && (
            <div className="h-full overflow-y-auto rg-scroll flex flex-col gap-2 pb-4">
              <UploadPanel />
              <SpikeUploadPanel />
            </div>
          )}

          {/* HISTORY → Analysis results */}
          {mobileTab === 'history' && (
            <div className="h-full overflow-y-auto rg-scroll flex flex-col gap-2 pb-4">
              <DashboardPanel />
            </div>
          )}

          {/* GUIDE → Disease field guide */}
          {mobileTab === 'guide' && (
            <div className="h-full overflow-y-auto rg-scroll pb-4">
              <div className="hud-panel p-4 flex flex-col gap-3">
                <h2 className="font-display neon-text-green tracking-widest text-base">FIELD GUIDE</h2>
                <div className="h-px bg-gradient-to-r from-transparent via-rg-neon/40 to-transparent" />
                <p className="text-rg-muted font-hud tracking-wide text-xs leading-relaxed">
                  Ask the chat assistant about any rice disease — its symptoms, treatment, or
                  prevention. Answers are drawn from agronomic references and cite their source.
                </p>
                <div className="flex flex-col gap-2">
                  {[
                    { name: 'Rice Blast',        tag: 'Magnaporthe oryzae',    color: 'neon-text-green' },
                    { name: 'Brown Spot',         tag: 'Bipolaris oryzae',      color: 'neon-text' },
                    { name: 'Bacterial Blight',   tag: 'Xanthomonas oryzae',    color: 'neon-text-green' },
                    { name: 'Sheath Blight',      tag: 'Rhizoctonia solani',    color: 'neon-text' },
                    { name: 'False Smut',         tag: 'Ustilaginoidea virens', color: 'neon-text-green' },
                  ].map((d) => (
                    <button
                      key={d.name}
                      onClick={() => setBottomNav('home')}
                      className="hud-panel px-3 py-2.5 flex items-center justify-between text-left hover:border-rg-neon/60 transition"
                    >
                      <div>
                        <div className={`font-display text-xs tracking-widest ${d.color}`}>{d.name}</div>
                        <div className="font-hud text-xs text-rg-muted tracking-wide mt-0.5 italic">{d.tag}</div>
                      </div>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-rg-muted shrink-0">
                        <path d="M9 18l6-6-6-6" />
                      </svg>
                    </button>
                  ))}
                </div>
                <p className="text-xs text-rg-muted font-hud tracking-wide text-center">
                  Tap a disease to chat with the AI assistant about it
                </p>
              </div>
            </div>
          )}

          {/* SETTINGS → System status */}
          {mobileTab === 'settings' && (
            <div className="h-full overflow-y-auto rg-scroll pb-4">
              <div className="hud-panel p-4 flex flex-col gap-3">
                <h2 className="font-display neon-text-green tracking-widest text-base">SETTINGS</h2>
                <div className="h-px bg-gradient-to-r from-transparent via-rg-neon/40 to-transparent" />
                <div className="flex flex-col gap-2">
                  {[
                    { label: 'BACKEND STATUS', desc: 'AI inference server connection' },
                    { label: 'KNOWLEDGE BASE',  desc: 'Agronomic reference database' },
                    { label: 'SPIKE MODEL',     desc: 'Panicle detection model' },
                  ].map((s) => (
                    <div key={s.label} className="hud-panel px-3 py-2.5 flex items-center justify-between">
                      <div>
                        <div className="font-display text-xs tracking-widest neon-text-green">{s.label}</div>
                        <div className="font-hud text-xs text-rg-muted tracking-wide mt-0.5">{s.desc}</div>
                      </div>
                      <div className="status-dot shrink-0" />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-rg-muted font-hud tracking-wide text-center mt-2">
                  OryzaMind v1.0 · For field diagnostics only
                </p>
              </div>
            </div>
          )}
        </main>

        <Footer />
      </div>

      <MobileBottomNav />
    </div>
  );
}
