import { BookOpen, ExternalLink, Film, Globe, Wrench } from "lucide-react";
import type { StudyResource } from "./types";

const ICONS = {
  book:  BookOpen,
  video: Film,
  site:  Globe,
  tool:  Wrench,
} as const;

const LABELS = {
  book:  "Livro",
  video: "Vídeo",
  site:  "Site",
  tool:  "Ferramenta",
} as const;

export function ResourceList({ resources }: { resources: StudyResource[] }) {
  if (!resources?.length) {
    return (
      <p className="font-mono text-[11px] text-muted-foreground">
        Nenhum recurso atribuído ainda.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {resources.map((r, i) => {
        const Icon = ICONS[r.type];
        const Wrap = r.url ? "a" : "div";
        const wrapProps = r.url
          ? { href: r.url, target: "_blank", rel: "noreferrer" }
          : {};
        return (
          <li key={`${r.title}-${i}`}>
            <Wrap
              {...(wrapProps as Record<string, string>)}
              className="group flex items-start gap-3 rounded-md border border-border bg-background p-3 transition-colors hover:border-primary/40"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-sm bg-primary/10 text-primary">
                <Icon className="size-3.5" aria-hidden />
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-foreground">{r.title}</p>
                  <span className="shrink-0 font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
                    {LABELS[r.type]}
                  </span>
                </div>
                {r.author && (
                  <p className="font-mono text-[10px] text-muted-foreground">{r.author}</p>
                )}
                {r.note && (
                  <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{r.note}</p>
                )}
              </div>
              {r.url && (
                <ExternalLink
                  className="size-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
                  aria-hidden
                />
              )}
            </Wrap>
          </li>
        );
      })}
    </ul>
  );
}
