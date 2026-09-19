import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileJson, Loader2, ShieldCheck, Upload } from "lucide-react";
import { adminDashboard, type LinhaSharkscope, type PlanoSharkscope } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Importação do resultado de torneios a partir do JSON do SharkScope. ADMIN.
 *
 * ── O pedido (19/09) ──────────────────────────────────────────────────────────────────────────
 *
 * O dono: "podemos criar um importador com base no json... assim eu posso capturar manualmente os
 * torneios dos jogadores, e inserir na ferramenta... ela deve ser apenas para uso admin por
 * enquanto".
 *
 * Fecha um buraco medido: `buy_in` preenchido em 8,9% dos torneios e `profit` em 6,7%. O
 * PartyPoker não publica summary que saibamos ler, e é a sala que o SharkScope rastreia bem.
 *
 * ── Por que a tela obriga a ver o plano antes ────────────────────────────────────────────────
 *
 * O risco desta importação não é o número, é o PAREAMENTO: casar o resultado de um torneio com
 * outro. Na primeira comparação que fizemos entre este JSON e produção, um pareamento por dia mais
 * buy-in trocou os pares em dias com dois torneios do mesmo valor. Por isso não existe botão que
 * escreve direto: primeiro o plano, e o botão de aplicar só nasce depois dele.
 *
 * ── O que esta tela NÃO faz ──────────────────────────────────────────────────────────────────
 *
 * Não busca nada no SharkScope, não guarda credencial, não automatiza o site deles. Ela recebe um
 * JSON que alguém já tinha em mãos.
 */

