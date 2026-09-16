import { useEffect, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { useWeather } from '../hooks/useWeather';
import { formatClock, formatDate } from '../utils/formatters';
import { APP_BRAND, SPIKE_MODEL_LABEL, VISION_MODEL_LABEL } from '../utils/constants';
import riceLeafIcon from '../assets/rice_leaf_icon.svg';


// Backend Icons
import PythonIcon from "../assets/Python.svg";
import FastAPIIcon from "../assets/FastAPI.svg";
import OpenCVIcon from "../assets/OpenCV.svg";
import NumpyIcon from "../assets/Numpy.svg";
import SklearnIcon from "../assets/Sklearn.svg";
import TensorFlowIcon from "../assets/TensorFlow.svg";
import YOLOIcon  from "../assets/Ultralytics.png";

// Frontend Icons
import ReactIcon from "../assets/React.svg";
import TypeScriptIcon from "../assets/TypeScript.svg";
import TailwindIcon from "../assets/Tailwind.svg";
import ViteIcon from "../assets/Vite.svg";

// Gemini & Google Icons
import GeminiIcon from "../assets/GeminiIcon.png";
import GeminiLLMIcon from "../assets/GeminiLLM.png";
import GoogleIcon from "../assets/Google.svg";


// Types & Credit Data
type Credit = { src: string; label: string; link: string };

const BACKEND_CREDITS: Credit[] = [
  { src: PythonIcon, label: "Python", link: "https://www.python.org/" },
  { src: FastAPIIcon, label: "FastAPI", link: "https://fastapi.tiangolo.com/" },
  { src: OpenCVIcon, label: "OpenCV", link: "https://opencv.org/" },
  { src: NumpyIcon, label: "Numpy", link: "https://numpy.org/" },
  { src: SklearnIcon, label: "Sklearn", link: "https://scikit-learn.org/stable/" },
  { src: TensorFlowIcon, label: "TensorFlow", link: "https://www.tensorflow.org/api_docs/python/tf" },
  { src: YOLOIcon, label: "YOLO", link: "https://ultralytics.com/" },
];

const LLM_CREDITS: Credit[] = [
  { src: GeminiIcon, label: "Gemini", link: "https://ai.google.dev/" },
  { src: GeminiLLMIcon, label: "Gemini LLM", link: "https://ai.google.dev/" },
  { src: GoogleIcon, label: "Google AI Studio", link: "https://aistudio.google.com/" },
];

const FRONTEND_CREDITS: Credit[] = [
  { src: ReactIcon, label: "React", link: "https://reactjs.org/" },
  { src: TypeScriptIcon, label: "TypeScript", link: "https://www.typescriptlang.org/" },
  { src: TailwindIcon, label: "Tailwind", link: "https://tailwindcss.com/" },
  { src: ViteIcon, label: "Vite", link: "https://vitejs.dev/" },
];

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
          <div className="ml-1 flex items-center gap-3">
            <div>
              <h1 className="font-display text-xl neon-text-green tracking-widest leading-none">{APP_BRAND}</h1>
              <p className="font-hud text-xs text-rg-muted tracking-[0.25em] mt-1">AI AGENT FOR RICE DISEASE DETECTION</p>
            </div>
            <a
              href="https://aistudio.google.com/"
              target="_blank"
              rel="noopener noreferrer"
              title="Google AI Studio"
              className="shrink-0 transition hover:scale-105"
            >
              <img
                src={GoogleIcon}
                alt="Google AI Studio"
                className="h-[33px] w-auto object-contain drop-shadow-[0_0_8px_rgba(140,255,77,0.4)]"
              />
            </a>
            <a
              href="https://ai.google.dev/"
              target="_blank"
              rel="noopener noreferrer"
              title="Powered by Gemini LLM"
              className="shrink-0 transition hover:scale-105"
            >
              <img
                src={GeminiLLMIcon}
                alt="Gemini LLM"
                className="h-[37px] w-auto object-contain drop-shadow-[0_0_8px_rgba(140,255,77,0.4)]"
              />
            </a>
            
          </div>

          <div className="flex-1" />

          {/* Open source & Gemini Credits */}
          <TechCredits />

          <div className="flex-1" />

          <StatusPill label={`${VISION_MODEL_LABEL} MODEL`} online={modelOnline} icon="AI" />
          <StatusPill label={`${SPIKE_MODEL_LABEL} MODEL`} online={spikeModelOnline} icon="AI" />
          <StatusPill label="CLIMATE SERVICE" online={serviceOnline} icon="☁" />

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
          <div className="flex-1 min-w-0 flex items-center gap-2">
            <div className="min-w-0 flex-1">
              <h1 className="font-display neon-text-green tracking-widest leading-none truncate
                             text-base sm:text-lg">
                {APP_BRAND}
              </h1>
              <p className="hidden xs:block font-hud text-xs text-rg-muted tracking-[0.18em] mt-0.5 truncate">
                AI RICE DISEASE DETECTION
              </p>
            </div>
            <a
              href="https://aistudio.google.com/"
              target="_blank"
              rel="noopener noreferrer"
              title="Google AI Studio"
              className="shrink-0 transition hover:scale-105"
            >
              <img
                src={GoogleIcon}
                alt="Google AI Studio"
                className="h-[26px] w-auto object-contain drop-shadow-[0_0_6px_rgba(140,255,77,0.4)]"
              />
            </a>
            <a
              target="_blank"
              rel="noopener noreferrer"
              title="Powered by Gemini 3.5 Flash  " 
              className="shrink-0 transition hover:scale-105"
            >
              <img
                src={GeminiLLMIcon}
                alt="Gemini LLM"
                className="h-[29px] w-auto object-contain drop-shadow-[0_0_6px_rgba(140,255,77,0.4)]"
              />
            </a>

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

          {/* Powered by Gemini strip on mobile */}
          <div className="w-full border-t border-rg-border/30 pt-1 mt-0.5 flex justify-center">
            <PoweredByGemini compact />
          </div>
        </div>
      </div>

    </header>
  );
}

