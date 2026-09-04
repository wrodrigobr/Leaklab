import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * Termos de Uso — deliberadamente SIMPLES (30/08, direção do dono): é um SaaS, o usuário paga
 * pelo período de acesso, sem outros compromissos; se não cancelar, renova. Mesma exceção de
 * idioma da Privacidade (pt-BR, declarada). Ponto de partida honesto, não aconselhamento
 * jurídico — revisar com advogado antes de escalar.
 */
const CONTACT_EMAIL = "suporte@grindlabpoker.com";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="font-heading text-lg font-bold text-foreground">{title}</h2>
      <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export default function Termos() {
  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link to="/"><img src={logoHorizontal} alt="GrindLab" className="h-6" /></Link>
          <Link to="/" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
            <ArrowLeft className="size-3.5" /> Voltar
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-8 px-6 py-10">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Termos de Uso</h1>
          <p className="mt-2 text-xs text-muted-foreground">
            Versão vigente. Ao criar conta ou assinar, você concorda com estes termos. Eles podem
            ser atualizados; mudanças relevantes serão avisadas na plataforma.
          </p>
        </div>

        <Section title="1. O que é o GrindLab">
          <p>
            O GrindLab Poker é uma plataforma de estudo e treino de poker: você envia seus
            históricos de mãos, e a plataforma analisa decisões, aponta leaks e oferece treinos
            baseados em ranges e soluções de GTO Solver, com explicações auxiliadas por
            inteligência artificial.
          </p>
          <p>
            O GrindLab é ferramenta <strong className="text-foreground">educativa</strong>. Não é
            site de apostas, não intermedeia jogo a dinheiro, não garante resultados financeiros e
            nada aqui é aconselhamento financeiro. Poker envolve variância: estudar melhora
            decisões, não garante ganhos.
          </p>
        </Section>

        <Section title="2. Sua conta">
          <p>
            Você precisa ter 18 anos ou mais. A conta é pessoal e intransferível: mantenha suas
            credenciais em sigilo e não compartilhe o acesso. Informações falsas ou uso abusivo
            (raspagem de dados, sobrecarga proposital, burla de limites) podem levar à suspensão.
          </p>
          <p>
            Ao usar as áreas de comunidade (mãos compartilhadas, comentários), você autoriza a
            exibição do conteúdo que publicar, e pode removê-lo ou publicar anonimamente. Nicks de
            poker de terceiros não são exibidos pela plataforma.
          </p>
        </Section>

        <Section title="3. Planos, cobrança e renovação">
          <p>
            O plano <strong className="text-foreground">Free</strong> dá acesso às funcionalidades
            básicas, com limites. O plano <strong className="text-foreground">Pro</strong> é uma
            assinatura paga que libera as funcionalidades avançadas pelo período contratado:
            <strong className="text-foreground"> 30 dias</strong> (mensal) ou
            <strong className="text-foreground"> 12 meses</strong> (anual), pelos preços exibidos
            na tela de assinatura no momento da compra.
          </p>
          <p>
            <strong className="text-foreground">Renovação automática:</strong> ao fim de cada
            período, a assinatura renova e o valor vigente é cobrado no mesmo meio de pagamento,
            até que você cancele. Não há fidelidade, multa ou qualquer outro compromisso além do
            período já pago.
          </p>
          <p>
            Os pagamentos são processados pela Stripe. O GrindLab não armazena os dados completos
            do seu cartão.
          </p>
        </Section>

        <Section title="4. Cancelamento e reembolso">
          <p>
            Você pode cancelar a qualquer momento na tela de assinatura. O cancelamento
            interrompe as próximas cobranças e o acesso Pro permanece ativo até o fim do período
            já pago, sem multa e sem burocracia.
          </p>
          <p>
            Na primeira contratação, você pode se arrepender em até 7 dias corridos (art. 49 do
            CDC) e receber reembolso integral: basta pedir pelo suporte. Após esse prazo, e nas
            renovações, não há reembolso proporcional do período em curso: o acesso segue até o
            fim do ciclo pago.
          </p>
        </Section>

        <Section title="5. Uso responsável">
          <p>
            As salas de poker têm regras próprias sobre ferramentas de auxílio em tempo real.
            É sua responsabilidade conhecer e respeitar as regras da sala onde joga. O GrindLab é
            desenhado para estudo fora da mesa.
          </p>
        </Section>

        <Section title="6. Disponibilidade e conteúdo">
          <p>
            Trabalhamos para manter a plataforma no ar e os vereditos precisos, mas o serviço é
            fornecido "como está", sem garantia de disponibilidade ininterrupta. Análises, ranges
            e explicações são material de estudo e podem ser atualizados conforme o motor evolui.
          </p>
          <p>
            A plataforma, sua marca e seu conteúdo (exceto o que você envia) são propriedade do
            GrindLab e não podem ser copiados ou revendidos.
          </p>
        </Section>

        <Section title="7. Encerramento e exclusão de dados">
          <p>
            Você pode parar de usar a qualquer momento. Para excluir sua conta e todos os dados
            associados (históricos, análises, treinos), solicite pelo suporte. A exclusão é
            completa e definitiva. Detalhes sobre tratamento de dados estão na{" "}
            <Link to="/privacidade" className="text-primary hover:underline">Política de Privacidade</Link>.
          </p>
        </Section>

        <Section title="8. Lei aplicável e contato">
          <p>
            Estes termos seguem a lei brasileira, e fica assegurado o foro do seu domicílio para
            questões de consumo. Dúvidas: {" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary hover:underline">{CONTACT_EMAIL}</a>{" "}
            ou o canal de suporte dentro da plataforma.
          </p>
        </Section>
      </main>
    </div>
  );
}
