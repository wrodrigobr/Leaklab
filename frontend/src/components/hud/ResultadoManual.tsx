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
/**
 * Um campo do formulário.
 *
 * ── Por que ele vive AQUI, e não dentro do componente (17/09) ─────────────────────────────────
 *
 * Ele era declarado dentro de `ResultadoManual`, e o dono relatou: "o formulario está estranho
 * também...a cada digitação, ele perde o foco".
 *
 * A causa é de React e não de CSS: uma função de componente declarada no corpo de outro componente
 * tem IDENTIDADE NOVA em cada render. O React compara os tipos por identidade, vê um componente
 * diferente, e em vez de atualizar o `input` ele DESMONTA a árvore e monta outra. O elemento com o
 * cursor deixa de existir a cada tecla.
 *
 * Declarado fora, a identidade é estável e o `input` é o mesmo elemento entre renders.
 *
 * O formulário tinha oito casos de teste e nenhum pegou isto, porque `fireEvent.change` não olha
 * o foco: o valor chegava certo no estado e o teste passava. Há um caso novo que digita e confere
 * `document.activeElement`.
 */
function Campo({ rotulo, valor, onChange, dica, testid }: {
  rotulo: string; valor: string; onChange: (v: string) => void; dica?: string; testid: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-[9.5px] uppercase tracking-widest-2 text-muted-foreground">
        {rotulo}
      </span>
      <input value={valor} onChange={(e) => onChange(e.target.value)} data-testid={testid}
             inputMode="decimal" placeholder={dica}
             className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-sm tabular-nums text-foreground outline-none transition-colors focus:border-primary" />
    </label>
  );
}

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
  /** quantas vezes ele entrou no torneio: 1 = sem re-entrada. NUNCA zero. */
  const [entradas, setEntradas] = useState("1");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Reabrir com OUTRO torneio não pode herdar os números do anterior: seria o jogador salvando
  // o resultado de um torneio nos campos de outro.
  useEffect(() => {
    if (!torneio) return;
    setPlace(torneio.place != null ? String(torneio.place) : "");
    setPrize(torneio.prize != null ? String(torneio.prize) : "");
    // O `buy_in` GUARDADO e o custo total (buy-in de uma entrada x entradas), que e a convencao
    // do caminho do arquivo. Ao reabrir, ele volta DIVIDIDO pelas entradas, senao o formulario
    // mostraria 2,20 como etiqueta de um torneio de 1,10 -- e salvar de novo dobraria o custo.
    const ent = (torneio.re_entries ?? 0) + 1;
    setEntradas(String(ent));
    setBuyIn(torneio.buy_in != null ? String(Math.round((torneio.buy_in / ent) * 100) / 100) : "");
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
  const e = num(entradas);
  /** o custo REAL: o buy-in de uma entrada vezes o total de entradas */
  const custo = b != null ? Math.round(b * Math.max(1, e ?? 1) * 100) / 100 : null;
  // a mesma conta do servidor, só para ele VER antes de salvar
  const lucro = p != null && custo != null ? Math.round((p - custo) * 100) / 100 : null;

  const salvar = async () => {
    const pl = num(place);
    if (pl == null || pl < 1) { setErro(t("manual.erroColocacao")); return; }
    if (p == null || p < 0) { setErro(t("manual.erroPremio")); return; }
    if (b == null || b < 0) { setErro(t("manual.erroBuyIn")); return; }
    const c = campo.trim() ? num(campo) : null;
    if (c != null && pl > c) { setErro(t("manual.erroColocacaoMaior")); return; }
    const ent = e == null ? 1 : Math.floor(e);
    if (ent < 1) { setErro(t("manual.erroEntradas")); return; }

    setSalvando(true);
    setErro(null);
    try {
      const r = await tournamentsApi.resultadoManual(torneio.tournament_id, {
        place: pl, prize: p, buy_in: b, field_size: c, entradas: ent,
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
          {/* ENTRADAS, e nao re-entradas: ele conta "joguei duas vezes". Fica na mesma grade dos
              outros, e o padrao e 1 -- a maioria dos torneios nao tem re-entrada, e um campo que
              comeca vazio obrigaria todo mundo a preenche-lo. */}
          <Campo rotulo={t("manual.entradas")} valor={entradas} onChange={setEntradas}
                 dica="1" testid="manual-entradas" />
        </div>
        {/* o CUSTO aparece quando ele entrou mais de uma vez: e o numero que o ROI usa, e sem
            mostra-lo o jogador ve um lucro que nao fecha com o buy-in que ele digitou */}
        {custo != null && (e ?? 1) > 1 && (
          <div className="mt-2 flex items-baseline justify-between font-mono text-[9.5px] text-muted-foreground">
            <span className="uppercase tracking-widest-2">{t("manual.custoTotal")}</span>
            <span data-testid="manual-custo" className="tabular-nums">${custo.toFixed(2)}</span>
          </div>
        )}

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
