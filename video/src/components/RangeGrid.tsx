import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { THEME, RANKS, handAt } from "../theme";

// Range grid 13x13 real: colore por frequência de abertura (grid: hand -> freq 0..1).
// Preenche progressivamente (animação) e destaca a mão do exemplo.
export const RangeGrid: React.FC<{
  grid: Record<string, number>;
  title: string;
  subtitle?: string;
  highlight?: string;
  accent?: string;
  size?: number;
  startFrame?: number;
}> = ({ grid, title, subtitle, highlight, accent = THEME.teal, size = 520, startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const cell = size / 13;
  const appear = interpolate(frame - startFrame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
      <div style={{ fontFamily: THEME.heading, fontSize: 34, fontWeight: 700, color: THEME.light }}>{title}</div>
      {subtitle && (
        <div style={{ fontFamily: THEME.mono, fontSize: 22, color: accent }}>{subtitle}</div>
      )}
      <div style={{ position: "relative", width: size, height: size, background: THEME.bgPanel, borderRadius: 12, padding: 4 }}>
        {RANKS.map((_, i) =>
          RANKS.map((__, j) => {
            const hand = handAt(i, j);
            const freq = grid[hand] ?? 0;
            const isHi = highlight === hand;
            // ordem de aparição diagonal (i+j), pra "preencher" a grade
            const localAppear = interpolate(appear, [(i + j) / 26, (i + j) / 26 + 0.25], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const bg =
              freq > 0
                ? `rgba(45,212,191,${0.25 + 0.65 * freq})` // teal por frequência
                : "rgba(255,255,255,0.04)";
            return (
              <div
                key={hand}
                style={{
                  position: "absolute",
                  left: 4 + j * cell,
                  top: 4 + i * cell,
                  width: cell - 2,
                  height: cell - 2,
                  background: bg,
                  opacity: localAppear,
                  borderRadius: 3,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: THEME.mono,
                  fontSize: cell * 0.3,
                  color: freq > 0 ? "#04121a" : THEME.muted,
                  fontWeight: 700,
                  boxShadow: isHi ? `0 0 0 3px ${THEME.amber}, 0 0 18px ${THEME.amber}` : "none",
                  zIndex: isHi ? 5 : 1,
                }}
              >
                {hand.replace("s", "").replace("o", "")}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
