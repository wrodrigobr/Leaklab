import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Uma janela REAL, sempre por cima, fora do navegador — para consultar range enquanto se joga.
 *
 * ── Por que existe (28/08) ────────────────────────────────────────────────────────────────
 *
 * Do benchmark do concorrente, é a única função dos dois produtos que serve **durante** a mão. O
 * nosso é inteiro pós-sessão: o jogador importa, olha o diagnóstico e treina — sempre depois. Uma
 * tabela que fica por cima da mesa muda a categoria da ferramenta.
 *
 * Eles resolvem com aplicativo desktop. `documentPictureInPicture` faz o mesmo a partir da página,
 * e foi confirmado ao vivo antes de eu escrever uma linha: a API existe, abre, e devolve um
 * `Document` de verdade.
 *
 * ── A armadilha que a medição pegou ───────────────────────────────────────────────────────
 *
 * **A janela NÃO herda o CSS da página.** Medido: `w.document.styleSheets.length === 0` numa
 * janela recém-aberta. Sem copiar os estilos, a grade abre sem formatação nenhuma — e isso não
 * gera erro, não quebra teste, e só aparece para quem olha. Copiar as folhas é metade do trabalho
 * deste arquivo, e não um detalhe.
 *
 * ── Onde ela NÃO aparece, e por quê ───────────────────────────────────────────────────────
 *
 * Firefox e Safari não têm a API. O botão só existe onde `documentPictureInPicture` existe:
 * oferecer e falhar é pior que não oferecer, porque o jogador conclui que o produto está quebrado.
 */

/** Copia as folhas de estilo da página para a janela nova.
 *
 *  Duas formas, porque as duas aparecem: em produção o Vite emite `<link rel="stylesheet">`, e no
 *  dev ele injeta `<style>`. Copiar só uma delas funciona num ambiente e falha no outro — o tipo
 *  de defeito que passa a revisão inteira porque quem revisa está no dev. */
function copiarEstilos(destino: Document) {
  for (const folha of Array.from(document.styleSheets)) {
    try {
      const regras = Array.from(folha.cssRules).map((r) => r.cssText).join("\n");
      const tag = destino.createElement("style");
      tag.textContent = regras;
      destino.head.appendChild(tag);
    } catch {
      // Folha de outra origem: as regras não são legíveis, então copia-se o <link>.
      const href = (folha as CSSStyleSheet).href;
      if (!href) continue;
      const link = destino.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      destino.head.appendChild(link);
    }
  }
  // O tema vive num atributo no <html>: sem ele a janela abre no claro enquanto o app está no
  // escuro, e a grade fica ilegível.
  destino.documentElement.className = document.documentElement.className;
  const tema = document.documentElement.getAttribute("data-theme");
  if (tema) destino.documentElement.setAttribute("data-theme", tema);
  destino.body.className = document.body.className;
}

export function suportaJanelaFlutuante(): boolean {
  return typeof window !== "undefined" && "documentPictureInPicture" in window;
}

interface Props {
  /** o que renderizar dentro da janela */
  children: React.ReactNode;
  /** rótulo do botão que abre */
  rotulo: string;
  largura?: number;
  altura?: number;
  className?: string;
}

export function JanelaFlutuante({ children, rotulo, largura = 380, altura = 460, className }: Props) {
  const [janela, setJanela] = useState<Window | null>(null);
  const abrindo = useRef(false);

  const abrir = useCallback(async () => {
    if (abrindo.current || janela) return;
    abrindo.current = true;
    try {
      const w = await (window as unknown as {
        documentPictureInPicture: { requestWindow: (o: { width: number; height: number }) => Promise<Window> };
      }).documentPictureInPicture.requestWindow({ width: largura, height: altura });
      copiarEstilos(w.document);
      // Fechar a janela precisa devolver o estado, senão o botão fica achando que ela está aberta
      // e não reabre — bug clássico de janela secundária.
      w.addEventListener("pagehide", () => setJanela(null));
      setJanela(w);
    } catch {
      /* o usuário cancelou, ou o navegador recusou: segue sem janela, e sem erro na cara dele */
    } finally {
      abrindo.current = false;
    }
  }, [janela, largura, altura]);

  // Se a aba principal for embora, a janela vai junto: deixá-la órfã é deixar lixo na tela do
  // jogador, sem nada que a feche.
  useEffect(() => () => { try { janela?.close(); } catch { /* já fechada */ } }, [janela]);

  if (!suportaJanelaFlutuante()) return null;

  return (
    <>
      <button type="button" onClick={abrir} className={className}>
        {rotulo}
      </button>
      {janela && createPortal(children, janela.document.body)}
    </>
  );
}
