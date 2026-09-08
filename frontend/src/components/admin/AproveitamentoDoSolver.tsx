import { useQuery } from "@tanstack/react-query";
import { adminDashboard, type CurvaDaSemelhanca } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Aproveitamento do solver (AY-28, 08/09): quanto do acervo de nos e reaproveitado por torneio
 * novo, quanto vai ao solver, e a cobertura que um veredito por semelhanca daria hoje.
 *
 * Por que existe: o dono perguntou "quanto reaproveitamos do que ja esta em base". Medido em
 * prod: 3%. Esta e a tela do antes e do depois de qualquer mudanca na chave do spot.
 */
const fmtH = (h: number | null) => (h == null ? "—" : h < 1 ? `${Math.round(h * 60)} min` : `${h.toFixed(1)} h`);

export function AproveitamentoDoSolver() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-solver-aproveitamento"],
    queryFn: () => adminDashboard.solverAproveitamento(56),
    staleTime: 60_000,
  });
  if (isLoading) return <p className="font-mono text-[10px] text-muted-foreground">…</p>;
  if (!data) return null;
  const ultima = data.semanas[data.semanas.length - 1];
  const fila = data.fila;
  return (
    <div className="space-y-3" data-testid="aproveitamento-solver">
      <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-muted-foreground">Aproveitamento do solver</h3>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Reaproveitado (última semana)" value={ultima ? `${ultima.pct_reaproveitado}%` : "—"}
              sub={ultima ? `${ultima.reaproveitadas} de ${ultima.decisoes} decisões` : "sem decisões"} hot={!!ultima && ultima.pct_reaproveitado < 10} testid="tile-reaproveitado" />
        <Tile label="Cobertura por semelhança (30 d)" value={`${data.semelhanca.pct}%`}
              sub={`${data.semelhanca.com_vizinho} de ${data.semelhanca.sem_no} sem nó · ${data.semelhanca.assinaturas_conhecidas} assinaturas`} testid="tile-semelhanca" />
        <Tile label="Fila do solver" value={String(fila.pending ?? 0)}
              sub={`rodando ${fila.running ?? 0} · falhos ${fila.failed ?? 0} · rejeitados ${fila.rejected ?? 0}`} hot={(fila.pending ?? 0) > 500} testid="tile-fila" />
        <Tile label="Espera mediana (30 d)" value={fmtH(data.espera.mediana_h)}
              sub={`média ${fmtH(data.espera.media_h)} · ${data.espera.n} solves · acervo ${data.acervo.nos.toLocaleString("pt-BR")} nós`} hot={(data.espera.mediana_h ?? 0) > 2} testid="tile-espera" />
      </div>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-xs">
          <thead className="border-b border-border bg-hud-elevated/40">
            <tr>
              {["Semana", "Decisões", "Spots", "Reaproveitadas", "Resolvidas depois", "Sem nó", "Enviados ao solver", "% reaproveitado"].map((h) => (
                <th key={h} className="px-3 py-2 text-left font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.semanas.map((s) => (
              <tr key={s.semana} className="border-b border-border/40" data-testid={`semana-${s.semana}`}>
                <td className="px-3 py-1.5 font-mono">{s.semana}</td>
                <td className="px-3 py-1.5 font-mono tabular-nums">{s.decisoes}</td>
                <td className="px-3 py-1.5 font-mono tabular-nums">{s.spots}</td>
                <td className="px-3 py-1.5 font-mono tabular-nums">{s.reaproveitadas}</td>
                <td className="px-3 py-1.5 font-mono tabular-nums">{s.resolvidas_depois}</td>
                <td className="px-3 py-1.5 font-mono tabular-nums">{s.sem_no}</td>
                <td className="px-3 py-1.5 font-mono tabular-nums">{s.enviados}</td>
                <td className={cn("px-3 py-1.5 font-mono tabular-nums font-bold", s.pct_reaproveitado < 10 ? "text-destructive" : "text-primary")}>{s.pct_reaproveitado}%</td>
              </tr>
            ))}
            {data.semanas.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-3 text-muted-foreground">Sem decisões pós-flop no período.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <CurvaDaSemelhancaBloco curva={data.semelhanca.curva} />
      <p className="font-mono text-[10px] leading-snug text-muted-foreground/70">
        Reaproveitada = o nó já existia quando o torneio entrou. Resolvida depois = o solver correu por ela. Semelhança = decisão sem nó cuja assinatura de board (rua, posição, stack, aposta, textura) já tem árvore resolvida.
      </p>
    </div>
  );
}

