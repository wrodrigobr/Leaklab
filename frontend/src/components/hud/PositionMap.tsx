import { cn } from "@/lib/utils";

/**
 * Mapa de posições: mesa de 9 lugares, minúscula, com os assentos NOMEADOS.
 *
 * Existe porque os exercícios dizem "LJ abre com 50bb" e isso não significa nada para quem ainda
 * não sabe onde o LJ senta. O nome da posição é vocabulário: sem a referência espacial, o jogador
 * decora uma sigla e não entende por que ela abre mais estreito que o CO.
 *
 * É um SVG próprio, e não o `PokerTableV3`: aquele monta uma MÃO (stacks, apostas, cartas, pote)
 * e precisa de um `step` inteiro. Aqui não há mão nenhuma, só a geometria dos assentos — usar a
 * mesa de verdade exigiria fabricar um estado falso só para desenhar rótulos.
 *
 * A ordem é FÍSICA (como as pessoas sentam), não a ordem de ação: começa no botão e anda no
 * sentido do jogo. É assim que a mesa aparece na tela do poker, e o objetivo aqui é justamente
 * construir a referência visual que o jogador vai reencontrar jogando.
 */

// Assentos no sentido do jogo, a partir do botão. SB e BB vêm logo depois dele, e o CO é o
// último antes de fechar a volta.
const ASSENTOS = ["BTN", "SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO"] as const;

const W = 260, H = 132;
const CX = W / 2, CY = H / 2, RX = 96, RY = 44;

/** Ângulo do assento: o botão fica embaixo à direita e a volta segue no sentido horário. */
function posicaoDoAssento(i: number) {
  const ang = (Math.PI / 2) + (i * 2 * Math.PI) / ASSENTOS.length + 0.35;
  return { x: CX + RX * Math.cos(ang), y: CY + RY * Math.sin(ang) };
}

export function PositionMap({ destaque, secundario, className }: {
  /** Posição em foco (a que o exercício está perguntando). */
  destaque?: string | null;
  /** Segunda posição a marcar, quando o spot tem vilão. */
  secundario?: string | null;
  className?: string;
}) {
  const norm = (p?: string | null) => (p || "").toUpperCase().trim();
  const alvo = norm(destaque), vilao = norm(secundario);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={cn("w-full max-w-[260px]", className)}
         role="img" aria-label={`Mesa de 9 lugares, posição ${alvo || "não definida"} em destaque`}>
      <ellipse cx={CX} cy={CY} rx={RX - 4} ry={RY - 4}
               fill="rgba(16,84,60,0.18)" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
      {ASSENTOS.map((p, i) => {
        const { x, y } = posicaoDoAssento(i);
        const eAlvo = p === alvo;
        const eVilao = p === vilao;
        const w = p.length > 3 ? 34 : 26;
        return (
          <g key={p}>
            <rect x={x - w / 2} y={y - 8} width={w} height={16} rx={4}
              fill={eAlvo ? "rgba(245,197,66,0.22)" : eVilao ? "rgba(45,212,191,0.18)" : "rgba(255,255,255,0.05)"}
              stroke={eAlvo ? "#f5c542" : eVilao ? "#2DD4BF" : "rgba(255,255,255,0.12)"}
              strokeWidth={eAlvo || eVilao ? 1.2 : 0.8} />
            <text x={x} y={y + 3.5} textAnchor="middle"
              fontSize={p.length > 3 ? 7.5 : 8.5} fontFamily="ui-monospace, monospace"
              fontWeight={eAlvo || eVilao ? 700 : 400}
              fill={eAlvo ? "#f5c542" : eVilao ? "#2DD4BF" : "rgba(255,255,255,0.45)"}>
              {p}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
