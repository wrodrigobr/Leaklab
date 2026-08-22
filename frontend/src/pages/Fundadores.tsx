import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Clock, Loader2, Upload, MessageSquare, Target } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { founder } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTranslation } from "react-i18next";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * Página pública do programa de parceiros fundadores.
 *
 * A decisão de desenho que importa: **o compromisso vem antes da vaga**, não depois.
 * O bloco do que se espera do fundador aparece acima do botão, com o mesmo peso visual da
 * oferta. Compromisso escondido no rodapé atrai exatamente quem some depois — o cadastro
 * que o painel marca como "Silencioso": ganhou o Pro, nunca importou nada, e no sexto mês
 * não há o que renovar nem conversa a ter.
 *
 * O termo formal (que vem depois) confirma o que a pessoa já leu aqui. Ele não pode ser a
 * primeira vez que ela vê as regras.
 */

const COMPROMISSOS = [
  {
    icone: Target,
    chave: "compromisso.jogar",
  },
  {
    icone: Upload,
    chave: "compromisso.importar",
  },
  {
    icone: MessageSquare,
    chave: "compromisso.reportar",
  },
];

function Compromisso({ icone: Icone, chave }: (typeof COMPROMISSOS)[number]) {
  const { t } = useTranslation("fundadores");
  return (
    <div className="rounded-lg border border-border bg-hud-surface p-5">
      <Icone className="mb-3 size-5 text-primary" aria-hidden />
      <h3 className="font-heading text-base font-bold text-foreground">{t(`${chave}.titulo`)}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{t(`${chave}.texto`)}</p>
    </div>
  );
}

export default function Fundadores() {
  const { t } = useTranslation("fundadores");
  const { user } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState<{
    candidatado_em: string | null; ja_e_fundador: boolean; expira_em: string | null;
  } | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!user) return;
    setCarregando(true);
    founder.status()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setCarregando(false));
  }, [user]);

  const candidatar = async () => {
    // Sem conta o caminho é o cadastro, carregando a candidatura junto — assim a pessoa
    // não precisa se lembrar de voltar aqui depois de criar a conta.
    if (!user) {
      navigate("/login?cadastro=1&fundador=1");
      return;
    }
    setEnviando(true);
    try {
      const r = await founder.apply();
      setStatus((s) => ({
        candidatado_em: r.candidatado_em ?? new Date().toISOString(),
        ja_e_fundador: r.ja_e_fundador ?? s?.ja_e_fundador ?? false,
        expira_em: s?.expira_em ?? null,
      }));
      toast.success(t(r.ja_estava ? "toast.jaEstava" : "toast.registrada"));
    } catch (e) {
      toast.error((e as Error).message || t("toast.erro"));
    } finally {
      setEnviando(false);
    }
  };

  const jaCandidatado = Boolean(status?.candidatado_em);
  const jaFundador = Boolean(status?.ja_e_fundador);

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <main className="mx-auto w-full max-w-3xl px-4 py-14 md:px-8">
        <Link to="/" className="mb-10 inline-block">
          <img src={logoHorizontal} alt="GrindLab" className="h-10 w-auto" />
        </Link>

        <p className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary">
          {t("eyebrow")}
        </p>
        <h1 className="mt-3 font-heading text-3xl font-bold leading-tight text-foreground md:text-4xl">
          {t("titulo")}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground">
          {t("subtitulo")}
        </p>

        {/* O compromisso ANTES do botão, com o mesmo peso da oferta. */}
        <section className="mt-10">
          <h2 className="font-heading text-xl font-bold text-foreground">
            {t("esperado.titulo")}
          </h2>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {t("esperado.aviso")}
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            {COMPROMISSOS.map((c) => <Compromisso key={c.chave} {...c} />)}
          </div>
        </section>

        <section className="mt-10">
          <h2 className="font-heading text-xl font-bold text-foreground">{t("recebe.titulo")}</h2>
          <ul className="mt-4 space-y-2.5">
            {(t("recebe.itens", { returnObjects: true }) as string[]).map((item) => (
              <li key={item} className="flex gap-2.5 text-sm leading-relaxed text-muted-foreground">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-12 rounded-xl border border-border bg-hud-surface p-6">
          {carregando ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> {t("verificando")}
            </p>
          ) : jaFundador ? (
            <div>
              <p className="flex items-center gap-2 font-heading text-lg font-bold text-primary">
                <CheckCircle2 className="size-5" /> {t("jaFundador.titulo")}
              </p>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {t("jaFundador.texto")}
              </p>
              <Link
                to="/dashboard"
                className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow"
              >
                {t("jaFundador.cta")}
              </Link>
            </div>
          ) : jaCandidatado ? (
            /* Estado honesto: "recebemos" não é "você entrou". Prometer vaga aqui seria
               criar expectativa que a fila pode não cumprir. */
            <div>
              <p className="flex items-center gap-2 font-heading text-lg font-bold text-foreground">
                <Clock className="size-5 text-primary" /> {t("naFila.titulo")}
              </p>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {t("naFila.texto")}
              </p>
              <Link
                to="/dashboard"
                className="mt-4 inline-flex h-10 items-center rounded-md border border-border px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-foreground hover:border-primary/40"
              >
                {t("naFila.cta")}
              </Link>
            </div>
          ) : (
            <div>
              <h2 className="font-heading text-lg font-bold text-foreground">
                {t("cta.titulo")}
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {t(user ? "cta.logado" : "cta.deslogado")}
              </p>
              <button
                onClick={candidatar}
                disabled={enviando}
                className={cn(
                  "mt-4 inline-flex h-11 items-center gap-2 rounded-md bg-primary px-6",
                  "font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground",
                  "transition-colors hover:bg-primary-glow disabled:opacity-50",
                )}
              >
                {enviando && <Loader2 className="size-4 animate-spin" aria-hidden />}
                {t(user ? "cta.botaoLogado" : "cta.botaoDeslogado")}
              </button>
            </div>
          )}
        </section>

        <p className="mt-8 text-xs leading-relaxed text-muted-foreground">
          {t("rodape")}
        </p>
      </main>
    </div>
  );
}
