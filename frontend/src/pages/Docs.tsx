import { useEffect, useRef, useState } from "react";
import { HudLayout } from "@/components/hud/HudLayout";
import { BookOpen, ChevronRight } from "lucide-react";

const SECTIONS = [
  { id: "scoring",      label: "Sistema de Scoring" },
  { id: "indicators",   label: "Indicadores" },
  { id: "mstacks",      label: "Fases de M-Ratio" },
  { id: "dna",          label: "Decision DNA" },
  { id: "ghost",        label: "Ghost Table / Drills" },
  { id: "compare",      label: "Comparativo de Torneios" },
  { id: "coaching",     label: "Coaching" },
  { id: "gamification", label: "Gamificação" },
];

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-widest ${color}`}>
      {children}
    </span>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 space-y-4">
      <h2 className="text-xl font-semibold tracking-tight text-foreground border-b border-border pb-2">
        {title}
      </h2>
      <div className="space-y-4 text-sm text-muted-foreground leading-relaxed">
        {children}
      </div>
    </section>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border bg-hud-surface">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-left font-mono font-bold uppercase tracking-widest text-muted-foreground">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0 hover:bg-hud-surface/50 transition-colors">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 text-foreground">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Docs() {
  const [active, setActive] = useState(SECTIONS[0].id);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
    );
    SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observerRef.current?.observe(el);
    });
    return () => observerRef.current?.disconnect();
  }, []);

  return (
    <HudLayout>
      <div className="mx-auto max-w-[1440px] px-4 pt-8 pb-28 md:px-8 md:pb-12">
        <div className="mb-8">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary mb-3">
            <BookOpen className="size-3.5" />
            Documentação
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            Como o Sistema Funciona
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Referência técnica dos indicadores, metodologia de scoring e recursos da plataforma.
          </p>
        </div>

        <div className="flex gap-10 items-start">
          {/* ── Sidebar nav ──────────────────────────────────────────────── */}
          <nav className="hidden lg:block sticky top-24 w-52 shrink-0 space-y-0.5">
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className={`flex items-center gap-2 rounded-md px-3 py-2 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                  active === s.id
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-hud-surface"
                }`}
              >
                {active === s.id && <ChevronRight className="size-3 shrink-0" />}
                {active !== s.id && <span className="size-3 shrink-0" />}
                {s.label}
              </a>
            ))}
          </nav>

          {/* ── Content ──────────────────────────────────────────────────── */}
          <div className="flex-1 min-w-0 space-y-14">

            {/* ── 1. Sistema de Scoring ────────────────────────────────── */}
            <Section id="scoring" title="Sistema de Scoring">
              <p>
                Cada decisão importada é avaliada por um score de <strong className="text-foreground">0 a 1</strong>, onde
                0 representa a decisão ótima e 1 representa o maior desvio possível do ideal. O score combina
                quatro fatores ponderados: equity da mão, adequação da aposta (bet sizing), awareness posicional e
                contexto MTT (M-ratio e pressão ICM).
              </p>
              <Table
                headers={["Label", "Score", "Significado"]}
                rows={[
                  [<Badge color="bg-emerald-500/15 text-emerald-400">Standard</Badge>,   "0.00 – 0.08", "Linha sólida. Desvio mínimo do ótimo."],
                  [<Badge color="bg-yellow-500/15 text-yellow-400">Marginal</Badge>,      "0.09 – 0.18", "Ação defensável, mas existe alternativa levemente melhor."],
                  [<Badge color="bg-orange-500/15 text-orange-400">Small Mistake</Badge>, "0.19 – 0.36", "Pequena perda estratégica, relevante no longo prazo."],
                  [<Badge color="bg-destructive/15 text-destructive">Clear Mistake</Badge>, "> 0.36",   "Erro claro com impacto relevante em EV."],
                ]}
              />
              <p>
                O sistema considera o contexto MTT ao reclassificar decisões: em situações de alta pressão ICM
                (M ≤ 6 ou final table), margens de erro são menores — uma decisão <em>marginal</em> pode ser
                reclassificada para <em>small_mistake</em> se o contexto amplifica o custo estratégico.
              </p>
              <p>
                O <strong className="text-foreground">Standard%</strong> de um torneio é a porcentagem de decisões
                com label <em>standard</em> sobre o total analisado. É o principal indicador de qualidade
                técnica de uma sessão.
              </p>
            </Section>

            {/* ── 2. Indicadores ───────────────────────────────────────── */}
            <Section id="indicators" title="Indicadores">
              <Table
                headers={["Indicador", "O que mede", "Como interpretar"]}
                rows={[
                  ["Standard%",     "% de decisões classificadas como standard no período",             "Alvo: acima de 70%. Jogadores elite ficam acima de 92%."],
                  ["Avg Score",     "Média do score bruto 0–1 de todas as decisões",                    "Quanto menor, melhor. < 0.15 é excelente; > 0.30 indica volume de erros."],
                  ["Clear Mistakes%", "% de decisões com score > 0.36",                                "Diretamente ligado ao EV perdido por sessão. Alvo: < 5%."],
                  ["Leak ROI",      "EV estimado perdido por leak spot no período (em BBs)",            "Priorize os leaks com maior ROI negativo — são os que mais custam."],
                  ["ICM Pressure",  "Nível de pressão ICM no momento da decisão (low / medium / high)", "Decisões com ICM high incorretas custam mais no longo prazo."],
                  ["Confidence Drift", "Tendência de queda de qualidade em sessões consecutivas",       "Indica tilt ou fadiga. Revisão das últimas sessões recomendada."],
                ]}
              />
              <p>
                <strong className="text-foreground">Leak ROI</strong> é calculado multiplicando a frequência de
                cada spot de erro pelo custo médio em EV de uma decisão incorreta naquele spot. Spots com
                frequência alta e custo individual baixo podem superar spots raros com custo alto — o ROI
                captura isso.
              </p>
            </Section>

            {/* ── 3. Fases de M-Ratio ──────────────────────────────────── */}
            <Section id="mstacks" title="Fases de M-Ratio">
              <p>
                O <strong className="text-foreground">M de Harrington</strong> mede quantas órbitas completas
                de blinds (SB + BB + antes) seu stack aguenta sem jogar uma mão. Governa a estratégia MTT:
                quanto menor o M, menor o leque de ações viáveis.
              </p>
              <Table
                headers={["Fase", "M-Ratio", "Estratégia implícita"]}
                rows={[
                  ["Deep Stack",  "> 20",    "Poker pós-flop completo. Espaço para bluffs, slowplays e manobras de stack."],
                  ["Mid Stack",   "10 – 20", "Jogabilidade pré-flop começa a reduzir. Cuidado com confrontos de grandes stacks."],
                  ["Short Stack", "6 – 10",  "Foco em spots de reshove/push-fold. Resteals importantes para manter M."],
                  ["Push/Fold",   "≤ 6",     "Estratégia binária: fold ou all-in. ICM pressure automaticamente alto."],
                ]}
              />
              <p>
                Decisões tomadas em fase Push/Fold são avaliadas com critérios diferentes das demais fases.
                O sistema aplica tabelas de push/fold baseadas em equity mínima e posição para calcular o
                score correto nesse contexto.
              </p>
              <p>
                O estágio do torneio (<em>early, middle, late, final_table, heads_up</em>) é detectado
                pelo número de jogadores ativos na mesa e complementa o M na definição do contexto.
              </p>
            </Section>

            {/* ── 4. Decision DNA ──────────────────────────────────────── */}
            <Section id="dna" title="Decision DNA">
              <p>
                O <strong className="text-foreground">Decision DNA</strong> é a assinatura estratégica do jogador —
                um radar de 5 eixos calculados sobre o histórico completo de decisões. Revela padrões
                estruturais de jogo independente de resultados financeiros.
              </p>
              <Table
                headers={["Eixo", "Cálculo", "Referência saudável"]}
                rows={[
                  ["Aggression Index",    "% de ações agressivas (bet/raise) sobre o total pós-flop",          "30–50% — abaixo indica passividade excessiva"],
                  ["Fold Frequency",      "% de decisões que resultaram em fold",                               "28–55% — extremos indicam problema estrutural"],
                  ["3-Bet%",             "% de situações pré-flop onde houve 3-bet sobre oportunidades",       "Varia por posição; > 12% em EP pode ser exploitável"],
                  ["Positional Awareness","Diferença de aggression entre late position e early position",       "Positivo = mais agressivo em posição (correto)"],
                  ["Discipline",         "% de decisões classificadas como standard (= Standard%)",             "> 70% é sólido; > 86% é elite"],
                ]}
              />
              <p>
                A combinação dos eixos gera um <strong className="text-foreground">arquétipo</strong>: Nit,
                Passive Calling Station, LAG, TAG, Disciplined TAGfish, Aggressive Reg, ou Balanced Reg.
                O arquétipo é um ponto de partida diagnóstico — não uma classificação definitiva.
              </p>
            </Section>

            {/* ── 5. Ghost Table ───────────────────────────────────────── */}
            <Section id="ghost" title="Ghost Table / Drills">
              <p>
                O <strong className="text-foreground">Ghost Table</strong> converte seus próprios leaks em drills
                de revisão. Cada "spot" é um padrão recorrente onde você tomou decisões abaixo do ideal —
                o sistema extrai esses spots automaticamente do histórico importado.
              </p>
              <p>
                <strong className="text-foreground">Como funciona o SRS adaptativo:</strong> após cada sessão
                de drill, o intervalo até a próxima revisão é ajustado com base na performance:
              </p>
              <Table
                headers={["Resultado", "Próxima revisão"]}
                rows={[
                  ["Acerto",    "Intervalo dobra: 3d → 7d → 14d → 28d → 60d"],
                  ["Erro",      "Intervalo reseta para 3 dias"],
                  ["Mastery",   "Spot arquivado — intervalo máximo de 60 dias"],
                ]}
              />
              <p>
                O card <em>GhostDrillCard</em> no dashboard mostra os spots com revisão vencida (vermelho),
                próximos de vencer (amarelo) e em dia (verde). O objetivo é manter todos os spots no verde —
                sinal de que os padrões foram internalizados.
              </p>
              <p>
                XP ganho: <strong className="text-foreground">25 XP</strong> por drill completo,
                <strong className="text-foreground"> 100 XP</strong> ao atingir mastery em um spot.
              </p>
            </Section>

            {/* ── 6. Comparativo de Torneios ───────────────────────────── */}
            <Section id="compare" title="Comparativo de Torneios">
              <p>
                Selecione 2 a 4 torneios na página de Torneios e clique em "Comparar" para ver uma análise
                lado a lado. O comparativo exibe:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li><strong className="text-foreground">Standard%</strong> e <strong className="text-foreground">Avg Score</strong> de cada torneio</li>
                <li>Top 3 leaks ativos em cada sessão com frequência e EV loss</li>
                <li>Breakdown por fase (early/middle/late/final table)</li>
                <li>Delta de ICM collapse entre torneios</li>
                <li>Narrativa gerada por IA destacando evolução ou regressão técnica</li>
              </ul>
              <p>
                O <strong className="text-foreground">Delta</strong> (▲/▼) indica a variação do indicador
                entre o torneio de referência (mais antigo selecionado) e os demais. Verde significa melhora,
                vermelho indica piora no mesmo spot.
              </p>
            </Section>

            {/* ── 7. Coaching ──────────────────────────────────────────── */}
            <Section id="coaching" title="Coaching">
              <p>
                Quando um coach é vinculado à sua conta, o sistema cria automaticamente um
                <strong className="text-foreground"> baseline</strong> — um snapshot dos seus indicadores
                no momento do vínculo. Todos os torneios importados a partir dali são comparados
                contra esse baseline para medir evolução real.
              </p>
              <Table
                headers={["Termo", "Significado"]}
                rows={[
                  ["Baseline",        "Média de Standard%, Avg Score e top leaks na data de início do coaching"],
                  ["Baseline Delta",  "Variação dos indicadores desde o baseline — principal métrica de progresso"],
                  ["Coach Reviewed",  "O coach anotou ou comentou pelo menos uma decisão da sessão"],
                  ["Override de Plano", "O coach substituiu o plano de estudos gerado por IA por um customizado"],
                  ["Coach Effectiveness", "Melhora mediana de Standard% dos alunos nos primeiros 60 dias de coaching"],
                ]}
              />
              <p>
                A <strong className="text-foreground">efetividade do coach</strong> é calculada comparando
                o Standard% médio de cada aluno nos 30 dias antes do vínculo com os 30 dias após o baseline.
                Coaches com ≥ 3 alunos com baseline recebem um badge público verificado no diretório.
              </p>
            </Section>

            {/* ── 8. Gamificação ───────────────────────────────────────── */}
            <Section id="gamification" title="Gamificação">
              <p>
                O sistema de XP recompensa atividade de estudo, não resultados financeiros. XP é persistido
                no servidor e sincronizado entre dispositivos.
              </p>
              <Table
                headers={["Evento", "XP"]}
                rows={[
                  ["Importar e analisar um torneio", "50 XP"],
                  ["Completar um exercício corretamente", "10 XP"],
                  ["Completar um drill no Ghost Table", "25 XP"],
                  ["Atingir mastery em um spot", "100 XP"],
                ]}
              />
              <p className="mt-2"><strong className="text-foreground">Nível</strong> é calculado com base no Standard% médio dos últimos torneios (mínimo 5):</p>
              <Table
                headers={["Nível", "Standard% necessário"]}
                rows={[
                  ["🎯 Iniciante",  "< 60%"],
                  ["📖 Estudante",  "60% – 70%"],
                  ["⚙️ Grinder",    "70% – 77%"],
                  ["📈 Regular",    "77% – 86%"],
                  ["🔷 Sólido",     "86% – 92%"],
                  ["♠ Expert",     "92% – 96%"],
                  ["👑 Elite",      "≥ 96%"],
                ]}
              />
              <p>
                <strong className="text-foreground">Streak</strong> é o número de dias consecutivos com
                atividade registrada (qualquer evento que gere XP). Reinicia se houver um dia sem atividade.
              </p>
              <p>
                <strong className="text-foreground">Conquistas:</strong>
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>🎯 Primeira Análise — importar e analisar o primeiro torneio</li>
                <li>📊 100 Decisões — acumular 100 decisões analisadas</li>
                <li>🎮 Primeiro Drill — completar o primeiro drill no Ghost Table</li>
                <li>🔥 Semana de Foco — 7 dias consecutivos de streak</li>
                <li>🏆 10 Torneios — importar e analisar 10 torneios</li>
              </ul>
            </Section>

          </div>
        </div>
      </div>
    </HudLayout>
  );
}
