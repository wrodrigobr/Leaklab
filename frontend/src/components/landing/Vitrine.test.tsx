// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { Vitrine, type BlocoVitrine } from './Vitrine';

/**
 * Vitrine da landing — o que ela promete é MOSTRAR o produto.
 *
 * Os dois riscos que este arquivo guarda:
 *
 * 1. O bloco sem `print` tem que renderizar a grade DE VERDADE. Se alguém trocar por uma imagem,
 *    a landing passa a mostrar um raster que envelhece calado no dia em que a carta muda.
 * 2. O bloco COM `print` cujo arquivo não existe tem que dizer "captura pendente" na tela. Slot
 *    vazio e silencioso parece proposital — é o mesmo defeito de uma medição que devolve zero
 *    sem ter olhado nada.
 */

const base: BlocoVitrine = {
  rotulo: 'grindlabpoker.com/ranges',
  titulo: 'A carta inteira',
  texto: 'texto do bloco',
  bullets: ['primeiro ponto', 'segundo ponto'],
};

function montar(blocos: BlocoVitrine[]) {
  return render(<Vitrine eyebrow="O PRODUTO" heading="Veja antes de criar conta" blocos={blocos} />);
}

describe('Vitrine', () => {
  afterEach(cleanup);

  it('o bloco sem print renderiza a grade viva, não uma imagem', () => {
    const { container } = montar([base]);
    expect(container.querySelectorAll('img')).toHaveLength(0);
    // a grade tem 169 células; se virar imagem, some
    const celulas = container.querySelectorAll('[title*=":"]');
    expect(celulas.length).toBeGreaterThan(150);
  });

  it('a grade viva mostra frequência de verdade no title da célula', () => {
    // CONTRAPROVA do teste acima: 169 divs vazias também passariam por "grade".
    const { container } = montar([base]);
    const titles = [...container.querySelectorAll('[title]')].map((e) => e.getAttribute('title'));
    expect(titles.some((x) => /Raise \d+%/.test(x ?? ''))).toBe(true);
    expect(titles.some((x) => /Fold \d+%/.test(x ?? ''))).toBe(true);
  });

  it('print declarado e ausente ESCONDE o bloco, em vez de anunciar o arquivo', () => {
    // ── Este teste dizia o contrário até 28/08 ──────────────────────────────────────────────
    //
    // Ele exigia que a captura ausente virasse "um aviso VISÍVEL", e o componente obedecia:
    // caixa tracejada, "captura pendente", caminho do arquivo em fonte mono. Era um lembrete
    // que eu tinha escrito para mim, e o teste o congelou como requisito.
    //
    // Foi para produção. O `main-CkqZOPrS.js` publicado em grindlabpoker.com continha a frase, e
    // três dos quatro blocos da seção "O produto" mostravam isso para o visitante.
    //
    // Aviso de obra é para quem constrói. O guarda que serve a quem constrói é
    // `landingCapturasExistem.test.ts`, que quebra a build; a tela do visitante não é o lugar.
    const { container } = montar([{ ...base, print: '/landing/nao-existe.webp' }]);
    const img = container.querySelector('img');
    expect(img, 'o bloco com print deveria começar tentando a imagem').toBeTruthy();
    // `error` em <img> não borbulha, então um Event cru não chega ao onError do React. O
    // `fireEvent.error` é quem entrega o evento sintético — a 1ª versão deste teste falhava por
    // isso e a falha estava CERTA.
    fireEvent.error(img!);
    expect(screen.queryByText(/captura pendente/i),
           'a tela do visitante não anuncia arquivo faltando').toBeNull();
    expect(screen.queryByText('/landing/nao-existe.webp'),
           'o caminho do arquivo não vai para a tela').toBeNull();
    // E o bloco inteiro sai: texto sozinho ao lado de moldura vazia leria como tela quebrada.
    expect(screen.queryByText(base.titulo), 'o bloco deveria ter sumido').toBeNull();
  });

  it('mostra o rótulo da tela, o título e os DOIS bullets', () => {
    montar([base]);
    expect(screen.getByText('grindlabpoker.com/ranges')).toBeTruthy();
    expect(screen.getByText('A carta inteira')).toBeTruthy();
    expect(screen.getByText('primeiro ponto')).toBeTruthy();
    expect(screen.getByText('segundo ponto')).toBeTruthy();
  });

  it('alterna o lado dos blocos, que é o ritmo do padrão', () => {
    const { container } = montar([base, { ...base, titulo: 'Segundo' }]);
    const ordenados = container.querySelectorAll('.md\\:order-1, .md\\:order-2');
    expect(ordenados.length).toBe(2);   // só o segundo bloco inverte
  });
});
