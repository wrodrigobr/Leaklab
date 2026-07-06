import React from "react";
import { AbsoluteFill, Series, useCurrentFrame, interpolate } from "remotion";
import { THEME } from "../theme";
import spec from "../data/coach_replay_spec.json";

// PROVA do Coach Replay: renderiza o ReplaySpec real (dados dos engines, sem invenção).
// Intro (stats do torneio) → uma cena por leak (título + EV perdido + mãos-exemplo +
// recomendação) → plano de estudo. 16:9. É a mesma ideia do curriculum, dirigida por spec.

const FPS = 30;
const fade = (f: number, d = 0) => interpolate(f - d, [0, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const GLYPH: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
const RED = new Set(["h", "d"]);

const MiniCards: React.FC<{ cards: string }> = ({ cards }) => {
  // "3d8h" -> [3d, 8h]
  const pairs = (cards || "").match(/.{1,2}/g) ?? [];
  return (
    <div style={{ display: "flex", gap: 6 }}>
      {pairs.map((c, i) => {
        const red = RED.has(c[1]);
        return (
          <div key={i} style={{ width: 42, height: 58, borderRadius: 6, background: "#fff", color: red ? "#e03131" : "#141821", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", fontFamily: THEME.heading, fontWeight: 700, fontSize: 22, lineHeight: 1 }}>
            <span>{c[0].toUpperCase()}</span><span style={{ fontSize: 18 }}>{GLYPH[c[1]] ?? c[1]}</span>
          </div>
        );
      })}
    </div>
  );
};

const IntroScene: React.FC = () => {
  const f = useCurrentFrame();
  const t = spec.tournament;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 26, padding: 100, textAlign: "center" }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 26, letterSpacing: 6, color: THEME.teal, opacity: fade(f) }}>GRINDLAB COACH REPLAY</div>
      <div style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 78, color: THEME.light, opacity: fade(f, 8) }}>{t.name}</div>
      <div style={{ fontFamily: THEME.body, fontSize: 44, color: THEME.muted, opacity: fade(f, 20), maxWidth: 1300 }}>
        Analisamos <b style={{ color: THEME.light }}>{spec.intro.hands_analyzed}</b> mãos e encontramos <b style={{ color: THEME.amber }}>{spec.intro.leaks_found}</b> padrões que estão custando EV.
      </div>
    </AbsoluteFill>
  );
};

const LeakScene: React.FC<{ leak: any; idx: number }> = ({ leak, idx }) => {
  const f = useCurrentFrame();
  const evPct = Math.min(100, Math.abs(leak.ev_lost_bb) * 12);   // barra proporcional (visual)
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: "0 140px", gap: 24 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 26, letterSpacing: 4, color: THEME.amber, opacity: fade(f) }}>LEAK #{idx + 1}</div>
      <div style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 66, color: THEME.light, opacity: fade(f, 6) }}>{leak.title}</div>

      <div style={{ display: "flex", alignItems: "center", gap: 20, opacity: fade(f, 14) }}>
        <span style={{ width: 220, fontFamily: THEME.body, fontSize: 30, color: THEME.muted }}>EV perdido</span>
        <div style={{ flex: 1, height: 24, borderRadius: 12, background: "rgba(255,255,255,0.08)", overflow: "hidden", maxWidth: 700 }}>
          <div style={{ height: "100%", width: `${evPct}%`, background: THEME.red }} />
        </div>
        <span style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 40, color: THEME.red }}>{leak.ev_lost_bb}bb</span>
      </div>
      <div style={{ fontFamily: THEME.mono, fontSize: 24, color: THEME.muted, opacity: fade(f, 18) }}>
        {leak.occurrences} spots · tendência {leak.trend}
      </div>

      {/* mãos-exemplo REAIS deste torneio */}
      <div style={{ marginTop: 10, opacity: fade(f, 24) }}>
        <div style={{ fontFamily: THEME.mono, fontSize: 22, letterSpacing: 3, color: THEME.teal, marginBottom: 12 }}>SUAS MÃOS</div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          {leak.examples.map((e: any, i: number) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, background: THEME.bgPanel, padding: "12px 18px", borderRadius: 12, border: "1px solid rgba(255,255,255,0.08)" }}>
              <MiniCards cards={e.hero_cards} />
              <div>
                <div style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 26, color: THEME.light }}>{e.position}</div>
                <div style={{ fontFamily: THEME.mono, fontSize: 20, color: THEME.muted }}>GTO {e.gto_action} · {e.ev_loss_bb}bb</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 16, fontFamily: THEME.body, fontSize: 32, color: THEME.light, opacity: fade(f, 32), maxWidth: 1200 }}>
        {leak.recommendation}
      </div>
    </AbsoluteFill>
  );
};

const PlanScene: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 26, padding: 100 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 26, letterSpacing: 6, color: THEME.teal }}>SEU PLANO DE ESTUDO</div>
      {spec.plan.map((p: any, i: number) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 24, opacity: fade(f, i * 12) }}>
          <div style={{ width: 120, textAlign: "center", fontFamily: THEME.heading, fontWeight: 700, fontSize: 30, color: THEME.amber }}>Semana {p.week}</div>
          <div style={{ fontFamily: THEME.body, fontSize: 40, color: THEME.light }}>{p.focus}</div>
        </div>
      ))}
      <div style={{ marginTop: 30, padding: "20px 46px", borderRadius: 14, background: THEME.teal, color: "#04121a", fontFamily: THEME.heading, fontWeight: 700, fontSize: 38, opacity: fade(f, 40) }}>
        Treinar no GrindLab
      </div>
    </AbsoluteFill>
  );
};

export const CoachReplay: React.FC = () => (
  <AbsoluteFill style={{ background: THEME.bg }}>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 30%, rgba(45,212,191,0.06), transparent 60%)" }} />
    <Series>
      <Series.Sequence durationInFrames={6 * FPS}><IntroScene /></Series.Sequence>
      {(spec.leaks as any[]).map((leak, i) => (
        <Series.Sequence key={i} durationInFrames={9 * FPS}><LeakScene leak={leak} idx={i} /></Series.Sequence>
      ))}
      <Series.Sequence durationInFrames={7 * FPS}><PlanScene /></Series.Sequence>
    </Series>
  </AbsoluteFill>
);

export const COACH_REPLAY_DURATION = (6 + 9 * (spec.leaks as any[]).length + 7) * FPS;
