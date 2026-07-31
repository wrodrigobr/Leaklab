import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { ONDE_ACHO, SITES, NOME_DO_SITE, type SiteSuportado } from "@/lib/ondeAchoOArquivo";

/**
 * PrimeiroAcesso — o que fazer quando ainda não há dado nenhum.
 *
 * ── Por que NÃO é um tour pela tela ───────────────────────────────────────────────────────────
 *
 * O pedido foi "um carrossel indicando o que deve ser feito, destacando onde clicar". Mas antes do
 * primeiro upload o dashboard é **vazio por construção**: um tour apontando para cards vazios
 * ensina que o produto é vazio. O gargalo real está antes da tela, e é conseguir o arquivo.
 *
 * Então o fluxo é: **achar o arquivo → subir → saber o que esperar**. Só depois do upload existe
 * tela para apontar, e aí quem conduz é o Próximo Passo, que já existe. Criar aqui um segundo
 * motor de "o que fazer agora" seria o risco que a spec do protocolo chama de sistema paralelo:
 * dois eixos discordando na cara do aluno.
 *
 * ── A honestidade do passo 3 ──────────────────────────────────────────────────────────────────
 *
 * Medido em 2026-07-31: um aluno com 258 decisões tem ZERO família com amostra para validar. Se o
 * onboarding prometer tudo no primeiro torneio, a pessoa sobe um arquivo, vê "ainda não dá para
 * afirmar" e conclui que o produto não funciona. Por isso o passo 3 diz o que aparece AGORA e o
 * que precisa de mais volume, com o número.
 */
export function PrimeiroAcesso({ className }: { className?: string }) {
  const { t } = useTranslation("dashboard");
  const [site, setSite] = useState<SiteSuportado>("pokerstars");
  const [copiado, setCopiado] = useState(false);
  const info = ONDE_ACHO[site];

  const copiar = () => {
    if (!info.caminho) return;
    navigator.clipboard?.writeText(info.caminho).then(
      () => { setCopiado(true); setTimeout(() => setCopiado(false), 1800); },
      () => null,
    );
  };

  return (
    <section className={cn("rounded-2xl border border-border bg-card/40 p-5", className)}
             aria-labelledby="primeiro-acesso-titulo">
      <p className="font-mono text-[10px] uppercase tracking-widest text-primary">
        {t("primeiroAcesso.eyebrow")}
      </p>
      <h2 id="primeiro-acesso-titulo" className="mt-1 font-heading text-lg font-bold text-foreground">
        {t("primeiroAcesso.titulo")}
      </h2>
      <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
        {t("primeiroAcesso.subtitulo")}
      </p>

      <ol className="mt-4 space-y-4">
        {/* ── 1. Achar o arquivo: o passo que hoje e uma frase entre parenteses ── */}
        <li className="flex gap-3">
          <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-[11px] font-bold text-primary">1</span>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-medium text-foreground">{t("primeiroAcesso.p1.titulo")}</h3>

            <div className="mt-2 flex flex-wrap gap-1.5" role="tablist"
                 aria-label={t("primeiroAcesso.p1.escolhaSite")}>
              {SITES.map((s) => (
                <button key={s} type="button" role="tab" aria-selected={site === s}
                        onClick={() => setSite(s)}
                        className={cn("rounded-full px-3 py-1 font-mono text-[11px] ring-1 transition-colors",
                          site === s ? "bg-primary/15 text-primary ring-primary/40"
                                     : "text-muted-foreground ring-border hover:text-foreground")}>
                  {NOME_DO_SITE[s]}
                </button>
              ))}
            </div>

            {info.precisaLigar && (
              <p className="mt-2 text-[12px] leading-snug text-foreground">
                {t("primeiroAcesso.p1.ligarPrimeiro", { site: NOME_DO_SITE[site] })}
              </p>
            )}

            {info.caminho ? (
              <div className="mt-2">
                <p className="text-[12px] leading-snug text-muted-foreground">
                  {t("primeiroAcesso.p1.pasta")}
                </p>
                <div className="mt-1 flex items-center gap-2 rounded-lg bg-background/70 p-2 ring-1 ring-border">
                  <code className="min-w-0 flex-1 truncate font-mono text-[11px] text-foreground">
                    {info.caminho}
                  </code>
                  <button type="button" onClick={copiar}
                          aria-label={t("primeiroAcesso.p1.copiar")}
                          className="shrink-0 rounded-md p-1 text-muted-foreground hover:text-primary">
                    {copiado ? <Check className="size-3.5 text-emerald-400" aria-hidden />
                             : <Copy className="size-3.5" aria-hidden />}
                  </button>
                </div>
              </div>
            ) : (
              // Sem caminho verificado, a tela NAO inventa um. Caminho errado manda a pessoa
              // procurar onde nao tem, e ela conclui que o produto nao serve para o site dela.
              <p className="mt-2 text-[12px] leading-snug text-muted-foreground">
                {t("primeiroAcesso.p1.semCaminho", { site: NOME_DO_SITE[site] })}
              </p>
            )}
          </div>
        </li>

        {/* ── 2. Subir: o upload ja existe, o onboarding so aponta para ele ── */}
        <li className="flex gap-3">
          <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-[11px] font-bold text-primary">2</span>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-medium text-foreground">{t("primeiroAcesso.p2.titulo")}</h3>
            <p className="mt-1 text-[12px] leading-snug text-muted-foreground">
              {t("primeiroAcesso.p2.desc")}
            </p>
          </div>
        </li>

        {/* ── 3. O que esperar, com o numero ── */}
        <li className="flex gap-3">
          <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-[11px] font-bold text-primary">3</span>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-medium text-foreground">{t("primeiroAcesso.p3.titulo")}</h3>
            <ul className="mt-1.5 space-y-1 text-[12px] leading-snug text-muted-foreground">
              <li>{t("primeiroAcesso.p3.agora")}</li>
              <li>{t("primeiroAcesso.p3.depois")}</li>
            </ul>
            {/* A expectativa honesta. Sem ela o aluno sobe um torneio, ve "ainda nao da para
                afirmar" e conclui que o produto nao funciona. */}
            <p className="mt-2 rounded-lg bg-background/70 p-2 text-[11px] leading-snug text-muted-foreground ring-1 ring-border">
              {t("primeiroAcesso.p3.honestidade")}
            </p>
          </div>
        </li>
      </ol>
    </section>
  );
}
