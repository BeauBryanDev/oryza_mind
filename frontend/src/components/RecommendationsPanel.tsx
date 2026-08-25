// The most valuable output in the app: retrieved, cited management advice.
// It was rendered at HUD-label size, which made the one section a farmer
// actually reads the hardest to read. Sized as body copy now, not as chrome.
// title is overridable so the leaf and spike blocks stay distinguishable when
// both are on screen at once. I might need to refactor this to be a component
// with a slot for the title. todo task for v2 maybe.
export default function RecommendationsPanel({
  items,  // it is a list of strings, not a list of objects
  title = 'MANAGEMENT RECOMMENDATIONS',  //it is coming English by default from backend
}: {  // it might need to change it to SP or whatever Language user writes to  the chatbot 
  items: string[];
  title?: string;
}) {
  if (!items.length) return null;

  return (

    <div className="hud-panel hud-panel-strong p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-8 h-8 rounded-md border border-rg-accent/60 bg-rg-accent/10 flex items-center justify-center shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#C7F000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18h6" /><path d="M10 22h4" />
            <path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z" />
          </svg>
        </span>
        <h3 className="font-display neon-text tracking-widest text-base">
          {title}
        </h3>
      </div>

      <ol className="space-y-3">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3">
            <span className="font-display text-sm neon-text-green tabular-nums shrink-0 w-7 h-7 rounded-md border border-rg-neon/40 bg-rg-neon/5 flex items-center justify-center">
              {i + 1}
            </span>
            <span className="text-rg-text font-body text-base leading-[1.55] pt-0.5">
              {item}
            </span>
          </li>
        ))}
      </ol>

      <p className="mt-4 pt-3 border-t border-rg-neon/20 text-xs font-hud tracking-[0.1em] text-rg-muted leading-relaxed">
        RETRIEVED FROM AGRONOMIC REFERENCES. VERIFY RATES ON THE PRODUCT LABEL.
      </p>
    </div>
  );
}
