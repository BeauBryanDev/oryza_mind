import { useEffect, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { useWeather } from '../hooks/useWeather';
import { formatClock, formatDate } from '../utils/formatters';
import { APP_BRAND, SPIKE_MODEL_LABEL, VISION_MODEL_LABEL } from '../utils/constants';
import riceLeafIcon from '../assets/rice_leaf_icon.svg';
import WeatherWidget from './WeatherWidget';

export default function Header() {
  const { modelOnline, spikeModelOnline, serviceOnline } = useAppStore();
  const { data: weather } = useWeather();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="relative z-10">
      {/* Desktop header */}
      <div className="hidden lg:block">
        <div className="hud-panel hud-corners px-5 py-3 flex items-center gap-4">
          <span className="corner-tl" /><span className="corner-tr" /><span className="corner-bl" /><span className="corner-br" />
          <Logo />
          <div className="ml-1">
            <h1 className="font-display text-2xl neon-text-green tracking-widest leading-none">{APP_BRAND}</h1>
            <p className="font-hud text-sm text-rg-muted tracking-[0.3em] mt-1">AI AGENT FOR RICE DISEASE DETECTION</p>
          </div>

          <div className="flex-1" />

          <StatusPill label={`${VISION_MODEL_LABEL} MODEL`} online={modelOnline} icon="AI" />
          <StatusPill label={`${SPIKE_MODEL_LABEL} MODEL`} online={spikeModelOnline} icon="AI" />
          <StatusPill label="CLIMATE SERVICE" online={serviceOnline} icon="☁" />
          <WeatherWidget compact weather={weather} />

          <div className="hud-panel px-4 py-2 min-w-[128px] text-right">
            <div className="font-display text-xl neon-text-green tracking-widest tabular-nums">{formatClock(now)}</div>
            <div className="font-hud text-sm text-rg-muted tracking-[0.2em]">{formatDate(now)}</div>
          </div>
        </div>
      </div>

      {/* Mobile header — fully responsive */}
      <div className="lg:hidden">
        {/* Top bar: logo + brand + clock */}
        <div className="hud-panel mx-0 px-3 py-2 flex items-center gap-2 min-w-0">
          <Logo small />

          {/* Brand — shrinks gracefully */}
          <div className="flex-1 min-w-0">
            <h1 className="font-display neon-text-green tracking-widest leading-none truncate
                           text-base sm:text-lg">
              {APP_BRAND}
            </h1>
            <p className="hidden xs:block font-hud text-xs text-rg-muted tracking-[0.18em] mt-0.5 truncate">
              AI RICE DISEASE DETECTION
            </p>
          </div>

          {/* Live clock — right side */}
          <div className="shrink-0 text-right">
            <div className="font-display text-sm sm:text-base neon-text-green tracking-widest tabular-nums leading-none">
              {formatClock(now)}
            </div>
            <div className="font-hud text-xs text-rg-muted tracking-[0.15em] mt-0.5 hidden sm:block">
              {formatDate(now)}
            </div>
          </div>
        </div>

        {/* Status bar — wraps cleanly on tiny screens */}
        <div className="mx-0 mt-1.5 hud-panel px-3 py-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          {/* Model status */}
          <div className="flex items-center gap-1.5">
            <span className={`status-dot ${!modelOnline && 'opacity-30'}`}
              style={!modelOnline ? { background: '#C7F000', boxShadow: '0 0 8px #C7F000' } : undefined} />
            <span className={`font-hud text-xs tracking-[0.18em] ${modelOnline ? 'neon-text-green' : 'text-rg-accent'}`}>
              VISION {modelOnline ? 'ON' : 'OFF'}
            </span>
          </div>

          {/* Spike model status */}
          <div className="flex items-center gap-1.5">
            <span className={`status-dot ${!spikeModelOnline && 'opacity-30'}`}
              style={!spikeModelOnline ? { background: '#C7F000', boxShadow: '0 0 8px #C7F000' } : undefined} />
            <span className={`font-hud text-xs tracking-[0.18em] ${spikeModelOnline ? 'neon-text-green' : 'text-rg-accent'}`}>
              SPIKE {spikeModelOnline ? 'ON' : 'OFF'}
            </span>
          </div>

          {/* Spacer pushes weather to the right */}
          <div className="flex-1" />

          {/* Weather compact */}
          {weather && (
            <div className="flex items-center gap-2 text-rg-muted font-hud text-xs tracking-[0.15em]">
              <span>☁ {weather.rainPct ?? '--'}%</span>
              <span>💧 {weather.humidityPct ?? '--'}%</span>
              {weather.temperatureC != null && (
                <span className="neon-text-green">{Math.round(weather.temperatureC)}°C</span>
              )}
            </div>
          )}
        </div>
      </div>

    </header>
  );
}

function Logo({ small = false }: { small?: boolean }) {
  const size = small ? 44 : 64;
  return (
    <div className="shrink-0" style={{ width: size, height: size }}>
      <img src={riceLeafIcon} alt={APP_BRAND} width={size} height={size}
        className="drop-shadow-[0_0_10px_rgba(140,255,77,0.6)]" />
    </div>
  );
}

function StatusPill({ label, online, icon, compact = false }: { label: string; online: boolean; icon: string; compact?: boolean }) {
  return (
    <div className={`hud-panel ${compact ? 'px-2 py-1.5' : 'px-3 py-2'} flex items-center gap-2`}>
      <div className={`${compact ? 'w-6 h-6 text-sm' : 'w-8 h-8 text-xs'} rounded-md border border-rg-border flex items-center justify-center font-display neon-text-green`}>{icon}</div>
      <div>
        <div className={`font-hud ${compact ? 'text-xs' : 'text-sm'} text-rg-muted tracking-[0.2em]`}>{label}</div>
        <div className="flex items-center gap-1.5">
          <span className={`status-dot ${!online && 'opacity-30'}`} style={!online ? { background: '#C7F000', boxShadow: '0 0 10px #C7F000' } : undefined} />
          <span className={`font-display ${compact ? 'text-sm' : 'text-sm'} tracking-widest ${online ? 'neon-text-green' : 'text-rg-accent'}`}>
            {online ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </div>
  );
}
