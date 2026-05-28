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
            2. A fórmula
          </h2>
          <pre className="rounded-md bg-card/60 border border-border/40 p-3 font-mono text-xs text-foreground overflow-x-auto">
{`R' = R + K × (S − E)

R  = rating atual
R' = novo rating após a partida
S  = resultado real      (1 vitória, 0.5 empate, 0 derrota)
E  = resultado esperado  = 1 / (1 + 10^((R_opp − R) / 400))
K  = fator de volatilidade (32 iniciante, 16 médio, 8 experiente)`}
          </pre>
          <p>
            Diferença de <strong>400 pontos</strong> significa que o mais forte é esperado
            ganhar <strong>10× mais</strong> que o mais fraco (E ≈ 0.91 vs E ≈ 0.09).
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
            Seu resultado <strong>S</strong> em cada decisão depende do alinhamento com o GTO:
          </p>
          <div className="rounded-lg border border-border/40 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-card/60">
                <tr>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">Classificação</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">S (score)</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">Significado</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-emerald-400 font-mono">gto_correct</td>
                  <td className="px-3 py-2 font-mono">1.0</td>
                  <td className="px-3 py-2">Jogou exatamente como GTO indica — vitória total</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-sky-400 font-mono">gto_mixed</td>
                  <td className="px-3 py-2 font-mono">0.7</td>
                  <td className="px-3 py-2">Jogou uma das ações mistas do solver</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-amber-400 font-mono">gto_minor_deviation</td>
                  <td className="px-3 py-2 font-mono">0.4</td>
                  <td className="px-3 py-2">Desvio pequeno; quase empate</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 text-red-400 font-mono">gto_critical</td>
                  <td className="px-3 py-2 font-mono">0.0</td>
                  <td className="px-3 py-2">Desvio grave; perdeu a partida</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">
            4. Exemplo de cálculo
          </h2>
          <p>
            Player no par (<strong>ELO 1500</strong>), decisão classificada como
            <code> gto_correct</code> (S = 1.0), K-factor = 32 (iniciante):
          </p>
          <pre className="rounded-md bg-card/60 border border-border/40 p-3 font-mono text-xs text-foreground">
{`E = 1 / (1 + 10^((1500 − 1500) / 400))
  = 1 / (1 + 1)
  = 0.5            ← partida equilibrada (você está no par)

R' = 1500 + 32 × (1.0 − 0.5)
   = 1500 + 16
   = 1516           ← acertou: +16 ELO`}
          </pre>
          <p>
            Mesmo player joga um <code>gto_critical</code> (S = 0):
          </p>
          <pre className="rounded-md bg-card/60 border border-border/40 p-3 font-mono text-xs text-foreground">
{`R' = 1500 + 32 × (0 − 0.5)
   = 1500 − 16
   = 1484           ← erro grave: −16 ELO`}
          </pre>
          <p>
            Conforme seu rating sobe acima do par, o <strong>E</strong> (resultado esperado)
            aumenta — então acertos passam a valer menos e erros a custar mais. É isso que
            estabiliza o rating: pra subir de 1800 pra 2000 você precisa de aderência
            consistentemente mais alta, não só "acertar o óbvio".
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
                  <td className="px-3 py-2 font-mono">Iniciante</td>
                  <td className="px-3 py-2 font-mono">&lt; 1200</td>
                  <td className="px-3 py-2">Começando a estudar poker</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">Casual</td>
                  <td className="px-3 py-2 font-mono">1200 – 1499</td>
                  <td className="px-3 py-2">Joga regularmente, ainda não estuda GTO</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">Em desenvolvimento</td>
                  <td className="px-3 py-2 font-mono">1500 – 1799</td>
                  <td className="px-3 py-2">Acerta preflop básico, postflop em construção</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">Sólido</td>
                  <td className="px-3 py-2 font-mono">1800 – 2099</td>
                  <td className="px-3 py-2">Joga reg-level, decisões consistentes</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">Avançado</td>
                  <td className="px-3 py-2 font-mono">2100 – 2399</td>
                  <td className="px-3 py-2">Dominio de spots complexos, raros erros graves</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">Elite</td>
                  <td className="px-3 py-2 font-mono">2400 – 2699</td>
                  <td className="px-3 py-2">Nível de high-stakes; aderência GTO alta</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">Master</td>
                  <td className="px-3 py-2 font-mono">2700 – 2999</td>
                  <td className="px-3 py-2">Indistinguível de pro player em maioria dos spots</td>
                </tr>
                <tr className="border-t border-border/30">
                  <td className="px-3 py-2 font-mono">Grandmaster</td>
                  <td className="px-3 py-2 font-mono">3000+</td>
                  <td className="px-3 py-2">Iguala ou supera o solver em consistência</td>
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
              <strong>K-factor dinâmico</strong>: 32 (até 100 decisões), 16 (100-1000), 8
              (acima de 1000). Volatilidade alta no início pra calibrar rápido; baixa depois
              pra que erros isolados não destruam o rating.
            </li>
            <li>
              <strong>Rating por street</strong>: além do agregado, mantemos ratings
              separados pra preflop / flop / turn / river. Útil pra identificar suas
              forças e fraquezas (ex: ELO 2300 preflop mas 1700 turn = oportunidade de estudo).
            </li>
            <li>
              <strong>Recalculado a cada upload</strong>: depois de cada novo torneio
              importado, recomputamos seu ELO processando todas as decisões em ordem
              cronológica. O snapshot é gravado pro gráfico de evolução.
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
