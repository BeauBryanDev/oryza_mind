import { useEffect, useRef } from 'react';
import { useChat } from '../hooks/useChat';
import { formatTime } from '../utils/formatters';
import PromptBox from './PromptBox';
import MarkdownMessage from './MarkdownMessage';
import CitationList from './CitationList';
import { useAnalysisStore } from '../stores/analysisStore';
import type { Citation } from '../types';
import { APP_BRAND, APP_NAME } from '../utils/constants';
import riceLeafIcon from '../assets/rice_leaf_icon.svg';
import oryzaChatIcon from '../assets/oryza_chat.svg';

export default function ChatPanel() {
 // this is for chat with oryza-mind type interface
  const { messages, isTyping } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);
  const stage = useAnalysisStore((s) => s.stage);
  const progress = useAnalysisStore((s) => s.progress);

  useEffect(() => {

    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isTyping]);

  const scanning = stage !== 'IDLE' && stage !== 'COMPLETED' && stage !== 'ERROR';
  // The upload fraction is real; inference reports no progress, so the bar goes
  // indeterminate rather than inventing a percentage.
  const indeterminate = stage === 'ANALYZING' || stage === 'GENERATING_DIAGNOSIS';

  return (

    <section aria-label="Chat with OryzaMind" className="hud-panel hud-corners p-5 flex flex-col h-full min-h-0 overflow-hidden">
      <span className="corner-tl" /><span className="corner-tr" /><span className="corner-bl" /><span className="corner-br" />

      <header className="flex items-center gap-2 mb-3">
        <span className="w-7 h-7 rounded-md border border-rg-border flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8CFF4D" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </span>
        <h2 className="font-display neon-text-green tracking-widest text-base"> CHAT WITH ORYZA-MIND</h2>
      </header>

      <div className="h-px bg-gradient-to-r from-transparent via-rg-neon/40 to-transparent mb-3" />

      <div ref={scrollRef} className="flex-1 overflow-y-auto rg-scroll pr-1 space-y-4 min-h-0">
        {messages.length === 0 && <EmptyChat />}

        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            content={m.content}
            timestamp={m.timestamp}
            attachments={m.attachments}
            citations={m.citations}
          />
        ))}

        {scanning && (
          <div className="hud-panel px-4 py-3 fade-in">
            <div className="flex items-center gap-3">
              <div className="relative w-9 h-9 rounded-full border border-rg-neon/60 flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-rg-neon shadow-[0_0_10px_#8CFF4D]" />
                <div className="absolute inset-0 rounded-full border border-rg-neon/30 animate-ping" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-hud text-xs tracking-[0.25em] neon-text-green">
                    {indeterminate ? 'ANALYZING IMAGES...' : 'UPLOADING IMAGES...'}
                  </span>
                  {!indeterminate && (
                    <span className="font-display text-xs neon-text tabular-nums">
                      {Math.round(progress)}%
                    </span>
                  )}
                </div>
                <div className="progress-track">
                  <div
                    className={`progress-fill ${indeterminate ? 'animate-pulse' : ''}`}
                    style={{ width: indeterminate ? '100%' : `${progress}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {isTyping && (
          <div className="hud-panel px-4 py-2 flex items-center gap-3 fade-in w-fit">
            <div className="w-6 h-6 rounded-full border border-rg-neon/50 flex items-center justify-center">
              <span className="text-sm neon-text-green">✱</span>
            </div>
            <span className="font-hud text-xs text-rg-muted tracking-[0.15em]">
              {APP_NAME} AI is typing
            </span>
            <span className="typing"><span/><span/><span/></span>
          </div>
        )}
      </div>

      <div className="mt-3">
        <PromptBox />
        <p className="text-center text-xs font-hud tracking-[0.15em] text-rg-muted mt-2">
          {APP_NAME} can make mistakes. Always verify in the field.
        </p>
      </div>
    </section>
  );
}

function EmptyChat() {

  return (
    <div className="h-full flex flex-col items-center justify-center text-center gap-2 py-8">
      <img src={riceLeafIcon} alt="" width={40} height={40} className="opacity-70" />
      <div className="font-display neon-text-green tracking-widest text-sm">
        {APP_BRAND} AI
      </div>
      <p className="text-xs text-rg-muted max-w-[280px] leading-relaxed">
        Upload rice leaf photos for a diagnosis, or ask about a disease, its
        treatment or prevention. Answers are drawn from agronomic references and
        cite their source.
      </p>
    </div>
  );
}

function MessageBubble({

  role,
  content,
  timestamp,
  attachments,
  citations,
}: {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  attachments?: string[];
  citations?: Citation[];
}) {

  const isUser = role === 'user';

  return (

    <div className={`flex gap-2 sm:gap-3 fade-in ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-full border flex items-center justify-center
        ${isUser ? 'border-rg-accent/60' : 'border-rg-neon/60 bg-rg-panel2'}`}>
        {isUser ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C7F000" strokeWidth="2"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>
        ) : (
          <img src={oryzaChatIcon} alt="AI" width={28} height={28} />
        )}
      </div>
      <div className={`max-w-[85%] min-w-0 rounded-xl px-3 py-2 border
        ${isUser
          ? 'bg-rg-panel border-rg-accent/40 text-rg-text'
          : 'bg-rg-panel2/80 border-rg-neon/40 text-rg-text'}`}>
        <div className="flex items-center gap-2 mb-1">
          <span className={`font-display text-xs tracking-widest ${isUser ? 'neon-text' : 'neon-text-green'}`}>
            {isUser ? 'You' : `${APP_NAME} AI`}
          </span>
          <span className="font-hud text-xs text-rg-muted tracking-[0.2em] tabular-nums">
            {formatTime(timestamp)}
          </span>
        </div>

        {attachments && attachments.length > 0 && (
          <div className="flex gap-2 mb-2">
            {attachments.map((a, i) => (
              <img key={i} src={a} alt={`attachment ${i + 1}`} className="w-10 h-10 rounded object-cover border border-rg-neon/40" />
            ))}
          </div>
        )}

        {isUser ? (
          <div className="text-sm leading-[1.55] whitespace-pre-wrap font-body">{content}</div>
        ) : (
          <MarkdownMessage content={content} />
        )}

        {!isUser && citations && <CitationList citations={citations} />}
      </div>
    </div>
  );
}
