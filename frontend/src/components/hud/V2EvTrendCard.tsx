import { useTranslation } from "react-i18next";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import { EvSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * V2EvTrendCard — evolução do EV perdido por torneio.
 *
 * ── O que estava errado (reportado pelo usuário) ───────────────────────────────────────────────
 *
 * "este gráfico não é tão intuitivo, não sei se estou melhorando ou piorando na perda de EV".
 * Quatro problemas, e o primeiro é o que dominava a leitura:
 *
 *   1. INVERTIA A CONVENÇÃO. Subir na tela é "melhor" em qualquer gráfico que uma pessoa já viu.
 *      Aqui subir era perder MAIS EV. O pico de 12bb parecia vitória e era o pior torneio. Aviso
 *      em texto não resolve: a leitura visual acontece antes da leitura da legenda.
 *   2. O aviso "menor = melhor" ficava em 9px, cinza a 70%, no canto oposto à entrada do olho —
 *      o mesmo padrão que já falhou na chave dos quadrantes da matriz 13x13.
 *   3. Cada ponto era UM torneio, e um torneio é ruído: a serra oscilava de 0 a 12bb e não
 *      mostrava tendência nenhuma.
 *   4. Não respondia a pergunta. Devolvia 11 pontos para o jogador comparar de cabeça, quando o
 *      produto já sabe a resposta.
 *
 * ── Como ficou ────────────────────────────────────────────────────────────────────────────────
 *
 * O eixo Y é INVERTIDO (`reversed`), então a linha subindo = perdendo menos = melhorando, e a
 * intuição passa a trabalhar a favor. A linha principal é a MÉDIA MÓVEL (a tendência, que foi o
 * que o usuário disse ser o principal); a série crua fica ao fundo, apagada, para quem quiser
 * investigar um torneio específico.
 *
 * O veredito em texto vem do SERVIDOR (`ev_per_100_recent` vs `ev_per_100_prev`, 5 torneios
 * contra 5), e não de um cálculo próprio daqui: aquela função já devolve `null` abaixo de 10
 * decisões ("amostra pequena demais pra taxa honesta"). Recalcular no cliente criaria uma segunda
 * noção de tendência, com outra régua de honestidade — exatamente o padrão que este projeto
 * evita. Sem amostra, o card diz que ainda não dá para afirmar, em vez de inventar direção.
 */

/** Média móvel simples. Janela adaptativa: com poucos pontos, encurta em vez de não existir. */
function mediaMovel(valores: number[], janela: number): (number | null)[] {
  return valores.map((_, i) => {
    const ini = Math.max(0, i - janela + 1);
    const fatia = valores.slice(ini, i + 1);
    if (fatia.length < Math.min(3, janela)) return null;   // 1 ou 2 pontos não são tendência
    return Math.round((fatia.reduce((a, b) => a + b, 0) / fatia.length) * 10) / 10;
  });
}

export function V2EvTrendCard({ evSummary }: { evSummary: EvSummary | null }) {
  const { t } = useTranslation("dashboard");
  const pts = (evSummary?.series ?? []).filter((p) => p.ev_per_100 != null);
  if (pts.length < 2) return null;

  const brutos = pts.map((p) => p.ev_per_100 as number);
  const suave = mediaMovel(brutos, 5);
  const data = pts.map((p, i) => ({
    i,
    name: p.name || `#${p.tournament_id}`,
    ev: brutos[i],
    media: suave[i],
  }));

  const medio = Math.round((brutos.reduce((a, b) => a + b, 0) / brutos.length) * 10) / 10;

  // Veredito: quem decide é o servidor (mesma régua do resto do produto). `null` em qualquer um
  // dos dois lados = sem amostra para afirmar, e é isso que a frase vai dizer.
  const rec = evSummary?.ev_per_100_recent ?? null;
  const ant = evSummary?.ev_per_100_prev ?? null;
  const temVeredito = rec != null && ant != null;
  const delta = temVeredito ? Math.round((ant - rec) * 10) / 10 : null;   // >0 = perdendo menos
  const melhorou = delta != null && delta > 0;
  // Diferença abaixo de 1bb/100 em amostra de 5 torneios é ruído, não direção.
  const estavel = delta != null && Math.abs(delta) < 1;

  const Icone = !temVeredito || estavel ? Minus : melhorou ? TrendingUp : TrendingDown;
  const tom = !temVeredito || estavel
    ? "text-muted-foreground"
    : melhorou ? "text-emerald-400" : "text-red-400";

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        {t("v2.trendTitle")}
      </div>

      {/* A RESPOSTA primeiro, em texto. Era a pergunta que o gráfico não respondia. */}
      <div className="mt-2 flex items-start gap-2">
        <Icone className={cn("mt-0.5 size-4 shrink-0", tom)} aria-hidden />
        <p className="text-[13px] leading-snug text-foreground">
          {!temVeredito
            ? t("v2.trendNoSample")
            : estavel
              ? t("v2.trendStable", { rec })
              : melhorou
                ? t("v2.trendBetter", { rec, ant, delta: Math.abs(delta!) })
                : t("v2.trendWorse", { rec, ant, delta: Math.abs(delta!) })}
        </p>
      </div>

      <div className="mt-3 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#1E2A45" strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false}
                   axisLine={false} interval="preserveStartEnd" />
            {/* `reversed`: menos EV perdido aparece MAIS ALTO. É o conserto principal — a
                intuição "subiu = melhorou" passa a valer sem precisar de legenda. */}
            <YAxis reversed tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false}
                   axisLine={false} width={46}
                   tickFormatter={(v: number) => `−${v}bb`} />
            <Tooltip
              contentStyle={{ background: "#0F1526", border: "1px solid #1E2A45",
                              borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: "#E3E8EC" }}
              formatter={(v: number, key: string) => [
                `−${v} bb/100`,
                key === "media" ? t("v2.trendAvgLabel") : t("v2.evLabel"),
              ]}
            />
            {/* A média histórica como referência: acima da linha é pior que o seu normal. */}
            <ReferenceLine y={medio} stroke="#8B96A8" strokeDasharray="4 4" strokeOpacity={0.5}
                           label={{ value: t("v2.trendAvgRef", { medio }), position: "insideTopRight",
                                    fontSize: 9, fill: "#8B96A8" }} />
            {/* Série crua ao FUNDO: quem quer investigar um torneio ainda encontra. */}
            <Line type="monotone" dataKey="ev" stroke="#8B96A8" strokeWidth={1}
                  strokeOpacity={0.35} dot={false} activeDot={{ r: 3 }} />
            {/* A TENDÊNCIA é a linha principal (o usuário: "o principal é a tendência"). */}
            <Line type="monotone" dataKey="media" stroke="#2DD4BF" strokeWidth={2.5}
                  dot={false} activeDot={{ r: 4 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legenda explícita, porque agora há duas linhas com significados diferentes. */}
      <div className="mt-1.5 flex items-center gap-3 font-mono text-[9px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-3 rounded bg-[#2DD4BF]" aria-hidden />
          {t("v2.trendAvgLabel")}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-3 rounded bg-[#8B96A8] opacity-50" aria-hidden />
          {t("v2.trendRawLabel")}
        </span>
        <span className="ml-auto">{t("v2.trendHintUp")}</span>
      </div>
    </div>
  );
}
