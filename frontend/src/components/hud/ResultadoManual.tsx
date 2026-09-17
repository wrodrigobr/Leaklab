import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, X } from "lucide-react";
import { tournaments as tournamentsApi, type Tournament } from "@/lib/api";

/**
 * O jogador preenche o resultado do torneio, quando a sala não publica o Tournament Summary.
 *
 * ── Por que existe (17/09) ────────────────────────────────────────────────────────────────────
 *
 * O dono: "nao haviamos criado um meio de torneios do party poker, o usuario conseguir preencher
 * os dados do summary que precisamos?". O PartyPoker entrega só mãos no export (conferido no
 * arquivo real do Rullian: zero linha de colocação ou prêmio em 157 mil linhas), então aqueles
 * torneios ficavam com "sem resultado" para sempre -- e sem prêmio não há ROI nem bankroll.
 *
 * ── O que ele NÃO pede ────────────────────────────────────────────────────────────────────────
 *
 * O lucro. Ele é `prêmio - buy-in`, calculado no servidor: três campos digitados poderiam não
 * fechar entre si, e ninguém saberia qual deles o ROI usou. A tela mostra a conta enquanto ele
 * digita, para o número não ser surpresa depois de salvar.
 */
export function ResultadoManual({ torneio, onFechar, onSalvo }: {
  torneio: Tournament | null;
  onFechar: () => void;
  onSalvo: (t: { place: number; prize: number; buy_in: number; profit: number }) => void;
}) {
  const { t } = useTranslation("tournaments");
  const [place, setPlace] = useState("");
  const [prize, setPrize] = useState("");
  const [buyIn, setBuyIn] = useState("");
  const [campo, setCampo] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Reabrir com OUTRO torneio não pode herdar os números do anterior: seria o jogador salvando
  // o resultado de um torneio nos campos de outro.
  useEffect(() => {
    if (!torneio) return;
    setPlace(torneio.place != null ? String(torneio.place) : "");
    setPrize(torneio.prize != null ? String(torneio.prize) : "");
    setBuyIn(torneio.buy_in != null ? String(torneio.buy_in) : "");
    setCampo(torneio.field_size != null ? String(torneio.field_size) : "");
    setErro(null);
  }, [torneio]);

  if (!torneio) return null;

  const num = (s: string) => {
    // Campo VAZIO é `null`, e não zero: `Number("")` devolve 0, e com isso a tela dizia
    // "lucro $0.00" antes de ele digitar qualquer coisa -- afirmação sobre um dado que não existe.
    // Achado pelo teste, não pela leitura.
    const bruto = s.trim();
    if (!bruto) return null;
    const v = Number(bruto.replace(",", "."));
    return Number.isFinite(v) ? v : null;
  };
  const p = num(prize);
  const b = num(buyIn);
  // a mesma conta do servidor, só para ele VER antes de salvar
  const lucro = p != null && b != null ? Math.round((p - b) * 100) / 100 : null;

  const salvar = async () => {
    const pl = num(place);
    if (pl == null || pl < 1) { setErro(t("manual.erroColocacao")); return; }
    if (p == null || p < 0) { setErro(t("manual.erroPremio")); return; }
    if (b == null || b < 0) { setErro(t("manual.erroBuyIn")); return; }
    const c = campo.trim() ? num(campo) : null;
    if (c != null && pl > c) { setErro(t("manual.erroColocacaoMaior")); return; }

    setSalvando(true);
    setErro(null);
    try {
      const r = await tournamentsApi.resultadoManual(torneio.tournament_id, {
        place: pl, prize: p, buy_in: b, field_size: c,
      });
      onSalvo({ place: r.place, prize: r.prize, buy_in: r.buy_in, profit: r.profit });
      onFechar();
    } catch (e) {
      // A frase do servidor quando ela existe (ele já manda tratada), e uma nossa quando não:
      // "nao podemos retornar codigo de erro para o usuario" (o dono, 16/09).
      const msg = e instanceof Error ? e.message : "";
      setErro(msg && !/^\d+$/.test(msg) ? msg : t("manual.erroSalvar"));
    } finally {
      setSalvando(false);
    }
  };

  const Campo = ({ rotulo, valor, onChange, dica, testid }: {
    rotulo: string; valor: string; onChange: (v: string) => void; dica?: string; testid: string;
  }) => (
    <label className="block">
      <span className="mb-1 block font-mono text-[9.5px] uppercase tracking-widest-2 text-muted-foreground">
        {rotulo}
      </span>
      <input value={valor} onChange={(e) => onChange(e.target.value)} data-testid={testid}
             inputMode="decimal" placeholder={dica}
             className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-sm tabular-nums text-foreground outline-none transition-colors focus:border-primary" />
    </label>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4"
         data-testid="resultado-manual">
      <div className="w-full max-w-sm rounded-lg border border-border bg-hud-surface p-4 shadow-xl">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[11px] uppercase tracking-widest-2 text-primary">
              {t("manual.titulo")}
            </div>
            <div className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">
              {torneio.tournament_name || torneio.tournament_id} · {torneio.site}
            </div>
          </div>
          <button onClick={onFechar} data-testid="resultado-manual-fechar"
                  className="shrink-0 text-muted-foreground transition-colors hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Campo rotulo={t("manual.colocacao")} valor={place} onChange={setPlace}
                 dica="6" testid="manual-place" />
          <Campo rotulo={t("manual.jogadores")} valor={campo} onChange={setCampo}
                 dica="180" testid="manual-field" />
          <Campo rotulo={t("manual.buyIn")} valor={buyIn} onChange={setBuyIn}
                 dica="5.50" testid="manual-buyin" />
          <Campo rotulo={t("manual.premio")} valor={prize} onChange={setPrize}
                 dica="12.40" testid="manual-prize" />
        </div>

        {/* O lucro é CALCULADO, e aparece aqui para não ser surpresa depois de salvar. */}
        <div className="mt-3 flex items-baseline justify-between rounded border border-border/60 bg-background/40 px-2.5 py-2">
          <span className="font-mono text-[9.5px] uppercase tracking-widest-2 text-muted-foreground">
            {t("manual.lucro")}
          </span>
          <span data-testid="manual-lucro"
                className={`font-mono text-sm font-bold tabular-nums ${
                  lucro == null ? "text-muted-foreground"
                  : lucro > 0 ? "text-emerald-400" : lucro < 0 ? "text-red-400" : "text-foreground"}`}>
            {lucro == null ? "—" : `${lucro > 0 ? "+" : ""}$${Math.abs(lucro).toFixed(2)}`}
          </span>
        </div>

        <p className="mt-2 font-mono text-[9px] leading-relaxed text-muted-foreground/80">
          {t("manual.avisoOrigem")}
        </p>

        {erro && (
          <p data-testid="resultado-manual-erro"
             className="mt-2 rounded border border-red-500/30 bg-red-500/10 px-2 py-1.5 font-mono text-[10px] leading-relaxed text-red-300">
            {erro}
          </p>
        )}

        <button onClick={() => void salvar()} disabled={salvando} data-testid="resultado-manual-salvar"
                className="mt-3 flex w-full items-center justify-center gap-1.5 rounded bg-primary px-2 py-2 font-mono text-[10.5px] font-bold uppercase tracking-widest-2 text-background transition-colors hover:bg-primary-glow disabled:opacity-60">
          {salvando && <Loader2 className="size-3 animate-spin" />}
          {t("manual.salvar")}
        </button>
      </div>
    </div>
  );
}

/**
 * A marca de PROCEDÊNCIA ao lado de um número financeiro.
 *
 * Existe como componente, e não como um `&&` dentro da tabela, por causa de um guarda que passou
 * verde: o teste da tela lia o FONTE e exigia a palavra `financeiro_origem` nele. Quando eu
 * quebrei a condição de propósito (`false &&`), a palavra continuou no comentário e no tipo, e o
 * guarda não viu nada. Componente próprio tem teste de COMPORTAMENTO.
 *
 * Por que a marca existe: o número digitado sustenta o ROI e o bankroll igual ao número que veio
 * do arquivo da sala, e quem digitou precisa saber qual dos dois está olhando.
 */
export function MarcaDeProcedencia({ origem }: { origem?: "arquivo" | "manual" | null }) {
  const { t } = useTranslation("tournaments");
  if (origem !== "manual") return null;
  return (
    <span data-testid="lucro-digitado" title={t("manual.digitado")}
          className="font-mono text-[8.5px] uppercase tracking-wider text-muted-foreground/70">
      {t("manual.digitado")}
    </span>
  );
}
