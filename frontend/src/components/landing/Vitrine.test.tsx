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

  it('print declarado e ausente vira aviso VISÍVEL, não espaço em branco', () => {
    const { container } = montar([{ ...base, print: '/landing/nao-existe.webp' }]);
    const img = container.querySelector('img');
    expect(img, 'o bloco com print deveria começar tentando a imagem').toBeTruthy();
    // `error` em <img> não borbulha, então um Event cru não chega ao onError do React. O
    // `fireEvent.error` é quem entrega o evento sintético — a 1ª versão deste teste falhava por
    // isso e a falha estava CERTA.
    fireEvent.error(img!);
    expect(screen.getByText(/captura pendente/i)).toBeTruthy();
    expect(screen.getByText('/landing/nao-existe.webp')).toBeTruthy();
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
