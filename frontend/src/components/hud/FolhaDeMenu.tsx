import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Lock, X } from "lucide-react";

import { GRUPOS, type ItemDeMenu } from "./navGrupos";
import { cn } from "@/lib/utils";

/**
 * O menu inteiro no celular: uma folha que sobe, com todos os grupos e os mesmos cadeados.
 *
 * ── Por que existe, e o erro que ela conserta (28/08) ─────────────────────────────────────
 *
 * O menu com painel resolveu o desktop (47 rotas de jogador, 11 na barra) e eu **piorei o
 * celular**: a barra inferior passou a mostrar as quatro RAÍZES dos grupos, o que tirou o toque
 * direto de Torneios, sumiu com o AI Coach, e não deu nada em troca — os subitens só existiam no
 * painel do desktop.
 *
 * O dono perguntou se no celular não era melhor manter como estava. Medindo: a barra caiu de 6-7
 * botões para 4 e nenhum subitem ficou alcançável. Ele estava certo, e reverter também não
 * resolveria — o problema das 47 rotas existe igual no celular.
 *
 * A saída é barra + folha: a barra volta a ter os destinos de uso diário, e um botão abre ISTO,
 * com o produto inteiro. Folha é o que o dedo espera; o menu do benchmark é hover, e hover não
 * existe em tela sensível ao toque.
 */

interface Props {
  aberta: boolean;
  aoFechar: () => void;
  capacidades?: Record<string, boolean | number | null | undefined>;
  ocultar?: string[];
}

function liberado(item: ItemDeMenu, caps?: Props["capacidades"]): boolean {
  if (!item.exige) return true;
  if (!caps) return true;                 // sem resposta ainda: não acusa quem talvez tenha
  return caps[item.exige] !== false;
}

export function FolhaDeMenu({ aberta, aoFechar, capacidades, ocultar = [] }: Props) {
  const { t } = useTranslation("common");

  // Trava o scroll do fundo enquanto a folha está aberta: sem isto o dedo arrasta a página por
  // baixo e a folha parece quebrada.
  useEffect(() => {
    if (!aberta) return;
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") aoFechar(); };
    document.addEventListener("keydown", esc);
    return () => {
      document.body.style.overflow = antes;
      document.removeEventListener("keydown", esc);
    };
  }, [aberta, aoFechar]);

  if (!aberta) return null;

  return (
    <div className="fixed inset-0 z-[60] lg:hidden" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label={t("nav.fechar")}
        onClick={aoFechar}
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
      />
      <div
        className={cn(
          "absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-2xl",
          "border-t border-border bg-hud-surface pb-[env(safe-area-inset-bottom)]",
        )}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-hud-surface px-4 py-3">
          <span className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
            {t("nav.tudo")}
          </span>
          <button type="button" onClick={aoFechar} aria-label={t("nav.fechar")}
                  className="rounded p-1 text-muted-foreground hover:text-foreground">
            <X className="size-4" aria-hidden />
          </button>
        </div>

        <div className="px-3 pb-4 pt-1">
          {GRUPOS.map((grupo) => {
            const itens = grupo.itens.filter((i) => !ocultar.includes(i.to));
            if (!itens.length) return null;
            return (
              <section key={grupo.to} className="mt-3 first:mt-1">
                <h2 className="px-1.5 pb-1 font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">
                  {t(grupo.chave)}
                </h2>
                <div className="grid grid-cols-2 gap-1.5">
                  {itens.map((item) => {
                    const ok = liberado(item, capacidades);
                    return (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        onClick={aoFechar}
                        className="flex flex-col gap-0.5 rounded-lg border border-border bg-background/40 px-2.5 py-2 active:bg-primary/10"
                      >
                        <span className="flex items-center gap-1.5">
                          <item.icone className={cn("size-3.5 shrink-0",
                                                    ok ? "text-primary" : "text-muted-foreground")} aria-hidden />
                          <span className={cn("text-[13px] font-medium leading-tight",
                                              ok ? "text-foreground" : "text-muted-foreground")}>
                            {t(item.chave)}
                          </span>
                          {!ok && <Lock className="size-2.5 shrink-0 text-primary" aria-hidden />}
                        </span>
                        {/* O motivo cabe aqui como cabe no desktop: cadeado sem argumento irrita. */}
                        {!ok && (
                          <span className="text-[10px] leading-snug text-muted-foreground/80">
                            {t(`nav.motivo.${item.exige}`)}
                          </span>
                        )}
                      </NavLink>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
