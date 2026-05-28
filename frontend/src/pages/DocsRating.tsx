import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";

/**
 * /docs/rating — explica a teoria ELO e como adaptamos pro LeakLab.
 */
export default function DocsRating() {
  return (
    <HudLayout
      eyebrow="Documentação"
      title="Sistema de Rating ELO"
      description="Como o ELO funciona, como adaptamos para poker, e como ler seu rating."
    >
      <div className="max-w-3xl space-y-8 text-sm text-muted-foreground leading-relaxed">

        <Link to="/rating" className="inline-flex items-center gap-1.5 font-mono text-xs text-primary hover:underline">
          <ArrowLeft className="size-3.5" /> Voltar pro meu rating
        </Link>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">
            1. O que é ELO
          </h2>
          <p>
            ELO é um sistema de rating criado pelo físico húngaro <strong>Árpád Élő</strong> nos
            anos 1960 para classificar jogadores de xadrez. Hoje é usado em xadrez (FIDE),
            tênis, futebol (FIFA), e muitos games competitivos.
          </p>
          <p>
            A ideia central: cada jogador tem um número (rating). Quando dois jogadores se
            enfrentam, o sistema calcula a <strong>probabilidade esperada</strong> de cada
            um ganhar com base na diferença de rating. Após a partida, o vencedor ganha
            pontos e o perdedor perde — quanto mais surpreendente o resultado, mais pontos
            mudam de mão.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">
            2. Como o rating se move
          </h2>
          <p>
            A cada decisão analisada, seu rating sobe ou desce um pouco. O tamanho do
            ajuste depende de quão <strong>surpreendente</strong> foi o resultado em
            relação ao que se esperava de alguém no seu nível: jogar bem quando já se
            espera que você jogue bem move pouco; um erro grave — ou um acerto acima do
            seu nível — move mais.
          </p>
          <p>
            Como em qualquer ELO, a distância entre dois níveis tem peso: uma diferença
            de <strong>400 pontos</strong> equivale a cerca de <strong>10× mais
            chance</strong> de o lado mais forte levar o confronto. É por isso que o
            rating não dispara nem despenca de um torneio para o outro.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">
            3. Adaptação para poker
          </h2>
          <p>
            Poker não tem um adversário direto cuja qualidade dê pra medir em cada partida.
            Adotamos uma abordagem <strong>vs Solver GTO</strong>: cada decisão sua é
            comparada com a solução do solver. O rating de referência ("par") da
            plataforma é <strong>1500</strong> — o jogador médio. Aderência alta ao GTO
            empurra seu rating acima do par; erros graves empurram abaixo.
          </p>
          <p className="rounded-md bg-emerald-500/10 border border-emerald-500/30 p-3 text-emerald-300/90 text-xs">
            <strong>Importante:</strong> o ELO considera <strong>apenas decisões com
            análise de solver GTO</strong>. Spots sem cobertura GTO (ainda não resolvidos)
            são ignorados — não inflam nem deflacionam seu rating. Isso garante que o
            número reflete aderência real ao equilíbrio, não estimativa heurística.
          </p>
          <p>
            O quanto cada decisão pesa no rating depende do alinhamento dela com o GTO:
          </p>
          <div className="rounded-lg border border-border/40 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-card/60">
                <tr>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">Classificação</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">Significado</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-emerald-400">Correta</td>
                  <td className="px-3 py-2">Jogou exatamente como o GTO indica</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-sky-400">Mista</td>
                  <td className="px-3 py-2">Jogou uma das ações que o solver mistura naquele spot</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-amber-400">Desvio pequeno</td>
                  <td className="px-3 py-2">Saiu um pouco do ideal, mas longe de um erro grave</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-red-400">Desvio grave</td>
                  <td className="px-3 py-2">Erro claro, que mais custa no rating</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">
            4. Por que o rating se estabiliza
          </h2>
          <p>
            Conforme seu rating sobe, passa a se esperar mais de você — então acertos
            "óbvios" valem cada vez menos e os erros pesam mais. É esse mecanismo que
            estabiliza o número: subir de uma banda para a próxima exige aderência
            consistentemente mais alta ao GTO, não apenas acertar o fácil.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">
            5. Bandas de rating
          </h2>
          <div className="rounded-lg border border-border/40 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-card/60">
                <tr>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">Banda</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">Range</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">Perfil</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">🎯 Iniciante</td>
                  <td className="px-3 py-2 font-mono">&lt; 1570</td>
                  <td className="px-3 py-2">Aderência GTO &lt; 60% — começando a estudar</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">📖 Estudante</td>
                  <td className="px-3 py-2 font-mono">1570 – 1646</td>
                  <td className="px-3 py-2">~60–70% — fundamentos em construção</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">⚙️ Grinder</td>
                  <td className="px-3 py-2 font-mono">1647 – 1709</td>
                  <td className="px-3 py-2">~70–77% — joga volume com consistência</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">📈 Regular</td>
                  <td className="px-3 py-2 font-mono">1710 – 1815</td>
                  <td className="px-3 py-2">~77–86% — decisões sólidas na maioria dos spots</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">🔷 Sólido</td>
                  <td className="px-3 py-2 font-mono">1816 – 1923</td>
                  <td className="px-3 py-2">~86–92% — reg-level, raros erros graves</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">♠ Expert</td>
                  <td className="px-3 py-2 font-mono">1924 – 2052</td>
                  <td className="px-3 py-2">~92–96% — domínio de spots complexos</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">👑 Elite</td>
                  <td className="px-3 py-2 font-mono">≥ 2053</td>
                  <td className="px-3 py-2">≥ 96% — aderência GTO de high-stakes</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">
            6. Notas importantes
          </h2>
          <ul className="list-disc list-inside space-y-2">
            <li>
              <strong>Volatilidade adaptativa</strong>: o rating é mais sensível no
              início, para calibrar rápido, e vai estabilizando conforme você acumula
              decisões — assim erros isolados não destroem um rating já consolidado.
            </li>
            <li>
              <strong>Rating por street</strong>: além do agregado, mantemos ratings
              separados pra preflop / flop / turn / river. Útil pra identificar suas
              forças e fraquezas (ex: ELO 2300 preflop mas 1700 turn = oportunidade de estudo).
            </li>
            <li>
              <strong>Recalculado a cada upload</strong>: depois de cada novo torneio
              importado, seu ELO é recalculado e um novo ponto é gravado no gráfico de
              evolução.
            </li>
            <li>
              <strong>Sem ranking público</strong>: por enquanto seu ELO é privado. Quando
              o leaderboard for liberado (feature opt-in), você decide se aparece.
            </li>
          </ul>
        </section>

        <Link to="/rating" className="inline-flex items-center gap-1.5 font-mono text-xs text-primary hover:underline">
          <ArrowLeft className="size-3.5" /> Voltar pro meu rating
        </Link>
      </div>
    </HudLayout>
  );
}
