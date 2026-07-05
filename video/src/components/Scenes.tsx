import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, useVideoConfig } from "remotion";
import { THEME } from "../theme";
import { RangeGrid } from "./RangeGrid";
import demos from "../data/module1_demos.json";

const POSITIONS = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"];

const fadeUp = (frame: number, delay = 0) =>
  interpolate(frame - delay, [0, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

export const TitleScene: React.FC<{ eyebrow: string; title: string; subtitle: string }> = ({ eyebrow, title, subtitle }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", padding: 120 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 26, letterSpacing: 6, textTransform: "uppercase", color: THEME.teal, opacity: fadeUp(frame) }}>
        {eyebrow}
      </div>
      <div style={{ fontFamily: THEME.heading, fontSize: 82, fontWeight: 700, color: THEME.light, marginTop: 24, maxWidth: 1500, lineHeight: 1.1, opacity: fadeUp(frame, 8) }}>
        {title}
      </div>
      <div style={{ fontFamily: THEME.heading, fontSize: 96, fontWeight: 700, color: THEME.teal, marginTop: 10, opacity: fadeUp(frame, 20), transform: `translateY(${interpolate(fadeUp(frame, 20), [0, 1], [20, 0])}px)` }}>
        {subtitle}
      </div>
    </AbsoluteFill>
  );
};

export const SeatRowScene: React.FC<{ highlight: string }> = ({ highlight }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 60 }}>
      <div style={{ display: "flex", gap: 18 }}>
        {POSITIONS.map((p, idx) => {
          const on = p === highlight;
          const reveal = interpolate(frame, [idx * 6, idx * 6 + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={p} style={{
              width: 150, height: 150, borderRadius: 18, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", opacity: reveal,
              background: on ? "rgba(45,212,191,0.15)" : THEME.bgPanel,
              border: `2px solid ${on ? THEME.teal : "rgba(255,255,255,0.08)"}`,
              boxShadow: on ? `0 0 30px ${THEME.teal}` : "none",
            }}>
              <div style={{ fontFamily: THEME.heading, fontSize: 30, fontWeight: 700, color: on ? THEME.teal : THEME.light }}>{p}</div>
              {on && <div style={{ fontFamily: THEME.mono, fontSize: 18, color: THEME.teal, marginTop: 6 }}>fala por último</div>}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const TwoPanelScene: React.FC<{ left: string; leftDesc: string; right: string; rightDesc: string }> = ({ left, leftDesc, right, rightDesc }) => {
  const frame = useCurrentFrame();
  const panel = (label: string, desc: string, accent: string, delay: number, dark: boolean) => (
    <div style={{
      width: 620, height: 460, borderRadius: 24, background: dark ? "#05070d" : THEME.bgPanel,
      border: `2px solid ${accent}`, display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", gap: 20, opacity: fadeUp(frame, delay),
    }}>
      <div style={{ fontFamily: THEME.heading, fontSize: 52, fontWeight: 700, color: accent }}>{label}</div>
      <div style={{ fontFamily: THEME.body, fontSize: 34, color: THEME.light }}>{desc}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "row", gap: 60 }}>
      {panel(left, leftDesc, THEME.teal, 0, false)}
      {panel(right, rightDesc, THEME.red, 12, true)}
    </AbsoluteFill>
  );
};

export const RangeCompareScene: React.FC<{ leftPos: string; rightPos: string; hand: string }> = ({ leftPos, rightPos, hand }) => {
  const c = (demos as any).lessons.conceitos_posicao;
  const grids: Record<string, Record<string, number>> = { UTG: c.utg_grid, BTN: c.btn_grid };
  const pct: Record<string, number> = { UTG: c.utg_range_pct, BTN: c.btn_range_pct };
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "row", gap: 120 }}>
      <RangeGrid grid={grids[leftPos]} title={leftPos} subtitle={`abre ${pct[leftPos]}%`} highlight={hand} startFrame={0} />
      <RangeGrid grid={grids[rightPos]} title={rightPos} subtitle={`abre ${pct[rightPos]}%`} highlight={hand} startFrame={10} />
    </AbsoluteFill>
  );
};

export const ExerciseScene: React.FC<{ question: string; options: string[]; answer: string; explain: string }> = ({ question, options, answer, explain }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const revealAt = 5 * fps; // resposta aparece aos 5s
  const revealed = frame >= revealAt;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 40, padding: 100 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 24, letterSpacing: 4, textTransform: "uppercase", color: THEME.amber }}>Exercício</div>
      <div style={{ fontFamily: THEME.heading, fontSize: 56, fontWeight: 700, color: THEME.light, textAlign: "center", maxWidth: 1300 }}>{question}</div>
      <div style={{ display: "flex", gap: 30 }}>
        {options.map((o) => {
          const correct = revealed && o === answer;
          return (
            <div key={o} style={{
              minWidth: 220, padding: "24px 40px", borderRadius: 16, textAlign: "center",
              fontFamily: THEME.heading, fontSize: 44, fontWeight: 700,
              color: correct ? "#04121a" : THEME.light,
              background: correct ? THEME.teal : THEME.bgPanel,
              border: `2px solid ${correct ? THEME.teal : "rgba(255,255,255,0.1)"}`,
            }}>{o}</div>
          );
        })}
      </div>
      {!revealed ? (
        <div style={{ fontFamily: THEME.mono, fontSize: 40, color: THEME.amber }}>
          {Math.max(0, Math.ceil((revealAt - frame) / fps))}
        </div>
      ) : (
        <div style={{ fontFamily: THEME.body, fontSize: 32, color: THEME.muted, textAlign: "center", maxWidth: 1200, opacity: fadeUp(frame, revealAt) }}>
          {explain}
        </div>
      )}
    </AbsoluteFill>
  );
};

export const RecapScene: React.FC<{ bullets: string[]; cta: string }> = ({ bullets, cta }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 28, padding: 120 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 24, letterSpacing: 4, textTransform: "uppercase", color: THEME.teal }}>Resumo</div>
      {bullets.map((b, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 20, opacity: fadeUp(frame, i * 12), maxWidth: 1300 }}>
          <div style={{ width: 14, height: 14, borderRadius: 7, background: THEME.teal }} />
          <div style={{ fontFamily: THEME.body, fontSize: 40, color: THEME.light }}>{b}</div>
        </div>
      ))}
      <div style={{ marginTop: 40, padding: "20px 44px", borderRadius: 14, background: THEME.teal, color: "#04121a", fontFamily: THEME.heading, fontSize: 40, fontWeight: 700, opacity: fadeUp(frame, 48) }}>
        {cta}
      </div>
    </AbsoluteFill>
  );
};
