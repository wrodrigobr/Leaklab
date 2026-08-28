/**
 * Vitrine da landing — blocos que MOSTRAM o produto, em vez de descrevê-lo.
 *
 * ── O que o benchmark mostrou (27/08) ─────────────────────────────────────────────────────
 *
 * A landing do concorrente tem seis blocos de feature, cada um com um print real dentro de uma
 * moldura de navegador, um título em linguagem de jogador e exatamente dois bullets. A moldura é
 * o truque: ela afirma "isto é o produto", não "isto é uma ilustração". A nossa tinha 8 seções e
 * duas imagens no arquivo inteiro — nós descrevíamos, eles mostravam.
 *
 * ── A decisão sobre o conteúdo da moldura ─────────────────────────────────────────────────
 *
 * O primeiro bloco não usa imagem: ele renderiza o `RangeGrid` DE VERDADE, com um recorte real da
 * nossa carta (20bb, CO, abertura). O visitante vê o componente do produto com dado do produto, e
 * isso não pode envelhecer — um print raster mente calado no dia em que a carta muda.
 *
 * Os demais blocos esperam um print em `/landing/*.webp`. Enquanto o arquivo não existe, o bloco
 * mostra um aviso visível em vez de um espaço em branco: slot vazio que parece proposital é como
 * uma medição que devolve zero sem ter olhado nada.
 */
import { useState } from "react";
import { Check } from "lucide-react";
import { RangeGrid } from "@/components/replayer/RangeGrid";
import { VITRINE_RANGE } from "@/data/vitrineRange";
import { cn } from "@/lib/utils";

/** Moldura de navegador. O rótulo é o caminho da tela, e ele importa: diz que aquilo existe. */
function Moldura({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface shadow-elevated">
      <div className="flex items-center gap-2 border-b border-border bg-background/60 px-3 py-2">
        <span className="block size-2 rounded-full bg-border" />
        <span className="block size-2 rounded-full bg-border" />
        <span className="block size-2 rounded-full bg-border" />
        <span className="ml-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {rotulo}
        </span>
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

/**
 * Print do produto.
 *
 * ── O aviso que eu construí para mim e foi para o ar (28/08) ──────────────────────────────
 *
 * A primeira versão renderizava, no `onError`, uma caixa tracejada dizendo "captura pendente"
 * com o caminho do arquivo em fonte mono. Era um lembrete para EU não esquecer de capturar.
 *
 * Ele foi para produção. O `main-*.js` publicado em grindlabpoker.com continha literalmente
 * "captura pendente" e "/landing/veredito.webp", e três dos quatro blocos da seção "O produto"
 * mostravam isso para o visitante. A seção anunciava as telas do produto e entregava avisos de
 * arquivo faltando.
 *
 * Agora a falha ESCONDE o bloco: melhor mostrar menos produto do que mostrar obra inacabada.
 * Mas isso é a rede de segurança, não o conserto. O conserto é
 * `landingCapturasExistem.test.ts`, que quebra a build quando um caminho de `print` não existe
 * no `public/` — sem ele, um arquivo faltando volta a virar um bloco que some calado, que é
 * mais difícil de notar do que a caixa tracejada.
 */
function Print({ src, alt, onFalhar }: { src: string; alt: string; onFalhar: () => void }) {
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={onFalhar}
      className="w-full rounded-md"
    />
  );
}

export interface BlocoVitrine {
  rotulo: string;
  titulo: string;
  texto: string;
  bullets: [string, string];
  /** quando ausente, o bloco renderiza o componente vivo */
  print?: string;
}

function Bloco({ b, invertido }: { b: BlocoVitrine; invertido: boolean }) {
  const [semCaptura, setSemCaptura] = useState(false);
  // Sem a imagem, o bloco inteiro sai. O texto sozinho ao lado de uma moldura vazia leria como
  // tela quebrada, e a moldura é o que dá a ele o sentido de "isto existe".
  if (b.print && semCaptura) return null;
  return (
    <div className="grid items-center gap-8 md:grid-cols-2">
      <div className={cn(invertido && "md:order-2")}>
        <h3 className="font-heading text-xl font-bold tracking-tight text-foreground md:text-2xl">
          {b.titulo}
        </h3>
        <p className="mt-3 text-sm leading-relaxed text-prose-fg">{b.texto}</p>
        <ul className="mt-4 space-y-2">
          {b.bullets.map((x) => (
            <li key={x} className="flex items-start gap-2 text-sm text-foreground">
              <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <span>{x}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className={cn(invertido && "md:order-1")}>
        <Moldura rotulo={b.rotulo}>
          {b.print ? (
            <Print src={b.print} alt={b.titulo} onFalhar={() => setSemCaptura(true)} />
          ) : (
            // O componente do produto, com dado do produto. Não é maquete.
            <RangeGrid range={VITRINE_RANGE} />
          )}
        </Moldura>
      </div>
    </div>
  );
}

export function Vitrine({ eyebrow, heading, blocos }: {
  eyebrow: string; heading: string; blocos: BlocoVitrine[];
}) {
  return (
    <section className="border-t border-border px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 text-center">
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {eyebrow}
          </span>
          <h2 className="mt-2 font-heading text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            {heading}
          </h2>
        </div>
        <div className="space-y-20">
          {blocos.map((b, i) => (
            <Bloco key={b.titulo} b={b} invertido={i % 2 === 1} />
          ))}
        </div>
      </div>
    </section>
  );
}
