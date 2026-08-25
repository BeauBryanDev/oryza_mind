import type { WeatherData } from '../types';

export default function WeatherWidget({
  weather,
  compact = false,
  mobile = false,
}: {
  weather: WeatherData | null;
  compact?: boolean;
  mobile?: boolean;
}) {
  if (!weather) {
    return (
      <div className={`hud-panel ${compact ? 'px-3 py-2' : 'px-4 py-3'} min-w-[160px]`}>
        <div className="font-hud text-sm text-rg-muted tracking-[0.2em]">CURRENT WEATHER</div>
        <div className="font-display neon-text-green">--°C</div>
      </div>
    );
  }

  if (mobile) {
    return (
      <div className="flex items-center gap-2 justify-center">
        <CloudIcon />
        <div className="text-center">
          <div className="font-hud text-xs text-rg-muted tracking-[0.2em]">CURRENT WEATHER</div>
          <div className="font-display text-xl neon-text-green leading-none">{weather.temperatureC}°C</div>
          <div className="font-hud text-xs text-rg-muted tracking-[0.2em]">{weather.city.toUpperCase()}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`hud-panel ${compact ? 'px-4 py-2' : 'px-5 py-3'} flex items-center gap-3`}>
      <CloudIcon />
      <div>
        <div className="font-hud text-sm text-rg-muted tracking-[0.25em]">CURRENT WEATHER</div>
        <div className="flex items-baseline gap-3">
          <span className="font-display text-2xl neon-text-green leading-none">{weather.temperatureC}°C</span>
          <span className="font-hud text-sm text-rg-muted tracking-[0.2em]">HUMIDITY <span className="neon-text-green">{weather.humidityPct}%</span></span>
          <span className="font-hud text-sm text-rg-muted tracking-[0.2em]">RAIN <span className="neon-text-green">{weather.rainPct}%</span></span>
        </div>
        <div className="font-hud text-xs text-rg-muted tracking-[0.25em] mt-0.5">{weather.city.toUpperCase()}</div>
      </div>
    </div>
  );
}

function CloudIcon() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="drop-shadow-[0_0_8px_rgba(140,255,77,0.6)]">
      <path d="M17.5 15a4.5 4.5 0 1 0-1.36-8.79A6 6 0 0 0 5 10.5a4 4 0 0 0 .5 8h12z"/>
      <path d="M8 20l1-2"/><path d="M12 20l1-2"/><path d="M16 20l1-2"/>
    </svg>
  );
}
