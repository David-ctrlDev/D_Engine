"use client";

/**
 * Markdown renderer for chat messages.
 *
 * The LLMs we talk to (Claude / GPT / Gemini) reach for markdown by
 * default — **bold**, bullet lists, numbered steps, fenced code. We
 * tried fighting that in the system prompt and it's a losing battle;
 * easier to just render it properly.
 *
 * What we render
 * --------------
 *
 * * GFM enabled (tables, strikethrough, autolinks) — but no raw HTML.
 *   react-markdown skips HTML by default which is exactly what we want.
 * * Tailwind classes per element so the styling matches the bubble it
 *   sits in (we render the same component in both ``user`` and
 *   ``assistant`` bubbles, which have different backgrounds).
 *
 * What we deliberately omit
 * -------------------------
 *
 * * No KaTeX / math: agent doesn't emit it for now.
 * * No syntax highlighting yet: code blocks render plain. We'll add
 *   highlight.js / shiki when the agent starts pasting SQL / Python.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

export function MessageMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      // No raw HTML — the model occasionally tries to emit `<br>` etc.,
      // which we'd rather not pipe through to the DOM. react-markdown
      // strips it by default; we keep that behaviour explicit.
      components={{
        // ----- Text + blocks --------------------------------------------
        p: ({ children }) => <p className="leading-relaxed">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        del: ({ children }) => <del className="line-through opacity-70">{children}</del>,
        // ----- Lists ----------------------------------------------------
        ul: ({ children }) => (
          <ul className="list-disc space-y-1 pl-5 [&>li>p]:m-0">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal space-y-1 pl-5 [&>li>p]:m-0">{children}</ol>
        ),
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        // ----- Headings (rare in chat, but the model uses them) ---------
        h1: ({ children }) => <h3 className="text-base font-semibold">{children}</h3>,
        h2: ({ children }) => <h3 className="text-base font-semibold">{children}</h3>,
        h3: ({ children }) => <h3 className="text-sm font-semibold">{children}</h3>,
        h4: ({ children }) => <h4 className="text-sm font-semibold">{children}</h4>,
        // ----- Code / quotes / links -----------------------------------
        code: ({ className, children }) => {
          const isBlock = (className ?? "").startsWith("language-");
          if (isBlock) {
            return (
              <pre className="bg-foreground/10 my-1 overflow-x-auto rounded-md p-2 text-xs">
                <code className="font-mono">{children}</code>
              </pre>
            );
          }
          return (
            <code className="bg-foreground/10 rounded px-1 py-0.5 font-mono text-xs">
              {children}
            </code>
          );
        },
        pre: ({ children }) => <>{children}</>,
        blockquote: ({ children }) => (
          <blockquote className="border-foreground/20 my-1 border-l-2 pl-3 italic opacity-90">
            {children}
          </blockquote>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:opacity-80"
          >
            {children}
          </a>
        ),
        // ----- Tables (GFM) --------------------------------------------
        table: ({ children }) => (
          <div className="my-1 overflow-x-auto">
            <table className="min-w-full text-xs">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border-foreground/20 border-b px-2 py-1 text-left font-medium">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border-foreground/10 border-b px-2 py-1">{children}</td>
        ),
        hr: () => <hr className={cn("border-foreground/15 my-2")} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