function Logo({ small = false }: { small?: boolean }) {
  const size = small ? 49 : 69;
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
      <div className={`${compact ? 'w-[29px] h-[29px] text-sm' : 'w-[37px] h-[37px] text-sm'} rounded-md border border-rg-border flex items-center justify-center font-display neon-text-green`}>{icon}</div>
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

/**
 * The credit strip: thank to  these projects, and the LLM behind the agent.
 */
function TechCredits() {
  return (
    <span className="flex items-center gap-10">
      <CreditRail credits={BACKEND_CREDITS} />
      <PoweredByGemini />
      <CreditRail credits={FRONTEND_CREDITS} />
    </span>
  );
}

function CreditRail({ credits }: { credits: Credit[] }) {
  return (
    <span className="hidden xl:flex items-center gap-8">
      {credits.map(({ src, label, link }) => (
        <a
          key={label}
          href={link}
          target="_blank"
          // noopener is the security half (the opened tab cannot reach back through
          // window.opener); noreferrer keeps it working in older browsers too.
          rel="noopener noreferrer"
          title={label}
          aria-label={label}
          className="opacity-55 transition hover:opacity-100 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D6D6D6]"
        >
          <img
            src={src}
            alt={label}
            className="h-[33px] w-[33px] shrink-0 object-contain"
            draggable={false}
          />
        </a>
      ))}
    </span>
  );
}

function PoweredByGemini ({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5 whitespace-nowrap">
      <a
        href="https://ai.google.dev/"
        target="_blank"
        rel="noopener noreferrer"
        title="Google Gemini — model documentation"
        aria-label="Google Gemini — model documentation"
        className="shrink-0 transition hover:opacity-80 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D6D6D6]"
      >
        <img
          src={GeminiIcon}
          alt="Google Gemini"
          className={`shrink-0 object-contain ${compact ? "h-[33px] w-[33px]" : "h-[37px] w-[37px]"}`}
          draggable={false}
        />
      </a>
      <span
        className={`mono font-semibold tracking-[0.16em] text-[#9A9A9A] ${
          compact ? "text-[12px]" : "text-[14px]"
        }`}
      >
        POWERED BY{" "}
        <span className="text-[#F0F0F0]">{compact ? "GEMINI" : "GEMINI - 3.5"}</span>
      </span>
    </span>
  );
}