function Bloco({ titulo, cor, linhas, nota }: {
  titulo: string;
  cor: string;
  linhas: LinhaSharkscope[];
  nota?: string;
}) {
  if (!linhas.length) return null;
  return (
    <div className="rounded-lg border border-border bg-hud-surface">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span className={cn("font-mono text-[11px] font-bold uppercase tracking-widest-2", cor)}>
          {titulo}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {linhas.length}
        </span>
      </div>
      {nota && <p className="px-3 pt-2 text-[11px] leading-relaxed text-muted-foreground">{nota}</p>}
      <div className="overflow-x-auto p-3">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead>
            <tr className="font-mono text-[9.5px] uppercase tracking-wider text-muted-foreground">
              <th className="pb-1 pr-3">quando</th>
              <th className="pb-1 pr-3">torneio</th>
              <th className="pb-1 pr-3 text-right">buy-in</th>
              <th className="pb-1 pr-3 text-right">prêmio</th>
              <th className="pb-1 pr-3 text-right">lucro</th>
              <th className="pb-1 pr-3 text-right">pos</th>
              <th className="pb-1 pr-3">casou por</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((l, i) => (
              <tr key={i} className="border-t border-border/40">
                <td className="py-1 pr-3 font-mono text-[11px] tabular-nums text-muted-foreground">
                  {l.quando.slice(0, 16).replace("T", " ")}
                </td>
                <td className="py-1 pr-3 text-foreground">
                  {l.torneio}
                  {l.freeroll && (
                    <span className="ml-1.5 rounded bg-sky-500/10 px-1 py-0.5 font-mono text-[9px] text-sky-300">
                      freeroll
                    </span>
                  )}
                  {l.entradas > 1 && (
                    <span className="ml-1.5 rounded bg-amber-500/10 px-1 py-0.5 font-mono text-[9px] text-amber-300">
                      {l.entradas} entradas
                    </span>
                  )}
                </td>
                <td className="py-1 pr-3 text-right font-mono tabular-nums text-muted-foreground">
                  {l.buy_in.toFixed(2)}
                </td>
                <td className="py-1 pr-3 text-right font-mono tabular-nums text-muted-foreground">
                  {l.premio.toFixed(2)}
                </td>
                <td className={cn("py-1 pr-3 text-right font-mono tabular-nums",
                                  l.lucro > 0 ? "text-emerald-400" : l.lucro < 0 ? "text-red-400"
                                                                                 : "text-muted-foreground")}>
                  {l.lucro > 0 ? "+" : ""}{l.lucro.toFixed(2)}
                </td>
                <td className="py-1 pr-3 text-right font-mono tabular-nums text-muted-foreground">
                  {l.colocacao ?? "—"}
                </td>
                <td className="py-1 pr-3 font-mono text-[10px] text-muted-foreground">
                  {l.motivo || l.casou_por || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SharkscopeTab() {
  const [userId, setUserId] = useState("");
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [plano, setPlano] = useState<PlanoSharkscope | null>(null);

  const importar = useMutation({
    mutationFn: ({ aplicar }: { aplicar: boolean }) => {
      // O parse acontece AQUI, antes da rede: JSON torto vira frase na tela em vez de erro 400
      // vindo do servidor. "Nao podemos retornar codigo de erro para o usuario" (o dono, 16/09).
      const payload = JSON.parse(texto);
      return adminDashboard.importarSharkscope(Number(userId), payload, aplicar);
    },
    onSuccess: (p) => { setPlano(p); setErro(null); },
    onError: (e: unknown) => {
      setErro(e instanceof SyntaxError
        ? "Esse texto não é um JSON válido. Cole a resposta inteira, das chaves de abertura às de fechamento."
        : (e instanceof Error ? e.message : "Não consegui importar."));
    },
  });

  const podeSeco = userId.trim() !== "" && texto.trim() !== "" && !importar.isPending;
  const temOQueAplicar = (plano?.atualizar.length ?? 0) > 0 && !plano?.aplicado;

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-border bg-hud-surface p-4">
        <div className="mb-3 flex items-center gap-2">
          <FileJson className="size-4 text-primary" />
          <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground">
            Importar resultado do SharkScope
          </h2>
        </div>
        <p className="mb-4 max-w-[80ch] text-xs leading-relaxed text-muted-foreground">
          Cole o JSON de <span className="font-mono text-foreground">completedTournaments</span> do
          jogador. Isto completa o financeiro dos torneios que já estão na base: buy-in, prêmio,
          colocação, field e premiação total. <strong className="text-foreground">Não traz mão
          nenhuma</strong>, e nunca sobrescreve resultado vindo do arquivo da sala.
        </p>

        <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              user_id
            </span>
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value.replace(/\D/g, ""))}
              inputMode="numeric"
              data-testid="sharkscope-user"
              className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-sm text-foreground outline-none focus:border-primary"
              placeholder="3"
            />
          </label>
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              JSON do SharkScope
            </span>
            <textarea
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              rows={6}
              data-testid="sharkscope-json"
              className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground outline-none focus:border-primary"
              placeholder='{"Response": {"PlayerResponse": ...'
            />
          </label>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={!podeSeco}
            onClick={() => importar.mutate({ aplicar: false })}
            data-testid="sharkscope-simular"
            className="inline-flex items-center gap-1.5 rounded border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-40"
          >
            {importar.isPending ? <Loader2 className="size-3 animate-spin" /> : <ShieldCheck className="size-3" />}
            Simular
          </button>
          {/* O botao de aplicar SO existe depois do plano, e so quando ha o que aplicar. O risco
              aqui nao e o numero, e o pareamento; ver o cabecalho deste arquivo. */}
          {temOQueAplicar && (
            <button
              type="button"
              disabled={importar.isPending}
              onClick={() => importar.mutate({ aplicar: true })}
              data-testid="sharkscope-aplicar"
              className="inline-flex items-center gap-1.5 rounded border border-primary/40 bg-primary/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-primary transition-colors hover:bg-primary/20"
            >
              <Upload className="size-3" />
              Aplicar {plano!.atualizar.length}
            </button>
          )}
        </div>

        {erro && (
          <p data-testid="sharkscope-erro"
             className="mt-3 flex items-start gap-1.5 text-xs leading-relaxed text-red-400">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" /> {erro}
          </p>
        )}
        {plano?.aplicado && (
          <p data-testid="sharkscope-aplicado"
             className="mt-3 flex items-center gap-1.5 text-xs text-emerald-400">
            <CheckCircle2 className="size-3.5" />
            {plano.atualizados ?? 0} torneios atualizados
            {(plano.falhos ?? 0) > 0 && <span className="text-red-400"> · {plano.falhos} falharam</span>}
          </p>
        )}
      </div>

      {plano && (
        <div className="space-y-4">
          <Bloco titulo="vai atualizar" cor="text-primary" linhas={plano.atualizar} />
          <Bloco titulo="já está igual" cor="text-muted-foreground" linhas={plano.iguais}
                 nota="O número no banco já bate com o do SharkScope. Nada a fazer." />
          <Bloco titulo="protegidos" cor="text-amber-400" linhas={plano.protegidos}
                 nota="Já têm resultado vindo do arquivo da sala, que é a fonte mais confiável. O importador não sobrescreve." />
          <Bloco titulo="sem par na base" cor="text-sky-400" linhas={plano.sem_par}
                 nota="O SharkScope tem o torneio e nós não. Normalmente é torneio jogado depois do último upload." />

          {plano.nossos_sem_correspondencia.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
              <div className="mb-1 flex items-center gap-2">
                <AlertTriangle className="size-3.5 text-amber-400" />
                <span className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-amber-400">
                  nossos, sem correspondência
                </span>
                <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                  {plano.nossos_sem_correspondencia.length}
                </span>
              </div>
              {/* Esta lista achou o AY-46. Linha com 1 ou 3 maos que o SharkScope nao conhece nao
                  e torneio: e fragmento do parser. Vale olhar, nao ignorar. */}
              <p className="mb-2 max-w-[80ch] text-[11px] leading-relaxed text-muted-foreground">
                Torneios que temos e o JSON não conhece. Alguns são de outra sala ou de outro
                período. Mas linha com pouquíssimas mãos que o SharkScope não conhece costuma ser
                fragmento do parser, e não torneio.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-left text-xs">
                  <tbody>
                    {plano.nossos_sem_correspondencia.map((t) => (
                      <tr key={t.id} className="border-t border-border/40">
                        <td className="py-1 pr-3 font-mono text-[11px] tabular-nums text-muted-foreground">{t.quando}</td>
                        <td className="py-1 pr-3 font-mono text-[10px] text-muted-foreground">#{t.id}</td>
                        <td className="py-1 pr-3 text-foreground">{t.nome || "—"}</td>
                        <td className={cn("py-1 pr-3 text-right font-mono tabular-nums",
                                          (t.maos ?? 0) <= 5 ? "text-amber-400" : "text-muted-foreground")}>
                          {t.maos ?? "—"} mãos
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
