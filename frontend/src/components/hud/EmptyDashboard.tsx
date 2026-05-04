import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { FileUp, ShieldCheck, Target, Sparkles, UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUploadQueue } from "@/components/hud/UploadQueue";

const SUPPORTED = [".txt", ".log"];

interface Props {
  onComplete?: () => void;
}

export function EmptyDashboard({ onComplete }: Props) {
  const { t } = useTranslation("dashboard");
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { enqueue, panel } = useUploadQueue(onComplete);

  const MODULES = [
    { code: t("empty.m1code"), title: t("empty.m1title"), description: t("empty.m1desc"), icon: Target },
    { code: t("empty.m2code"), title: t("empty.m2title"), description: t("empty.m2desc"), icon: ShieldCheck },
    { code: t("empty.m3code"), title: t("empty.m3title"), description: t("empty.m3desc"), icon: Sparkles },
  ];

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files.length) enqueue(e.dataTransfer.files);
  };

  const handleFiles = (selected: FileList | null) => {
    if (selected?.length) enqueue(selected);
  };

  return (
    <>
    {panel}
    <div className="space-y-16">
      <section className="relative">
        <div className="absolute -top-7 left-0 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          {t("empty.phase")}
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={cn(
            "bg-hud-surface border border-border p-1 transition-colors rounded-xl",
            isDragging && "border-primary"
          )}
        >
          <div
            className={cn(
              "border border-dashed border-border rounded-lg py-20 px-6 text-center transition-colors",
              isDragging && "border-primary/40 bg-primary/5",
            )}
          >
            <div className="mb-8 flex justify-center">
              <div className="size-16 rounded-full border border-border flex items-center justify-center bg-background">
                <div className="size-8 bg-primary/10 rounded-sm flex items-center justify-center">
                  <UploadCloud className="size-4 text-primary" aria-hidden />
                </div>
              </div>
            </div>

            <h1 className="text-3xl md:text-4xl font-medium tracking-tight text-foreground mb-3">
              {t("empty.title")}
            </h1>
            <p className="text-muted-foreground max-w-md mx-auto mb-10 text-sm leading-relaxed">
              {t("empty.desc")}
            </p>

            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-8 py-4 font-mono text-xs font-bold uppercase tracking-widest-2 transition-colors hover:bg-primary-glow rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <FileUp className="size-3.5" aria-hidden />
              {t("empty.import")}
            </button>

            <input
              ref={inputRef}
              type="file"
              accept=".txt,.log"
              multiple
              className="sr-only"
              onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }}
              aria-label={t("empty.fileLabel")}
            />

            <div className="mt-8 flex flex-wrap justify-center items-center gap-3 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
              {SUPPORTED.map((ext, i) => (
                <span key={ext} className="flex items-center gap-3">
                  {i > 0 && <span className="h-3 w-px bg-border" aria-hidden />}
                  {ext}
                </span>
              ))}
              <span className="h-3 w-px bg-border" aria-hidden />
              <span>PokerStars</span>
              <span className="h-3 w-px bg-border" aria-hidden />
              <span>AES-256</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-6 flex items-baseline justify-between">
          <h2 className="text-sm font-bold uppercase tracking-widest-2 text-foreground">
            {t("empty.unlocks")}
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("empty.modules")}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {MODULES.map((m) => {
            const Icon = m.icon;
            return (
              <article
                key={m.code}
                className="tactical-corners relative bg-hud-surface border border-border p-6 transition-transform hover:-translate-y-1 rounded-lg"
              >
                <div className="flex items-center justify-between mb-6">
                  <span className="font-mono text-[10px] tracking-widest-2 text-primary uppercase">
                    {m.code}
                  </span>
                  <Icon className="size-4 text-primary/60" aria-hidden />
                </div>
                <h3 className="text-lg font-medium text-foreground mb-2">{m.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed mb-6">{m.description}</p>
                <div className="flex items-center gap-3">
                  <div className="h-1 flex-1 bg-border overflow-hidden rounded-full">
                    <div className="h-full w-0 bg-primary" />
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground">0%</span>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
    </>
  );
}
