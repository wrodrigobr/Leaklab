import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * Política de Privacidade (RASCUNHO, orientada à LGPD). Página pública (logada ou não).
 * Os trechos [entre colchetes] precisam ser preenchidos/validados pelo responsável jurídico
 * antes de publicar (razão social, CNPJ, encarregado/DPO, endereço). O texto é um ponto de
 * partida, não aconselhamento jurídico.
 */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="font-heading text-lg font-bold text-foreground">{title}</h2>
      <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export default function Privacy() {
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
          <h1 className="font-heading text-2xl font-bold text-foreground">Política de Privacidade</h1>
          <p className="mt-2 text-xs text-muted-foreground">
            Rascunho para revisão. Última atualização: [data]. Em caso de dúvida sobre seus dados,
            fale com a gente pelo contato abaixo.
          </p>
        </div>

        <Section title="1. Quem somos">
          <p>
            O GrindLab (&quot;nós&quot;) é uma plataforma de análise e estudo de mãos de poker.
            O controlador dos dados é [razão social / CNPJ], com contato em [email de privacidade].
            Perguntas sobre esta política ou sobre seus dados podem ser enviadas a esse endereço.
          </p>
        </Section>

        <Section title="2. Dados que coletamos">
          <p>Coletamos apenas o necessário para o serviço funcionar:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li><strong>Cadastro:</strong> nome de usuário, email e senha (armazenada de forma cifrada).</li>
            <li><strong>Conteúdo que você envia:</strong> os arquivos de hand history e de resultados dos seus torneios, e a análise gerada a partir deles.</li>
            <li><strong>Uso da plataforma:</strong> páginas visitadas, ações e métricas de desempenho, para melhorar o produto.</li>
            <li><strong>Cookies de análise e publicidade:</strong> quando você aceita, usamos Google Analytics e Google Ads para medir acessos e a eficácia de campanhas.</li>
            <li><strong>Pagamento:</strong> processado pela Stripe. Não armazenamos os dados do seu cartão.</li>
          </ul>
        </Section>

        <Section title="3. Como usamos os dados">
          <ul className="list-disc space-y-1 pl-5">
            <li>Fornecer a análise das suas mãos e as funcionalidades da plataforma.</li>
            <li>Melhorar o produto e a experiência.</li>
            <li>Medir a aquisição e a eficácia de anúncios (apenas com o seu consentimento de cookies).</li>
            <li>Segurança, prevenção a fraude e cumprimento de obrigações legais.</li>
          </ul>
        </Section>

        <Section title="4. Base legal (LGPD)">
          <p>Tratamos seus dados com base em:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li><strong>Execução de contrato:</strong> para fornecer o serviço que você contratou.</li>
            <li><strong>Consentimento:</strong> para cookies de análise e publicidade, que você pode aceitar ou recusar a qualquer momento.</li>
            <li><strong>Legítimo interesse:</strong> para melhorar o produto e garantir a segurança, sempre respeitando os seus direitos.</li>
          </ul>
        </Section>

        <Section title="5. Cookies, análise e publicidade">
          <p>
            Usamos cookies estritamente necessários (para manter você conectado) e, mediante
            consentimento, cookies de análise e publicidade (Google Analytics e Google Ads). Enquanto
            você não aceita, esses cookies de marketing não são gravados (Consent Mode). Você pode
            mudar sua escolha limpando os cookies do site ou pelo aviso de cookies.
          </p>
        </Section>

        <Section title="6. Com quem compartilhamos">
          <p>
            Não vendemos seus dados. Compartilhamos apenas com prestadores que viabilizam o serviço,
            no limite necessário: pagamento (Stripe), análise e anúncios (Google), hospedagem
            (Cloudflare, [provedor de servidor]), envio de email ([provedor de email]) e monitoramento
            de erros (Sentry). Alguns desses provedores processam dados fora do Brasil.
          </p>
        </Section>

        <Section title="7. Transferência internacional">
          <p>
            Por usarmos provedores globais (como Google e Cloudflare), seus dados podem ser
            processados fora do Brasil. Adotamos provedores que oferecem garantias adequadas de
            proteção, conforme a LGPD.
          </p>
        </Section>

        <Section title="8. Retenção">
          <p>
            Mantemos seus dados enquanto a sua conta existir e pelo prazo necessário para cumprir
            obrigações legais. Você pode solicitar a exclusão a qualquer momento (ver seus direitos).
          </p>
        </Section>

        <Section title="9. Seus direitos">
          <p>Como titular, você pode, a qualquer momento:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>confirmar a existência de tratamento e acessar seus dados;</li>
            <li>corrigir dados incompletos ou desatualizados;</li>
            <li>solicitar a exclusão dos seus dados;</li>
            <li>solicitar a portabilidade;</li>
            <li>revogar o consentimento de cookies de marketing.</li>
          </ul>
          <p>Para exercer, escreva para [email de privacidade].</p>
        </Section>

        <Section title="10. Segurança">
          <p>
            Adotamos medidas técnicas para proteger seus dados, como transporte cifrado (HTTPS) e
            senhas armazenadas de forma cifrada. Nenhum sistema é 100% infalível, mas trabalhamos para
            reduzir riscos.
          </p>
        </Section>

        <Section title="11. Menores de idade">
          <p>
            A plataforma é destinada a maiores de 18 anos e não é direcionada a menores.
          </p>
        </Section>

        <Section title="12. Alterações e contato">
          <p>
            Podemos atualizar esta política. Mudanças relevantes serão comunicadas na plataforma.
            Dúvidas ou solicitações: [email de privacidade].
          </p>
        </Section>
      </main>
    </div>
  );
}
