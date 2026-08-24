import type { ReactNode } from 'react';
import { useAppStore } from '../stores/appStore';
import type { BottomNavKey } from '../stores/appStore';

const ITEMS: { key: BottomNavKey; label: string; icon: ReactNode }[] = [
  { key: 'home', label: 'HOME', icon: <path d="M3 12L12 4l9 8M5 10v10h14V10" /> },
  { key: 'history', label: 'HISTORY', icon: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></> },
  { key: 'scan', label: 'SCAN', icon: <><path d="M4 8V5a1 1 0 0 1 1-1h3"/><path d="M16 4h3a1 1 0 0 1 1 1v3"/><path d="M20 16v3a1 1 0 0 1-1 1h-3"/><path d="M8 20H5a1 1 0 0 1-1-1v-3"/><rect x="8" y="8" width="8" height="8" rx="1"/></> },
  { key: 'guide', label: 'GUIDE', icon: <><path d="M4 4h12a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M4 17a3 3 0 0 1 3-3h12"/></> },
  { key: 'settings', label: 'SETTINGS', icon: <><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2-1.2L14 3h-4l-.6 2.6a7 7 0 0 0-2 1.2l-2.3-1-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2 1.2L10 21h4l.6-2.6a7 7 0 0 0 2-1.2l2.3 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z"/></> },
];

export default function MobileBottomNav() {

  const { bottomNav, setBottomNav } = useAppStore();

  return (

    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-30 border-t border-rg-border bg-rg-bg/95 backdrop-blur-md">
      <ul className="grid grid-cols-5">
        {ITEMS.map((it) => {
          const active = bottomNav === it.key;
          const isScan = it.key === 'scan';
          
          return (
            <li key={it.key}>
              <button
                onClick={() => setBottomNav(it.key)}
                aria-label={it.label}
                className={`w-full py-2.5 flex flex-col items-center gap-1 transition
                  ${active ? 'neon-text-green' : 'text-rg-muted hover:text-rg-neon'}`}
              >
                <span className={`w-8 h-8 rounded-md flex items-center justify-center
                  ${isScan && active ? 'border border-rg-accent shadow-[0_0_16px_rgba(199,240,0,0.5)]' : ''}
                  ${active && !isScan ? 'border border-rg-neon/50' : ''}`}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    {it.icon}
                  </svg>
                </span>
                <span className="font-hud text-xs tracking-[0.2em]">{it.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
