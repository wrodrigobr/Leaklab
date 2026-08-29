import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Heart, MessageSquare, Play } from "lucide-react";

import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { sharedHandFeed, type FeedItem } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * O feed da comunidade: as mãos compartilhadas, num lugar só.
 *
 * ── O desenho (30/08, benchmark do dono) ──────────────────────────────────────────────────
 *
 * Do benchmark: cards com autor, pergunta, cartas, placar e ordenações (recentes / mais
 * comentadas / mais votadas / sem resposta). As duas diferenças DELIBERADAS:
 *
 * 1. O card NÃO mostra o veredito nem o resultado da mão — a página do link pede o voto
 *    ANTES de revelar, e um feed que entrega a resposta mataria o mecanismo.
 * 2. O autor é o username GrindLab de quem ESCOLHEU compartilhar; nicks de POKER (as pessoas
 *    da mesa que não consentiram) continuam invisíveis em toda a superfície.
 */

const SORTS = ["recentes", "comentadas", "votadas", "sem_resposta"] as const;
const POSICOES = ["", "UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"] as const;

function parseCartas(raw?: string | null): CardData[] {
  if (!raw) return [];
  const s = String(raw).replace(/[[\]"',\s]/g, "");
  const out: CardData[] = [];
  for (let i = 0; i + 1 < s.length; i += 2) {
    out.push({ rank: s[i] as CardData["rank"], suit: s[i + 1].toLowerCase() as CardData["suit"] });
  }
  return out;
}

function CardDoFeed({ item }: { item: FeedItem }) {
  const { t } = useTranslation("common");
  const cartas = parseCartas(item.previa.hero_cards);
  const board = parseCartas(
    Array.isArray(item.previa.board) ? item.previa.board.join("") : item.previa.board,
  );
  const quando = item.created_at
    ? new Date(item.created_at).toLocaleDateString(undefined, { day: "2-digit", month: "2-digit" })
    : "";
  return (
    <Link
      to={`/h/${item.token}`}
      className="flex flex-col gap-2.5 rounded-xl border border-border bg-hud-surface p-4 transition-colors hover:border-primary/40"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className={cn("truncate font-mono text-[12px] font-bold",
                            item.autor ? "text-primary" : "text-muted-foreground")}>
          {item.autor ?? t("sharedFeed.anonimo")}
        </span>
        <span className="shrink-0 font-mono text-[10px] text-muted-foreground/70">{quando}</span>
      </div>

      <p className="text-[14px] font-medium leading-snug text-foreground">
        {item.pergunta || t("sharedFeed.compartilhou")}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {item.previa.position && (
          <span className="rounded bg-amber-400/10 px-1.5 py-0.5 font-mono text-[9.5px] font-bold uppercase text-amber-400">
            {item.previa.position}
          </span>
        )}
        <span className="flex gap-0.5">
          {cartas.map((c, i) => <PlayingCard key={i} card={c} size="sm" />)}
        </span>
        {board.length > 0 && (
          <>
            <span className="text-muted-foreground/40">·</span>
            <span className="flex gap-0.5">
              {board.map((c, i) => <PlayingCard key={i} card={c} size="sm" />)}
            </span>
          </>
        )}
      </div>

      <div className="mt-0.5 flex items-center gap-4 font-mono text-[10.5px] tabular-nums text-muted-foreground">
        <span className="flex items-center gap-1"><Heart className="size-3" aria-hidden />{item.votos}</span>
        <span className="flex items-center gap-1"><MessageSquare className="size-3" aria-hidden />{item.comentarios}</span>
        {item.n_passos > 1 && <span>{t("sharedFeed.passos", { n: item.n_passos })}</span>}
        <span className="ml-auto flex items-center gap-1 text-primary">
          <Play className="size-3" aria-hidden />{t("sharedFeed.ver")}
        </span>
      </div>
    </Link>
  );
}

export default function FeedDeMaos() {
  const { t } = useTranslation("common");
  const [sort, setSort] = useState<(typeof SORTS)[number]>("recentes");
  const [posicao, setPosicao] = useState("");

  const { data, isPending } = useQuery({
    queryKey: ["shared-feed", sort, posicao],
    queryFn: () => sharedHandFeed(sort, posicao || undefined),
    staleTime: 60_000,
  });
  const feed = data?.feed ?? [];

  return (
    <HudLayout>
      <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 md:px-8">
        <h1 className="font-heading text-2xl font-bold text-foreground">{t("sharedFeed.titulo")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("sharedFeed.sub")}</p>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          {SORTS.map((sk) => (
            <button key={sk} type="button" onClick={() => setSort(sk)}
                    className={cn(
                      "rounded-full px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider transition-colors",
                      sort === sk
                        ? "bg-primary/10 text-primary ring-1 ring-primary/25"
                        : "text-muted-foreground hover:text-foreground",
                    )}>
              {t(`sharedFeed.sort.${sk}`)}
            </button>
          ))}
          <select
            value={posicao}
            onChange={(e) => setPosicao(e.target.value)}
            className="ml-auto rounded-lg border border-border bg-hud-surface px-2.5 py-1.5 font-mono text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {POSICOES.map((p) => (
              <option key={p} value={p}>{p || t("sharedFeed.posicao")}</option>
            ))}
          </select>
        </div>

        {isPending ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-40 animate-pulse rounded-xl bg-muted/20" />)}
          </div>
        ) : feed.length === 0 ? (
          <p className="mt-10 text-center text-sm text-muted-foreground">
            {sort === "recentes" && !posicao ? t("sharedFeed.vazio") : t("sharedFeed.vazioSort")}
          </p>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {feed.map((f) => <CardDoFeed key={f.token} item={f} />)}
          </div>
        )}
      </main>
    </HudLayout>
  );
}
