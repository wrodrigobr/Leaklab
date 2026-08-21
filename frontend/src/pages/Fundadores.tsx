import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Clock, Loader2, Upload, MessageSquare, Target } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { founder } from "@/lib/api";
import { cn } from "@/lib/utils";
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
    titulo: "Jogar",
    texto: "Você continua jogando seus torneios normalmente. O programa não muda seu jogo, " +
           "nem pede volume que você já não faria.",
  },
  {
    icone: Upload,
    titulo: "Importar",
    texto: "Suba os hand histories dos torneios que jogar. Sem as mãos importadas não há " +
           "leak medido, e é isso que a ferramenta faz de diferente.",
  },
  {
    icone: MessageSquare,
    titulo: "Dizer o que está quebrado",
    texto: "Quando algo travar, estiver confuso ou parecer errado, reporte. Feedback ruim " +
           "e direto vale mais do que elogio.",
  },
];

function Compromisso({ icone: Icone, titulo, texto }: (typeof COMPROMISSOS)[number]) {
  return (
    <div className="rounded-lg border border-border bg-hud-surface p-5">
      <Icone className="mb-3 size-5 text-primary" aria-hidden />
      <h3 className="font-heading text-base font-bold text-foreground">{titulo}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{texto}</p>
    </div>
  );
}

export default function Fundadores() {
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
      toast.success(r.ja_estava ? "Sua candidatura já estava registrada."
                                : "Candidatura registrada. Você entrou na fila.");
    } catch (e) {
      toast.error((e as Error).message || "Não consegui registrar sua candidatura");
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
          Programa de parceiros fundadores
        </p>
        <h1 className="mt-3 font-heading text-3xl font-bold leading-tight text-foreground md:text-4xl">
          Pro liberado por 6 meses para quem vai usar de verdade
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground">
          Estamos abrindo as primeiras vagas de parceiro fundador. Você recebe o plano Pro
          completo, sem pagar, por 6 meses. Em troca, joga, importa seus torneios e conta o
          que está quebrado. É isso: sem letra miúda, sem cartão, sem renovação automática.
        </p>

        {/* O compromisso ANTES do botão, com o mesmo peso da oferta. */}
        <section className="mt-10">
          <h2 className="font-heading text-xl font-bold text-foreground">
            O que se espera de você
          </h2>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Vale ler antes de se candidatar. Quem não usa perde a vaga na renovação, e isso
            é dito aqui de propósito.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            {COMPROMISSOS.map((c) => <Compromisso key={c.titulo} {...c} />)}
          </div>
        </section>

        <section className="mt-10">
          <h2 className="font-heading text-xl font-bold text-foreground">O que você recebe</h2>
          <ul className="mt-4 space-y-2.5">
            {[
              "Plano Pro completo por 6 meses, renovável enquanto o programa fizer sentido para os dois lados",
              "Análise de cada decisão contra um GTO Solver, com o EV perdido em big blinds",
              "Treino dirigido aos seus leaks, montado a partir das suas próprias mãos",
              "Canal direto para reportar problema e sugerir o que falta",
            ].map((t) => (
              <li key={t} className="flex gap-2.5 text-sm leading-relaxed text-muted-foreground">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-12 rounded-xl border border-border bg-hud-surface p-6">
          {carregando ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> verificando sua situação…
            </p>
          ) : jaFundador ? (
            <div>
              <p className="flex items-center gap-2 font-heading text-lg font-bold text-primary">
                <CheckCircle2 className="size-5" /> Você já é parceiro fundador
              </p>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Seu Pro está ativo. A melhor coisa que você pode fazer agora é importar um
                torneio e dizer o que achou estranho.
              </p>
              <Link
                to="/dashboard"
                className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow"
              >
                Ir para o painel
              </Link>
            </div>
          ) : jaCandidatado ? (
            /* Estado honesto: "recebemos" não é "você entrou". Prometer vaga aqui seria
               criar expectativa que a fila pode não cumprir. */
            <div>
              <p className="flex items-center gap-2 font-heading text-lg font-bold text-foreground">
                <Clock className="size-5 text-primary" /> Candidatura registrada
              </p>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Você está na fila. As vagas saem por ordem de chegada, e avisamos assim que
                a sua for confirmada. Enquanto isso, pode usar a plataforma normalmente no
                plano gratuito.
              </p>
              <Link
                to="/dashboard"
                className="mt-4 inline-flex h-10 items-center rounded-md border border-border px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-foreground hover:border-primary/40"
              >
                Começar a usar
              </Link>
            </div>
          ) : (
            <div>
              <h2 className="font-heading text-lg font-bold text-foreground">
                Quero ser parceiro fundador
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {user
                  ? "Ao se candidatar, você concorda com os três compromissos acima."
                  : "Você vai criar sua conta e já entra na fila de candidatos."}
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
                {user ? "Me candidatar" : "Criar conta e me candidatar"}
              </button>
            </div>
          )}
        </section>

        <p className="mt-8 text-xs leading-relaxed text-muted-foreground">
          O programa é por tempo determinado e as vagas saem por ordem de chegada. Não
          prometemos resultado em torneio: o que a ferramenta faz é medir suas decisões e
          apontar onde o EV está indo embora.
        </p>
      </main>
    </div>
  );
}
