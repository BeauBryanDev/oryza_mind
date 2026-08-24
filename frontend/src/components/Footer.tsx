import { APP_NAME, APP_TAGLINE, APP_VERSION } from '../utils/constants';

export default function Footer() {
  
  return (
    <footer className="relative z-10 hud-panel px-5 py-3 mt-3 hidden lg:flex items-center gap-4">
      <div className="flex items-center gap-3">
        <span className="font-display neon-text-green tracking-widest text-sm">{APP_NAME}</span>
        <span className="font-hud text-sm text-rg-muted tracking-[0.2em]">{APP_VERSION}</span>
      </div>
      <div className="flex-1 h-px bg-gradient-to-r from-rg-border via-rg-neon/40 to-rg-border" />
      <div className="font-hud text-sm text-rg-muted tracking-[0.25em]">
        {APP_TAGLINE}
      </div>
      <div className="flex-1 h-px bg-gradient-to-r from-rg-border via-rg-neon/40 to-rg-border" />
      <div className="font-hud text-sm text-rg-muted tracking-[0.2em] flex items-center gap-1">
        BUILT WITH <span className="neon-text">♥</span> FOR RICE FARMERS
      </div>
    </footer>
  );
}
