import { Fragment } from "react";
import { cn } from "@/lib/utils";

interface Props {
  children: string;
  /** "sm" (default) for reports/analysis; "xs" for compact card narratives */
  size?: "sm" | "xs";
  className?: string;
}

// ── Inline parser — handles **bold**, *italic*, `code` ──────────────────────

function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1])      parts.push(<strong key={key++} className="font-semibold text-foreground">{m[1]}</strong>);
    else if (m[2]) parts.push(<em     key={key++} className="italic text-muted-foreground">{m[2]}</em>);
    else if (m[3]) parts.push(<code   key={key++} className="rounded bg-hud-elevated px-1 py-0.5 font-mono text-[0.9em] text-primary">{m[3]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

// ── Block renderer ───────────────────────────────────────────────────────────

type Block =
  | { type: "h2"; text: string }
  | { type: "h3"; text: string }
  | { type: "hr" }
  | { type: "ul"; items: string[] }
  | { type: "p"; text: string };

function parse(raw: string): Block[] {
  const blocks: Block[] = [];
  // Split into logical sections by blank lines; also treat --- as its own section
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  let listBuf: string[] = [];

  const flushList = () => {
    if (listBuf.length) { blocks.push({ type: "ul", items: [...listBuf] }); listBuf = []; }
  };

  let paraBuf = "";
  const flushPara = () => {
    const t = paraBuf.trim();
    if (t) { blocks.push({ type: "p", text: t }); }
    paraBuf = "";
  };

  for (const line of lines) {
    const h2 = line.match(/^#{1,2} (.+)/);
    const h3 = line.match(/^#{3} (.+)/);
    const li = line.match(/^[-*] (.+)/);
    const hr = /^---+$/.test(line.trim());

    if (h2) {
      flushList(); flushPara();
      blocks.push({ type: "h2", text: h2[1] });
    } else if (h3) {
      flushList(); flushPara();
      blocks.push({ type: "h3", text: h3[1] });
    } else if (hr) {
      flushList(); flushPara();
      blocks.push({ type: "hr" });
    } else if (li) {
      flushPara();
      listBuf.push(li[1]);
    } else if (line.trim() === "") {
      flushList(); flushPara();
    } else {
      if (listBuf.length) flushList();
      paraBuf += (paraBuf ? " " : "") + line;
    }
  }
  flushList();
  flushPara();
  return blocks;
}

// ── Component ────────────────────────────────────────────────────────────────

export function AiText({ children, size = "sm", className }: Props) {
  if (!children) return null;

  const base  = size === "xs" ? "text-[11px]" : "text-sm";
  const blocks = parse(children);

  return (
    <div className={cn("space-y-2", base, className)}>
      {blocks.map((block, i) => {
        switch (block.type) {
          case "h2":
            return (
              <h2 key={i} className="mt-4 border-b border-border pb-1 font-mono text-xs font-bold uppercase tracking-widest text-foreground first:mt-0">
                {parseInline(block.text)}
              </h2>
            );
          case "h3":
            return (
              <h3 key={i} className="mt-3 font-mono text-[10px] font-bold uppercase tracking-widest text-primary first:mt-0">
                {parseInline(block.text)}
              </h3>
            );
          case "hr":
            return <hr key={i} className="border-border/40" />;
          case "ul":
            return (
              <ul key={i} className="space-y-0.5 pl-0">
                {block.items.map((item, j) => (
                  <li key={j} className="flex items-start gap-2 text-muted-foreground">
                    <span className="mt-[6px] size-1.5 shrink-0 rounded-full bg-primary/50" aria-hidden />
                    <span className="leading-relaxed">{parseInline(item)}</span>
                  </li>
                ))}
              </ul>
            );
          case "p":
            return (
              <p key={i} className="leading-relaxed text-foreground">
                {parseInline(block.text)}
              </p>
            );
        }
      })}
    </div>
  );
}
