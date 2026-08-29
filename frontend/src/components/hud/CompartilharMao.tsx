import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Check, Copy, Share2, X } from "lucide-react";

import { sharedHand } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * O botão que transforma a mão num link público — com a PERGUNTA do dono.
 *
 * ── Por que a pergunta vai junto (29/08) ──────────────────────────────────────────────────
 *
 * Quem compartilha quase sempre compartilha POR CAUSA de uma decisão ("call ou jam aqui?").
 * O link abre focado nela, e quem clica vota antes de ver o veredito — é o que faz o link ser
 * uma conversa, e não um print. A decisão marcada é a que está NA TELA na hora do clique.
 *
 * O payload público é whitelist no backend: nick de POKER de ninguém sai, nunca. O nome
 * GrindLab de quem compartilha aparece por padrão (30/08, decisão do dono) — anônimo é a
 * opção logo abaixo da pergunta.
 */

interface Props {
  tournamentId: string | number;
  handId: string;
  /** índice do passo em exibição — vira a decisão marcada do link */
  stepIdx?: number;
}

export function CompartilharMao({ tournamentId, handId, stepIdx }: Props) {
  const { t } = useTranslation("common");
  const [aberto, setAberto] = useState(false);
  const [pergunta, setPergunta] = useState("");
  const [anonimo, setAnonimo] = useState(false);
  const [link, setLink] = useState("");
  const [copiado, setCopiado] = useState(false);
  const [erro, setErro] = useState("");
  const [gerando, setGerando] = useState(false);

  const gerar = async () => {
    setGerando(true);
    setErro("");
    try {
      const r = await sharedHand.criar(tournamentId, handId, stepIdx, pergunta.trim() || undefined, anonimo);
      setLink(`${window.location.origin}/h/${r.token}`);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : t("share.erro"));
    } finally {
      setGerando(false);
    }
  };

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // clipboard bloqueado (http/iframe): o campo fica selecionável abaixo
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        title={t("share.botao")}
        className="inline-flex size-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Share2 className="size-3.5" aria-hidden />
      </button>

      {aberto && (
        <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-border bg-hud-surface p-3 shadow-elevated">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              {t("share.titulo")}
            </span>
            <button type="button" onClick={() => setAberto(false)} aria-label={t("nav.fechar")}
                    className="rounded p-0.5 text-muted-foreground hover:text-foreground">
              <X className="size-3.5" aria-hidden />
            </button>
          </div>

          {!link ? (
            <>
              <p className="mb-2 text-[11px] leading-snug text-muted-foreground">
                {t("share.explica")}
              </p>
              <textarea
                value={pergunta}
                onChange={(e) => setPergunta(e.target.value.slice(0, 280))}
                placeholder={t("share.perguntaPlaceholder")}
                rows={2}
                className="mb-2 w-full resize-none rounded-lg border border-border bg-background/50 px-2.5 py-2 text-[12px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {/* 30/08, decisao do dono: nome por padrao (compartilhar e ato publico);
                  anonimo e OPCAO de quem compartilha. */}
              <label className="mb-2 flex cursor-pointer items-center gap-2 text-[11.5px] text-muted-foreground">
                <input type="checkbox" checked={anonimo}
                       onChange={(e) => setAnonimo(e.target.checked)}
                       className="size-3.5 accent-[hsl(var(--primary))]" />
                {t("share.anonimoOpcao")}
              </label>
              {erro && <p className="mb-2 text-[11px] text-destructive">{erro}</p>}
              <button
                type="button"
                onClick={gerar}
                disabled={gerando}
                className="w-full rounded-lg bg-primary px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {gerando ? t("share.gerando") : t("share.publicar")}
              </button>
            </>
          ) : (
            <>
              {/* 30/08, o dono estranhou "gerar link": o ATO e publicar na comunidade; o
                  link e o bonus para colar num grupo. A tela agora diz isso nessa ordem. */}
              <p className="mb-1 flex items-center gap-1.5 text-[12px] font-medium text-foreground">
                <Check className="size-3.5 text-primary" aria-hidden /> {t("share.publicado")}
              </p>
              <RouterLink to="/maos"
                    className="mb-2 inline-block font-mono text-[10.5px] uppercase tracking-wider text-primary hover:underline">
                {t("share.verNoFeed")}
              </RouterLink>
              <p className="mb-2 text-[11px] leading-snug text-muted-foreground">
                {t("share.pronto")}
              </p>
              <div className="mb-2 flex items-center gap-1.5">
                <input
                  readOnly
                  value={link}
                  onFocus={(e) => e.target.select()}
                  className="min-w-0 flex-1 rounded-lg border border-border bg-background/50 px-2 py-1.5 font-mono text-[10.5px] text-foreground"
                />
                <button
                  type="button"
                  onClick={copiar}
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-lg border transition-colors",
                    copiado
                      ? "border-primary/40 bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                  aria-label={t("share.copiar")}
                >
                  {copiado ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
                </button>
              </div>
              <p className="text-[10px] leading-snug text-muted-foreground/70">
                {t("share.anonimo")}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
