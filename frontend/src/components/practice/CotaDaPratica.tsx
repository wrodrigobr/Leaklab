import { Infinity as InfinityIcon, Lock } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { CotaDaPratica } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * A cota do Prática na tela.
 *
 * ── O pedido (18/09) ──────────────────────────────────────────────────────────────────────────
 *
 * O dono: "o modo pratica pode ser liberado para plano free, mas eu quero que eles tenham uma
 * limitacao de apenas 2 mesas simultaneas e no maximo 30 spots por mes... **e isto precisa ficar
 * explicito pra eles na tela**".
 *
 * A última frase é a que manda no desenho deste arquivo. Teto que o jogador só descobre ao bater
 * nele é indistinguível de defeito: ele conclui que o produto travou, não que a cota acabou. Por
 * isso o contador fica na BARRA DO TOPO, que é o único lugar visível o tempo todo (o painel fecha,
 * e no celular ele é uma gaveta sobre as mesas).
 *
 * ── Por que os números vêm do servidor, e não daqui ──────────────────────────────────────────
 *
 * A tela tem o placar da sessão (`stats.maos`) e seria fácil derivar o consumo dele. Mas a cota é
 * do MÊS e atravessa sessão e aparelho: quem abre o Prática de manhã no celular e de noite no
 * desktop tem um consumo só. Derivar na tela criaria dois números, e o que barra é o do servidor.
 */

function formataData(iso: string, locale: string): string {
  try {
    // `T00:00:00` explícito: sem ele o navegador interpreta a data pura como UTC e, em fuso
    // negativo (o nosso), "2026-10-01" vira 30/09 na tela. A promessa erraria por um dia.
    return new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "2-digit", month: "short" });
  } catch {
    return iso;
  }
}

/** O contador da barra do topo. Some em plano sem teto, onde ele não informaria nada. */
export function ContadorDaCota({ cota }: { cota: CotaDaPratica | null }) {
  const { t, i18n } = useTranslation("practice");
  if (!cota || cota.spots_limite == null) return null;

  const usados = Math.min(cota.spots_usados, cota.spots_limite);
  const pct = Math.round((usados / cota.spots_limite) * 100);
  // Três faixas, e o vermelho não é decoração: ele aparece quando resta pouco, que é quando o
  // jogador ainda tem tempo de decidir o que fazer com o que sobrou.
  const tom = cota.esgotado ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-primary";

  return (
    <span data-testid="pratica-cota" className="flex shrink-0 items-center gap-1.5"
          title={t("cota.tooltip", { usados: cota.spots_usados, limite: cota.spots_limite,
                                     mesas: cota.mesas, data: formataData(cota.renova_em, i18n.language) })}>
      <span className="font-mono text-[10.5px] tabular-nums tracking-widest text-muted-foreground">
        {t("cota.spots", { usados: cota.spots_usados, limite: cota.spots_limite })}
      </span>
      {/* A barra é curta de propósito: na barra do topo ela divide espaço com o placar da sessão,
          e no celular os rótulos somados já estouraram 390px uma vez. */}
      <span aria-hidden className="hidden h-1 w-14 overflow-hidden rounded-full bg-border sm:block">
        <span className={cn("block h-full rounded-full transition-all", tom)}
              style={{ width: `${Math.max(2, pct)}%` }} />
      </span>
    </span>
  );
}

/**
 * O fim do mês, quando a cota acaba.
 *
 * Fecha com o relatório e não com uma parede. Não é preferência estética: é o princípio que o Free
 * já segue no treino avulso, escrito no `PLAN_LIMITS` em 28/08 ("eles fecham a sessão com um
 * boletim, não com uma parede"). O que decide se o limite engaja ou irrita é a embalagem.
 */
export function CotaEsgotada({ cota, onRelatorio, compacto = false }: {
  cota: CotaDaPratica;
  onRelatorio: () => void;
  /**
   * Com mesas ainda na tela, o aviso é uma FAIXA e não um bloco de tela cheia.
   *
   * A primeira versão tomava a tela sempre que a cota zerava, e com isso o jogador que respondia
   * a 30ª mão PERDIA o veredito dela: o aviso entrava e apagava as mesas que ele estava lendo. O
   * limite não causava esse dano; o meu aviso causava.
   */
  compacto?: boolean;
}) {
  const { t, i18n } = useTranslation("practice");

  if (compacto) {
    return (
      <div data-testid="pratica-cota-faixa"
           className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5">
        <span className="font-mono text-[10px] leading-relaxed text-amber-200/90">
          {t("cota.esgotada.titulo", { limite: cota.spots_limite })}
          {" · "}
          {t("cota.esgotada.volta", { data: formataData(cota.renova_em, i18n.language) })}
        </span>
        <Link to="/subscription" data-testid="pratica-cota-pro-faixa"
              className="ml-auto inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest-2 text-primary hover:underline">
          <InfinityIcon className="size-3" />
          {t("cota.esgotada.pro")}
        </Link>
      </div>
    );
  }

  return (
    <div data-testid="pratica-cota-esgotada"
         className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <Lock className="size-5 text-amber-400/80" />
      <p className="font-mono text-sm text-foreground">
        {t("cota.esgotada.titulo", { limite: cota.spots_limite })}
      </p>
      <p className="max-w-[48ch] text-xs leading-relaxed text-muted-foreground">
        {t("cota.esgotada.corpo", { data: formataData(cota.renova_em, i18n.language) })}
      </p>
      <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
        <button type="button" onClick={onRelatorio} data-testid="pratica-cota-relatorio"
                className="rounded border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary">
          {t("cota.esgotada.relatorio")}
        </button>
        <Link to="/subscription" data-testid="pratica-cota-pro"
              className="inline-flex items-center gap-1.5 rounded border border-primary/40 bg-primary/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-primary transition-colors hover:bg-primary/20">
          <InfinityIcon className="size-3" />
          {t("cota.esgotada.pro")}
        </Link>
      </div>
    </div>
  );
}
