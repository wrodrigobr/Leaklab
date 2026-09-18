import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { metrics, type EscopoDoDashboard, type LeakHands } from "@/lib/api";
import { HeroHand } from "@/components/PlayingCard";
import { chaveDoLeak, hrefDaMao } from "@/lib/playlistDoLeak";

/**
 * As maos por tras de uma linha do card "Leaks por custo" (AY-32, pedido de um fundador:
 * "e possivel cada uma dessas linhas ser clicavel, e mostrar a lista de maos em que esta
 * situacao ocorreu? e nesta lista conseguirmos abrir o replayer?").
 *
 * A lista vem da MESMA consulta, do mesmo recorte e da MESMA regua (`decisao_entra_no_leak`)
 * que produzem o numero da linha, entao `total` bate com o `count` dela.
 *
 * ── A mensagem que saiu daqui, e por que ela era errada (15/09) ───────────────────────────────
 *
 * Havia um aviso na tela: "A lista tem 5 maos e a linha diz 4. Alguma coisa esta fora do lugar,
 * e o numero da linha e o que vale". Eu escrevi isso em 09/09 como salvaguarda de honestidade, e
 * era a decisao errada: divergencia entre dois numeros NOSSOS e defeito nosso, e mostra-la ao
 * jogador transfere a ele um problema que ele nao pode resolver, na tela em que ele confia para
 * estudar. O dono viu o aviso em producao e o classificou como bug, com razao.
 *
 * O aviso existia porque a divergencia era possivel, e ela era possivel porque a linha e a lista
 * tinham reguas diferentes. A regua agora e uma, e quem acusa a divergencia e o teste
 * (`test_maos_do_leak`), que semeia multiway e zona de ICM e exige a reconciliacao linha a linha.
 * Deteccao de defeito nosso vive na suite, nao na vitrine.
 */
export function MaosDoLeak({ street, actionTaken, bestAction, escopo }: {
  /** O MESMO escopo do dashboard: este card mostra as maos do leak, e elas tem de sair do
   *  recorte que a faixa verde declara. Era `lastN?: number`, que so sabia contar torneios. */
  street: string; actionTaken: string; bestAction: string; escopo?: EscopoDoDashboard | number | null;
}) {
  const { t } = useTranslation("dashboard");
  const navigate = useNavigate();
  const [dados, setDados] = useState<LeakHands | null>(null);
  const [erro, setErro] = useState(false);
  useEffect(() => {
    let vivo = true;
    setDados(null); setErro(false);
    metrics.evLeakHands(street, actionTaken, bestAction, escopo, 200)
      .then((d) => { if (vivo) setDados(d); })
      .catch(() => { if (vivo) setErro(true); });
    return () => { vivo = false; };
  }, [street, actionTaken, bestAction, escopo]);

  if (erro) return <p className="mt-2 px-1 text-[11px] text-muted-foreground">{t("v2.leakHandsError")}</p>;
  if (!dados) return <p className="mt-2 px-1 font-mono text-[10px] text-muted-foreground/60">…</p>;
  if (dados.total === 0) return <p className="mt-2 px-1 text-[11px] text-muted-foreground">{t("v2.leakHandsEmpty")}</p>;

  return (
    <div className="mt-2 rounded-lg border border-border bg-hud-elevated/30 p-2" data-testid="leak-maos">
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2 px-1">
        <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
          {t("v2.leakHandsTitle", { n: dados.total, bb: dados.loss_bb.toFixed(1) })}
        </span>
        {dados.hands.length < dados.total && (
          <span className="font-mono text-[9px] text-muted-foreground/70">
            {t("v2.leakHandsPartial", { n: dados.hands.length, total: dados.total })}
          </span>
        )}
      </div>
      <div className="max-h-64 overflow-y-auto overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-hud-elevated/95">
            <tr className="text-muted-foreground">
              {["hand", "seat", "stack", "cost", "date", ""].map((k) => (
                <th key={k} className="px-1.5 py-1 text-left font-mono text-[9px] font-normal uppercase tracking-wider">
                  {k ? t(`v2.leakHandsCol.${k}`) : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dados.hands.map((m) => (
              <tr key={m.decision_id} className="border-t border-border/40" data-testid={`leak-mao-${m.decision_id}`}>
                {/* As cartas DESENHADAS (16/09), com o mesmo baralho da mesa e do replayer.
                    Era o texto cru do parser, que mostrava `4dAd` com o quatro na frente do as
                    porque a sala escreve na ordem do assento; `HeroHand` ordena. */}
                <td className="px-1.5 py-1.5"><HeroHand cards={m.hero_cards} /></td>
                <td className="px-1.5 py-1 font-mono">{m.position ?? "—"}</td>
                <td className="px-1.5 py-1 font-mono tabular-nums">{m.stack_bb != null ? `${Math.round(m.stack_bb)}bb` : "—"}</td>
                <td className="px-1.5 py-1 font-mono tabular-nums text-red-400">−{m.ev_loss_bb.toFixed(2)}bb</td>
                <td className="px-1.5 py-1 font-mono text-muted-foreground">{m.played_at ?? "—"}</td>
                <td className="px-1.5 py-1 text-right">
                  <button
                    type="button"
                    onClick={() => navigate(
                      // `leak` e `ln` fazem a PLAYLIST: no replayer as setas percorrem as maos
                      // deste leak, e nao as do torneio de origem. Sem estes dois parametros o
                      // jogador voltava ao dashboard para cada mao (12 vezes, no leak medido).
                      hrefDaMao({
                        mao: m.hand_id,
                        tournamentId: String(m.tournament_id),
                        leakParam: chaveDoLeak({ street, action_taken: actionTaken, best_action: bestAction }),
                        leakLastN: typeof escopo === "number" ? escopo
                          : escopo?.tipo === "torneios" ? escopo.n : undefined,
                      }))}
                    className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                  >
                    {t("v2.leakHandsOpen")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
