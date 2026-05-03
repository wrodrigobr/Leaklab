import { HudHeader } from "./HudHeader";

export function HudLayout({
  children,
  eyebrow,
  title,
  description,
}: {
  children: React.ReactNode;
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />
      <main className="mx-auto max-w-[1440px] space-y-8 px-4 pt-8 pb-28 md:px-8 md:pb-8 animate-fade-in">
        <header className="flex flex-col gap-3">
          {eyebrow && (
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
              <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
              {eyebrow}
            </div>
          )}
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">{title}</h1>
          {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
        </header>
        {children}
      </main>
    </div>
  );
}