const pct = (v: number | null) => (v == null ? "—" : `${v}%`);

/**
 * Curva do veredito por semelhança (passo 2): quanto o provisório bateu com o exato quando o
 * solver chegou. A meta (85% de acordo erro/não-erro com 3+ vizinhos, duas semanas seguidas) é
 * o critério de saída para discutir o passo 3 (mostrar ao jogador). Semana sem comparação não
 * aparece; sem nenhuma, o bloco diz isso em vez de mostrar zeros.
 */
function CurvaDaSemelhancaBloco({ curva }: { curva?: CurvaDaSemelhanca }) {
  if (!curva) return null;
  const m = curva.com_3_vizinhos;
  const ok = curva.meta.atingida;
  return (
    <div className="space-y-2 rounded-xl border border-border p-4" data-testid="curva-semelhanca">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Veredito por semelhança × exato</span>
        <span className={cn("rounded-md border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider",
                            ok ? "border-primary/40 text-primary" : "border-amber-500/30 text-amber-400")} data-testid="meta-semelhanca">
          {ok ? "meta atingida" : "meta aberta"} · {curva.meta.pct}% erro/não-erro com {curva.meta.min_vizinhos}+ vizinhos
        </span>
      </div>
      {curva.total.comparadas === 0 ? (
        <p className="text-xs text-muted-foreground" data-testid="curva-vazia">
          Nenhum provisório comparado ainda{curva.abertos > 0 ? ` (${curva.abertos} esperando o solver)` : ""}.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3 text-xs" data-testid="curva-total">
            <div><span className="text-muted-foreground">ação igual</span><p className="font-mono text-lg font-bold">{pct(curva.total.acao_pct)}</p></div>
            <div><span className="text-muted-foreground">erro/não-erro igual</span><p className="font-mono text-lg font-bold">{pct(curva.total.erro_pct)}</p></div>
            <div><span className="text-muted-foreground">rótulo igual</span><p className="font-mono text-lg font-bold">{pct(curva.total.rotulo_pct)}</p></div>
          </div>
          <p className="font-mono text-[10px] text-muted-foreground" data-testid="curva-recorte">
            {curva.total.comparadas} comparadas · {curva.abertos} abertas · com 3+ vizinhos: {m.comparadas} comparadas, erro/não-erro {pct(m.erro_pct)}
            {Object.keys(curva.ruas).length > 0 && " · por rua: " + Object.entries(curva.ruas).map(([r, b]) => `${r} ${pct(b.erro_pct)} (${b.comparadas})`).join(", ")}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-border">
                <tr>
                  {["Semana", "Comparadas", "Ação", "Erro/não-erro", "Rótulo", "3+ vizinhos: erro/não-erro"].map((h) => (
                    <th key={h} className="px-2 py-1 text-left font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {curva.semanas.map((s) => (
                  <tr key={s.semana} className="border-b border-border/40" data-testid={`curva-${s.semana}`}>
                    <td className="px-2 py-1 font-mono">{s.semana}</td>
                    <td className="px-2 py-1 font-mono tabular-nums">{s.comparadas}</td>
                    <td className="px-2 py-1 font-mono tabular-nums">{pct(s.acao_pct)}</td>
                    <td className={cn("px-2 py-1 font-mono tabular-nums font-bold", (s.erro_pct ?? 0) >= curva.meta.pct ? "text-primary" : "text-amber-400")}>{pct(s.erro_pct)}</td>
                    <td className="px-2 py-1 font-mono tabular-nums">{pct(s.rotulo_pct)}</td>
                    <td className="px-2 py-1 font-mono tabular-nums">{pct(s.com_3_vizinhos.erro_pct)} ({s.com_3_vizinhos.comparadas})</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Tile({ label, value, sub, hot, testid }: { label: string; value: string; sub: string; hot?: boolean; testid: string }) {
  return (
    <div className={cn("rounded-xl border p-4 space-y-1", hot ? "border-amber-500/30 bg-amber-500/5" : "border-border bg-card/60")} data-testid={testid}>
      <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">{label}</span>
      <p className={cn("text-2xl font-bold", hot ? "text-amber-400" : "text-foreground")}>{value}</p>
      <p className="font-mono text-[10px] text-muted-foreground">{sub}</p>
    </div>
  );
}
