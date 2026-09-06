import { useState, useRef, useEffect } from 'react';
import { useChat } from '../hooks/useChat';

export default function PromptBox() {
  const [text, setText] = useState('');
  const { send, isSending } = useChat();
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }, [text]);

  const submit = () => {

    if (!text.trim() || isSending) return;
    send(text);
    setText('');
  };

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); submit(); }}
      className="hud-panel px-3 py-2 flex items-end gap-2 focus-within:hud-panel-strong transition"
    >
      <button type="button" aria-label="Attach" className="p-2 text-rg-neon/70 hover:text-rg-neon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.5l-8.5 8.5a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8"/></svg>
      </button>
      <textarea
        ref={taRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
        }}
        rows={1}
        disabled={isSending}
        placeholder="Describe your crop or ask about a disease, treatment or prevention..."
        aria-label="Write a message"
        className="flex-1 bg-transparent resize-none outline-none text-base text-rg-text placeholder:text-rg-muted/70 py-2 max-h-40 rg-scroll"
      />
      <button
        type="submit"
        disabled={!text.trim() || isSending}
        aria-label="Send message"
        className="w-10 h-10 rounded-md bg-rg-accent text-black flex items-center justify-center
          shadow-[0_0_16px_rgba(199,240,0,0.55)] hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2 21L23 12 2 3v7l15 2-15 2z"/></svg>
      </button>
    </form>
  );
}
