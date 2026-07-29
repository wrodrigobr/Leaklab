import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, RotateCw, Sparkles, Target } from "lucide-react";
import { proximoPasso, type ProximoPasso } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * A faixa do PRÓXIMO PASSO no dashboard (spec cobranca-proximo-passo.md §4).
 *
 * Diagnóstico sem próxima ação é extrato bancário: informa e desmoraliza. Esta faixa lidera o
 * dashboard com a prescrição — o quê, o porquê em bb e o custo em minutos — vinda do MESMO
 * endpoint que o sino e a resposta do upload consomem. Ela nunca decide nada: renderiza o que
 * o servidor decidiu, porque superfície que recalcula precedência diverge (lição do veredito).
 *
 * É uma FAIXA DE AÇÃO, irmã do alerta de drift, e não um card do masonry: nenhum card existente
 * muda de posição (o replanejamento exigido pela regra do dashboard está nisto — a grade fica
 * intocada e a ação ganha a primeira dobra).
 *
 * `titulo` e `porque` chegam prontos do servidor (PT, como as missões e a camada didática);
 * os rótulos estáticos são i18n normal.
 */
const ICONE: Record<ProximoPasso["tipo"], typeof Target> = {
  leak_reaberto:  RotateCw,
  revisao_vencida: AlertTriangle,
  missao:          Target,
  carta_nova:      Sparkles,
  desafio_diario:  Sparkles,
};

export function ProximoPassoBanner() {
  const { t } = useTranslation("dashboard");
  const { data } = useQuery({
    queryKey: ["proximo-passo", "dashboard"],
    queryFn: () => proximoPasso.get("dashboard"),
    staleTime: 60_000,
  });

  if (!data) return null;               // carregando: sem skeleton — a faixa entra quando sabe
  const passo = data.passo;

  if (!passo) {
    // Em dia É um estado, não uma ausência: sem isto o aluno que fez tudo abre o dashboard e
    // não recebe nenhum reconhecimento — e a faixa só aparecer para cobrar ensina a temê-la.
    return (
      <div className="flex items-center gap-2.5 rounded-xl ring-1 ring-emerald-500/25 bg-emerald-500/[0.04] px-4 py-3">
        <CheckCircle2 className="size-4 shrink-0 text-emerald-400" aria-hidden />
        <p className="text-sm text-muted-foreground">{t("proximoPasso.emDia")}</p>
      </div>
    );
  }

  const Icone = ICONE[passo.tipo] ?? Target;
  const urgente = passo.tipo === "leak_reaberto";

  return (
    <Link to={passo.cta_url}
      className={cn(
        "group flex items-center gap-3 rounded-xl px-4 py-3.5 ring-1 transition-colors",
        urgente
          ? "ring-amber-500/40 bg-amber-500/[0.07] hover:ring-amber-500/70"
          : "ring-primary/25 bg-primary/[0.04] hover:ring-primary/50",
      )}>
      <Icone className={cn("size-5 shrink-0", urgente ? "text-amber-400" : "text-primary")} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className={cn("font-mono text-[10px] font-bold uppercase tracking-widest",
          urgente ? "text-amber-400" : "text-primary")}>
          {t(`proximoPasso.eyebrow.${passo.tipo}`)}
        </p>
        <p className="mt-0.5 truncate text-sm font-medium text-foreground">{passo.titulo}</p>
        <p className="mt-0.5 line-clamp-2 text-xs leading-snug text-muted-foreground">{passo.porque}</p>
      </div>
      <span className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider",
        urgente ? "bg-amber-500 text-black group-hover:bg-amber-400"
                : "bg-primary/15 text-primary ring-1 ring-primary/40 group-hover:bg-primary/25",
      )}>
        {t("proximoPasso.cta", { min: passo.custo_min })}
        <ArrowRight className="size-3.5" aria-hidden />
      </span>
    </Link>
  );
}
