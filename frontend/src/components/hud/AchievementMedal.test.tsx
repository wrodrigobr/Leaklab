// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { AchievementMedal, MEDAL_EMBLEMS } from "./AchievementMedal";
import { ACHIEVEMENT_MEDALS } from "@/lib/achievementMedals";
import { MEDAL_TIERS, TIER_COLORS } from "@/lib/medalTiers";

/**
 * A medalha de conquista.
 *
 * ── O bug da referência, e por que ele é o primeiro teste ─────────────────────────────────────
 *
 * O componente de referência (gerado pelo Lovable) dava `id` único a três dos quatro gradientes e
 * deixava o quarto fixo: `id="engrave"`. `id` em SVG é global do DOCUMENTO. Numa grade de 12
 * medalhas, todo `url(#engrave)` resolve para o PRIMEIRO do documento, e os 12 emblemas saem
 * pintados com as cores da primeira medalha.
 *
 * É um defeito que passa em revisão e passa isolado no Storybook: só aparece quando mais de uma
 * medalha existe na mesma página, que é o único jeito que a tela usa.
 */
afterEach(cleanup);

describe("AchievementMedal — ids não podem colidir entre medalhas", () => {
  it("duas medalhas na mesma página não compartilham nenhum id de gradiente", () => {
    const { container } = render(
      <>
        <AchievementMedal tier="bronze" emblem="chip" label="a" />
        <AchievementMedal tier="diamond" emblem="crown" label="b" />
      </>,
    );
    const ids = Array.from(container.querySelectorAll("[id]")).map((e) => e.id);
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size, `ids repetidos: ${ids.join(", ")}`).toBe(ids.length);
  });

  it("medalhas de MESMO tier e MESMO emblema também não colidem", () => {
    // O `uid` da referência era `tier-emblem-locked`: este caso colidia.
    const { container } = render(
      <>
        <AchievementMedal tier="gold" emblem="club" label="a" />
        <AchievementMedal tier="gold" emblem="club" label="b" />
      </>,
    );
    const ids = Array.from(container.querySelectorAll("[id]")).map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("todo url(#...) aponta para um id que existe NESTA medalha", () => {
    const { container } = render(
      <>
        <AchievementMedal tier="bronze" emblem="chip" label="a" />
        <AchievementMedal tier="silver" emblem="range" label="b" />
      </>,
    );
    container.querySelectorAll("svg").forEach((svg) => {
      const locais = new Set(Array.from(svg.querySelectorAll("[id]")).map((e) => e.id));
      const html = svg.outerHTML;
      const refs = Array.from(html.matchAll(/url\(#([^)]+)\)/g)).map((m) => m[1]);
      expect(refs.length).toBeGreaterThan(0);
      refs.forEach((r) => expect(locais.has(r), `${r} não existe nesta medalha`).toBe(true));
    });
  });
});

describe("AchievementMedal — acessibilidade", () => {
  it("anuncia o estado bloqueado, e não só o nome", () => {
    // Na referência o aria-label era o mesmo com e sem cadeado: quem usa leitor de tela não
    // distinguia uma conquista ganha de uma pendente.
    const { container } = render(
      <AchievementMedal tier="gold" emblem="club" locked label="Ouro. Medalha ouro, ainda bloqueada." />,
    );
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("role")).toBe("img");
    expect(svg.getAttribute("aria-label")).toContain("bloqueada");
    expect(svg.querySelector("title")?.textContent).toContain("bloqueada");
  });

  it("o componente NÃO monta frase — o texto vem pronto do chamador", () => {
    // Se ele montasse ("Medalha " + tier), a string ficaria em PT fixo e violaria o i18n.
    const { container } = render(
      <AchievementMedal tier="bronze" emblem="spade" label="TEXTO EXATO" />,
    );
    expect(container.querySelector("svg")!.getAttribute("aria-label")).toBe("TEXTO EXATO");
  });
});

describe("AchievementMedal — legibilidade do emblema", () => {
  it("o emblema é desenhado DEPOIS do brilho especular", () => {
    // Na referência o brilho vinha por último e lavava o canto superior esquerdo do traço, o que
    // deixava bronze e ouro difíceis de ler a 56px.
    const { container } = render(<AchievementMedal tier="bronze" emblem="chip" label="a" />);
    const html = container.querySelector("svg")!.innerHTML;
    expect(html.indexOf("ellipse")).toBeLessThan(html.indexOf("<g>"));
  });

  it("o emblema usa o tom CLARO do tier, não o profundo", () => {
    const { container } = render(<AchievementMedal tier="bronze" emblem="spade" label="a" />);
    const path = container.querySelector("svg > path[fill]")!;
    expect(path.getAttribute("fill")).toBe(TIER_COLORS.bronze.light);
  });
});

/** Luminância relativa e razão de contraste WCAG. */
function luminancia(hex: string) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const f = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function contraste(a: string, b: string) {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

describe("contraste do emblema", () => {
  const NUCLEO = "#0A0E1A";   // --background da marca, o fundo do disco interno

  it("todo tier lê contra o núcleo escuro", () => {
    // O limiar WCAG para objeto gráfico é 3:1; exigimos 4.5 porque o emblema é traço fino a 52px.
    // Medido: bronze 8.95, prata 15.30, ouro 11.87, diamante 12.84.
    MEDAL_TIERS.forEach((tr) => {
      const c = contraste(TIER_COLORS[tr].light, NUCLEO);
      expect(c, `${tr}: ${c.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
    });
  });

  it("o tom PROFUNDO não serviria, e é por isso que o emblema não usa gradiente", () => {
    // A referência pintava o emblema com um gradiente claro→profundo, então a metade de baixo do
    // desenho caía no tom profundo. No bronze isso dá 3.70:1, no limite do aceitável para traço
    // fino. Este teste documenta o motivo da escolha: se alguém "melhorar" reintroduzindo o
    // gradiente, o de cima falha.
    expect(contraste(TIER_COLORS.bronze.deep, NUCLEO)).toBeLessThan(4.5);
  });
});

describe("mapa de conquistas", () => {
  it("cobre as 12 conquistas do backend", () => {
    // As chaves vêm de `_TRAINING_ACHIEVEMENT_DEFS` (database/repositories.py). Uma conquista fora
    // do mapa não renderiza — e o teste falha aqui em vez de a medalha sumir na tela em silêncio.
    const doBackend = [
      "train:first", "train:reps50", "train:silver", "train:gold", "train:reps200",
      "train:explorer", "train:gold3", "train:diamond", "train:streak3", "train:streak7",
      "train:reps1000", "train:streak30",
    ];
    doBackend.forEach((k) => expect(ACHIEVEMENT_MEDALS[k], `sem medalha: ${k}`).toBeTruthy());
    expect(Object.keys(ACHIEVEMENT_MEDALS).sort()).toEqual(doBackend.sort());
  });

  it("as conquistas de TIER recebem o tier correspondente", () => {
    // Sem isto a conquista "Ouro" poderia sair com medalha de prata e a tela se contradiria.
    expect(ACHIEVEMENT_MEDALS["train:silver"].tier).toBe("silver");
    expect(ACHIEVEMENT_MEDALS["train:gold"].tier).toBe("gold");
    expect(ACHIEVEMENT_MEDALS["train:diamond"].tier).toBe("diamond");
  });

  it("só usa tiers e emblemas que existem", () => {
    Object.entries(ACHIEVEMENT_MEDALS).forEach(([k, m]) => {
      expect(MEDAL_TIERS, k).toContain(m.tier);
      expect(MEDAL_EMBLEMS, k).toContain(m.emblem);
    });
  });

  it("todo emblema declarado desenha alguma coisa", () => {
    // Um emblema sem `case` no switch cai no `default: return null` e a medalha sai VAZIA, com o
    // disco perfeito e nada dentro. Falha silenciosa clássica.
    MEDAL_EMBLEMS.forEach((e) => {
      const { container } = render(<AchievementMedal tier="gold" emblem={e} label={e} />);
      const svg = container.querySelector("svg")!;
      const desenhos = svg.querySelectorAll("path, g > circle, g > rect");
      expect(desenhos.length, `emblema vazio: ${e}`).toBeGreaterThan(0);
      cleanup();
    });
  });
});

describe("a escala de tier é UMA só", () => {
  it("rótulos de tier existem nas 3 locales", async () => {
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = (await import(`@/i18n/locales/${loc}/training.json`)).default as
        { tiers: Record<string, string>; status: Record<string, string> };
      MEDAL_TIERS.forEach((tr) => {
        expect(d.tiers?.[tr], `${loc}.tiers.${tr}`).toBeTruthy();
      });
      // e as duas frases da medalha, com os dois placeholders
      for (const k of ["medalAria", "medalAriaLocked"]) {
        expect(d.status?.[k], `${loc}.status.${k}`).toContain("{{title}}");
        expect(d.status?.[k], `${loc}.status.${k}`).toContain("{{tier}}");
      }
      // ganha e bloqueada não podem ser a MESMA frase
      expect(d.status.medalAria).not.toBe(d.status.medalAriaLocked);
      // regra do projeto: sem travessão na copy visível
      MEDAL_TIERS.forEach((tr) => expect(d.tiers[tr]).not.toContain("—"));
    }
  });
});
