// @vitest-environment jsdom
import fs from "node:fs";
import path from "node:path";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JanelaFlutuante, suportaJanelaFlutuante } from "./JanelaFlutuante";

/**
 * A janela flutuante: a única parte do produto que serve DURANTE a mão.
 *
 * ── O que originou (28/08) ────────────────────────────────────────────────────────────────
 *
 * Último item do benchmark. Eles resolvem com aplicativo desktop;
 * `documentPictureInPicture` faz o mesmo a partir da página, e isso foi confirmado ao vivo antes
 * de escrever a primeira linha: a API existe, abre e devolve um `Document` real.
 *
 * ── A armadilha que a medição pegou, e que estes guardas protegem ─────────────────────────
 *
 * **A janela não herda o CSS da página**: `w.document.styleSheets.length === 0` numa janela
 * recém-aberta. Sem copiar as folhas, a grade abre sem formatação nenhuma — não gera erro, não
 * quebra teste, e só aparece para quem olha. É a mesma família da captura que faltava na landing:
 * o defeito é invisível para o código e óbvio na tela.
 *
 * E copiar de UMA forma só não basta: em produção o Vite emite `<link rel="stylesheet">`, no dev
 * ele injeta `<style>`. Quem revisa está no dev e não veria o modo que quebra.
 */

class JanelaFalsa {
  document: Document;
  fechada = false;
  private ouvintes: Record<string, Array<() => void>> = {};
  constructor() {
    this.document = document.implementation.createHTMLDocument("pip");
  }
  addEventListener(ev: string, fn: () => void) {
    (this.ouvintes[ev] ||= []).push(fn);
  }
  close() { this.fechada = true; }
}

let ultima: JanelaFalsa | null = null;

beforeEach(() => {
  ultima = null;
  (window as unknown as Record<string, unknown>).documentPictureInPicture = {
    requestWindow: vi.fn(async () => {
      ultima = new JanelaFalsa();
      return ultima as unknown as Window;
    }),
  };
});

afterEach(() => {
  cleanup();
  delete (window as unknown as Record<string, unknown>).documentPictureInPicture;
});

describe("janela flutuante de consulta", () => {
  it("não oferece o botão onde a API não existe", () => {
    // Firefox e Safari não têm `documentPictureInPicture`. Oferecer e falhar é pior que não
    // oferecer: o jogador conclui que o produto está quebrado, e não que o navegador não suporta.
    delete (window as unknown as Record<string, unknown>).documentPictureInPicture;
    expect(suportaJanelaFlutuante()).toBe(false);
    const { container } = render(<JanelaFlutuante rotulo="abrir"><p>x</p></JanelaFlutuante>);
    expect(container.querySelector("button")).toBeNull();
  });

  it("abre a janela e renderiza o conteúdo dentro DELA", async () => {
    render(<JanelaFlutuante rotulo="abrir"><p>conteudo-da-janela</p></JanelaFlutuante>);
    fireEvent.click(screen.getByText("abrir"));
    await vi.waitFor(() => expect(ultima).not.toBeNull());
    await vi.waitFor(() => {
      expect(ultima!.document.body.textContent).toContain("conteudo-da-janela");
    });
    // E NÃO no documento principal: o portal existe para tirar o conteúdo daqui.
    expect(document.body.textContent).not.toContain("conteudo-da-janela");
  });

  it("COPIA as folhas de estilo para a janela", async () => {
    // O defeito que a medição pegou: a janela nasce com `styleSheets.length === 0`.
    const tag = document.createElement("style");
    tag.textContent = ".teste-de-copia{color:red}";
    document.head.appendChild(tag);
    try {
      render(<JanelaFlutuante rotulo="abrir"><p>x</p></JanelaFlutuante>);
      fireEvent.click(screen.getByText("abrir"));
      await vi.waitFor(() => expect(ultima).not.toBeNull());
      await vi.waitFor(() => {
        const css = Array.from(ultima!.document.head.querySelectorAll("style"))
          .map((e) => e.textContent).join("");
        expect(css, "a janela abriu SEM os estilos da página").toContain("teste-de-copia");
      });
    } finally {
      tag.remove();
    }
  });

  it("leva o TEMA junto", async () => {
    // Sem isto a janela abre no claro enquanto o app está no escuro, e a grade fica ilegível.
    document.documentElement.setAttribute("data-theme", "dark");
    document.documentElement.className = "dark";
    render(<JanelaFlutuante rotulo="abrir"><p>x</p></JanelaFlutuante>);
    fireEvent.click(screen.getByText("abrir"));
    await vi.waitFor(() => expect(ultima).not.toBeNull());
    await vi.waitFor(() => {
      expect(ultima!.document.documentElement.getAttribute("data-theme")).toBe("dark");
    });
  });

  it("copia as DUAS formas de folha, <style> e <link>", () => {
    // Em produção o Vite emite <link>; no dev injeta <style>. Quem revisa está no dev e não veria
    // o modo que quebra — por isso o guarda olha o CÓDIGO, e não só o comportamento no jsdom
    // (onde folhas de outra origem não existem para exercitar o ramo do <link>).
    const fonte = fs.readFileSync(path.join(__dirname, "JanelaFlutuante.tsx"), "utf-8");
    expect(fonte, "não copia <style>").toContain('createElement("style")');
    expect(fonte, "não copia <link> (o caminho de produção)").toContain('createElement("link")');
  });

  it("fecha a janela quando o componente sai", async () => {
    // Janela órfã é lixo na tela do jogador, sem nada que a feche.
    const { unmount } = render(<JanelaFlutuante rotulo="abrir"><p>marca-de-portal</p></JanelaFlutuante>);
    fireEvent.click(screen.getByText("abrir"));
    // Espera o CONTEUDO aparecer, e nao so a janela falsa existir: a janela nasce dentro da
    // promessa, mas `janela` so entra no estado do React no render seguinte. Desmontar antes
    // disso testava um componente que ainda nao sabia da janela -- e a 1a versao deste teste
    // acusou o componente por um defeito do proprio teste.
    await vi.waitFor(() => {
      expect(ultima?.document.body.textContent).toContain("marca-de-portal");
    });
    unmount();
    expect(ultima!.fechada, "a janela ficou aberta depois de a página sair").toBe(true);
  });
});
