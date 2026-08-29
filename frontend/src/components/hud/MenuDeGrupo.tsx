import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronDown, Lock } from "lucide-react";

import type { CorDeItem, GrupoDeMenu, ItemDeMenu } from "./navGrupos";

/** cor de intenção → classes do tile (a mesma língua dos ícones do catálogo) */
const COR_DO_TILE: Record<CorDeItem, string> = {
  teal:   "bg-primary/10 text-primary",
  amber:  "bg-amber-400/10 text-amber-400",
  blue:   "bg-sky-400/10 text-sky-400",
  red:    "bg-red-400/10 text-red-400",
  purple: "bg-purple-400/10 text-purple-400",
};
import { cn } from "@/lib/utils";

/**
 * Um grupo do menu: o título leva a algum lugar, e o painel mostra TUDO que o grupo tem.
 *
 * ── Por que existe (28/08) ────────────────────────────────────────────────────────────────
 *
 * O produto tem 47 rotas de jogador e a barra oferecia 11. O jogador via seis palavras e concluía
 * que o produto tinha seis telas — `/ranges`, `/evolucao`, `/ghost`, `/grind`, `/hand-builder` e
 * 23 aulas da Academia não tinham porta de entrada.
 *
 * ── Três decisões que separam isto do menu do benchmark ───────────────────────────────────
 *
 * **1. Abre no toque, não só no hover.** O menu que inspirou este é hover puro, e hover não
 * existe em tela sensível ao toque. A base aqui é grinder, e grinder revisa no celular: no touch
 * o título vira botão. O hover continua valendo no desktop, porque lá ele é mais rápido.
 *
 * **2. O título continua sendo um link.** Um menu em que o topo só abre painel obriga dois
 * cliques para chegar onde um bastava.
 *
 * **3. O cadeado explica.** "Pro" sozinho irrita; "Pro — treina os seus erros medidos" vende. E o
 * item travado continua CLICÁVEL: quem clica vê a tela com o convite, em vez de bater num item
 * morto. Esconder o que é pago faria o jogador descobrir o paywall depois de investir tempo, que
 * é o dano que a landing causou hoje de manhã.
 */

interface Props {
  grupo: GrupoDeMenu;
  /** capacidades que o usuário TEM; `undefined` enquanto o backend não respondeu */
  capacidades?: Record<string, boolean | number | null | undefined>;
  /** itens a ocultar por regra de negócio (ex.: `/coaches` sem coach vinculado) */
  ocultar?: string[];
}

/** O item tem a capacidade que exige? Sem resposta do backend ainda, assume que SIM — um cadeado
 *  que pisca enquanto carrega é pior que cadeado nenhum, porque acusa o usuário de não ter o que
 *  ele talvez tenha. */
function liberado(item: ItemDeMenu, caps?: Props["capacidades"]): boolean {
  if (!item.exige) return true;
  if (!caps) return true;
  return caps[item.exige] !== false;
}

export function MenuDeGrupo({ grupo, capacidades, ocultar = [] }: Props) {
  const { t } = useTranslation("common");
  const location = useLocation();
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLDivElement>(null);

  const aceso = grupo.acende.some(
    (p) => location.pathname === p || location.pathname.startsWith(p + "/"),
  );

  // Fecha ao navegar: sem isto o painel fica aberto por cima da tela nova.
  useEffect(() => { setAberto(false); }, [location.pathname]);

  // Fecha ao clicar fora e no Esc — teclado é caminho de primeira classe, não cortesia.
  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => {
      if (caixa.current && !caixa.current.contains(e.target as Node)) setAberto(false);
    };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAberto(false); };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);

  return (
    <div
      ref={caixa}
      className="relative shrink-0"
      onMouseEnter={() => setAberto(true)}
      onMouseLeave={() => setAberto(false)}
    >
      {/* v2 (30/08): gatilho com ícone + PILL de estado — o sublinhado fino quase não
          registrava; o fundo preenchido é o que dá presença ao grupo aberto/ativo. */}
      <div className="flex items-center">
        <NavLink
          to={grupo.to}
          className={cn(
            "flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-[12.5px] font-semibold transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            (aceso || aberto)
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <grupo.icone className="size-[15px]" aria-hidden />
          {t(grupo.chave)}
        </NavLink>
        <button
          type="button"
          aria-expanded={aberto}
          aria-label={t(grupo.chave)}
          onClick={() => setAberto((v) => !v)}
          className="-ml-1 rounded p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronDown className={cn("size-3 transition-transform", aberto && "rotate-180")} aria-hidden />
        </button>
      </div>

      {aberto && (
        /* ── O VAO mata o hover (28/08) ────────────────────────────────────────────────────
           A 1a versao punha `mt-3` aqui: 12px de espaco entre o titulo e o painel. Ao mover o
           mouse para baixo, o ponteiro saia do container, `onMouseLeave` disparava e o painel
           fechava ANTES de o mouse chegar nele. Medido: abre no hover, e some no vao.

           O afastamento agora e `padding` do proprio painel (`pt-3` no wrapper), que faz parte da
           area sensivel. O visual e o mesmo; a diferenca e que o mouse nunca sai. */
        <div className="absolute left-0 top-full z-50 pt-3">
        {/* Mega-menu v2 (30/08, aprovado sobre a proposta renderizada): colunas TITULADAS —
            a arquitetura do grupo aparece antes dos itens, que é a diferença nº 1 medida
            contra o benchmark. A descrição segue sempre visível (v1 de 29/08). */}
        <div className="flex gap-6 rounded-xl border border-border bg-hud-surface p-4 shadow-elevated">
          {grupo.secoes.map((secao) => {
            const daSecao = secao.itens.filter((i) => !ocultar.includes(i.to));
            if (!daSecao.length) return null;
            return (
              <div key={secao.chave} className="min-w-[218px]">
                <p className="px-2 pb-2 font-mono text-[9.5px] font-bold uppercase tracking-widest text-muted-foreground/70">
                  {t(secao.chave)}
                </p>
                {daSecao.map((item) => {
            const ok = liberado(item, capacidades);
            const Icone = item.icone;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={cn(
                  "group/item flex items-center gap-3 rounded-lg px-2.5 py-2 transition-colors",
                  "hover:bg-primary/[0.07] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                <span className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-lg transition-colors",
                  ok ? COR_DO_TILE[item.cor ?? "teal"] : "bg-background/40 text-muted-foreground",
                )}>
                  <Icone className="size-4" aria-hidden />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-px">
                  {/* PRO inline: lê na mesma fixação do rótulo — na borda direita exigia um
                      segundo olhar (a diferença nº 3 do benchmark). */}
                  <span className={cn("flex items-center gap-1.5 text-[13px] font-semibold leading-tight",
                                      ok ? "text-foreground" : "text-muted-foreground")}>
                    {t(item.chave)}
                    {!ok && (
                      <span className="flex shrink-0 items-center gap-1 rounded bg-amber-400/10 px-1 py-0.5">
                        <Lock className="size-2.5 text-amber-400" aria-hidden />
                        <span className="font-mono text-[8px] font-bold uppercase tracking-wider text-amber-400">
                          Pro
                        </span>
                      </span>
                    )}
                  </span>
                  <span className="truncate text-[10.5px] leading-snug text-muted-foreground/80">
                    {ok ? t(item.desc) : t(`nav.motivo.${item.exige}`)}
                  </span>
                </span>
              </NavLink>
                );
                })}
              </div>
            );
          })}
        </div>
        </div>
      )}
    </div>
  );
}
