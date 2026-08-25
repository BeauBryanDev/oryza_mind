import ReactMarkdown from 'react-markdown';


export default function MarkdownMessage({ content }: { content: string }) {

  return (

    <div className="text-base leading-[1.55] font-body space-y-2">
      <ReactMarkdown
        components={{
          
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          strong: ({ children }) => (
            <strong className="neon-text-green font-semibold">{children}</strong>
          ),
          em: ({ children }) => <em className="italic text-rg-muted">{children}</em>,
          ul: ({ children }) => <ul className="list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          h1: ({ children }) => (
            <h3 className="font-display neon-text-green tracking-widest text-sm mt-2">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="font-display neon-text-green tracking-widest text-sm mt-2">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="font-hud tracking-[0.2em] text-sm text-rg-muted mt-2">{children}</h4>
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer" className="neon-text underline">
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="px-1 py-0.5 rounded bg-black/40 border border-rg-neon/25 text-base">
              {children}
            </code>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-rg-neon/50 pl-3 text-rg-muted">
              {children}
            </blockquote>
          ),
          // Dosage tables are wide. Let them scroll rather than squeeze the
          // column and wrap a rate onto two lines.
          table: ({ children }) => (
            <div className="overflow-x-auto rg-scroll my-2">
              <table className="w-full text-sm border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-rg-panel2/60">{children}</thead>,
          th: ({ children }) => (
            <th className="border border-rg-neon/25 px-2 py-1 text-left font-hud tracking-[0.1em] text-sm text-rg-muted whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-rg-neon/20 px-2 py-1 align-top">{children}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
