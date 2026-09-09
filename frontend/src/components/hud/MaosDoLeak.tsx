import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { metrics, type LeakHands } from "@/lib/api";

/**
 * As maos por tras de uma linha do card "Leaks por custo" (AY-32, pedido de um fundador:
 * "e possivel cada uma dessas linhas ser clicavel, e mostrar a lista de maos em que esta
 * situacao ocorreu? e nesta lista conseguirmos abrir o replayer?").
 *
 * A lista vem da MESMA consulta, do mesmo recorte e da mesma regua que produzem o numero da
 * linha, entao `total` bate com o `count` dela. Quando nao bater, a tela DIZ isso em vez de
 * deixar o jogador concluir sozinho que faltou dado.
 */
export function MaosDoLeak({ street, actionTaken, bestAction, esperado, lastN }: {
  street: string; actionTaken: string; bestAction: string; esperado: number; lastN?: number | null;
}) {
  const { t } = useTranslation("dashboard");
  const navigate = useNavigate();
  const [dados, setDados] = useState<LeakHands | null>(null);
  const [erro, setErro] = useState(false);
  useEffect(() => {
    let vivo = true;
    setDados(null); setErro(false);
    metrics.evLeakHands(street, actionTaken, bestAction, lastN ?? undefined, 200)
      .then((d) => { if (vivo) setDados(d); })
      .catch(() => { if (vivo) setErro(true); });
    return () => { vivo = false; };
  }, [street, actionTaken, bestAction, lastN]);

  if (erro) return <p className="mt-2 px-1 text-[11px] text-muted-foreground">{t("v2.leakHandsError")}</p>;
  if (!dados) return <p className="mt-2 px-1 font-mono text-[10px] text-muted-foreground/60">…</p>;
  if (dados.total === 0) return <p className="mt-2 px-1 text-[11px] text-muted-foreground">{t("v2.leakHandsEmpty")}</p>;

  const faltando = dados.total !== esperado;
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
      {faltando && (
        <p className="mb-1.5 px-1 font-mono text-[9px] leading-snug text-amber-400/80" data-testid="leak-divergencia">
          {t("v2.leakHandsMismatch", { lista: dados.total, linha: esperado })}
        </p>
      )}
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
                <td className="px-1.5 py-1 font-mono">{m.hero_cards ?? "—"}</td>
                <td className="px-1.5 py-1 font-mono">{m.position ?? "—"}</td>
                <td className="px-1.5 py-1 font-mono tabular-nums">{m.stack_bb != null ? `${Math.round(m.stack_bb)}bb` : "—"}</td>
                <td className="px-1.5 py-1 font-mono tabular-nums text-red-400">−{m.ev_loss_bb.toFixed(2)}bb</td>
                <td className="px-1.5 py-1 font-mono text-muted-foreground">{m.played_at ?? "—"}</td>
                <td className="px-1.5 py-1 text-right">
                  <button
                    type="button"
                    onClick={() => navigate(`/replayer?t=${m.tournament_id}&h=${m.hand_id}`)}
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
