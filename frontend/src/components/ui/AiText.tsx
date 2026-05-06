import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface Props {
  children: string;
  /** "sm" (default) for reports/analysis; "xs" for compact card narratives */
  size?: "sm" | "xs";
  className?: string;
}

/**
 * Renders AI-generated Markdown text using the system's typography.
 * Handles ##/### headings, **bold**, lists, inline code, and --- dividers.
 */
export function AiText({ children, size = "sm", className }: Props) {
  const base = size === "xs" ? "text-[11px]" : "text-sm";

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className={cn("space-y-2", base, className)}
      components={{
        p: ({ children }) => (
          <p className="leading-relaxed text-foreground">{children}</p>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-foreground">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-muted-foreground">{children}</em>
        ),
        h2: ({ children }) => (
          <h2 className="mt-4 mb-1 border-b border-border pb-1 font-mono text-xs font-bold uppercase tracking-widest text-foreground first:mt-0">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="mt-3 mb-0.5 font-mono text-[10px] font-bold uppercase tracking-widest text-primary first:mt-0">
            {children}
          </h3>
        ),
        ul: ({ children }) => (
          <ul className="my-1 list-disc space-y-0.5 pl-4 marker:text-primary/50">
            {children}
          </ul>
        ),
        ol: ({ children }) => (
          <ol className="my-1 list-decimal space-y-0.5 pl-4 marker:text-muted-foreground">
            {children}
          </ol>
        ),
        li: ({ children }) => (
          <li className="pl-0.5 leading-relaxed text-muted-foreground">
            {children}
          </li>
        ),
        code: ({ children }) => (
          <code className="rounded bg-hud-elevated px-1 py-0.5 font-mono text-[0.9em] text-primary">
            {children}
          </code>
        ),
        hr: () => <hr className="my-3 border-border/40" />,
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-primary/40 pl-3 italic text-muted-foreground">
            {children}
          </blockquote>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
