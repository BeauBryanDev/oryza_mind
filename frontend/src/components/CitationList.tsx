import type { Citation } from '../types';

// Provenance is the point of the RAG layer: an answer that cites a page can be
// checked, one that cannot should not be trusted.
export default function CitationList({ citations }: { citations: Citation[] }) {
  
  if (!citations.length) return null;

  // Several chunks usually come from the same document and page.
  const seen = new Set<string>();
  const unique = citations.filter((c) => {
    const key = `${c.documentTitle}|${c.pageStart ?? ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return (
    <details className="mt-2 group">
      <summary className="cursor-pointer list-none font-hud text-xs tracking-[0.2em] text-rg-muted hover:text-rg-neon transition">
        {unique.length} SOURCE{unique.length === 1 ? '' : 'S'} ▾
      </summary>
      <ul className="mt-1.5 space-y-1">
        {unique.map((c) => (
          <li key={c.chunkId} className="text-sm text-rg-muted leading-snug flex gap-1.5">
            <span className="text-rg-neon/60 shrink-0">▸</span>
            <span>
              {c.sourceUrl ? (
                <a href={c.sourceUrl} target="_blank" rel="noreferrer" className="hover:text-rg-neon underline">
                  {c.documentTitle}
                </a>
              ) : (
                c.documentTitle
              )}
              {c.pageStart !== null && <span className="text-rg-muted/70">, p. {c.pageStart}</span>}
              {c.organization && <span className="text-rg-muted/60"> · {c.organization}</span>}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
