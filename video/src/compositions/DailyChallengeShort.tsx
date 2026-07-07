import React from "react";
import { AbsoluteFill, Series, Img, staticFile, useCurrentFrame, interpolate, spring } from "remotion";
import { THEME } from "../theme";
import { CardFace } from "../components/CardFace";
import spot from "../data/short_spot.json";

// Short vertical (9:16) do Desafio do Dia: gancho → spot → suspense → veredito → CTA.
// Dados 100% reais (spot vetado do #42). Feito pra TikTok/Reels/Shorts.

const FPS = 30;
const fade = (frame: number, d = 0) =>
  interpolate(frame - d, [0, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const actLabel = (a: string) =>
  a === "raise" ? (spot.scenario === "vs_3bet" ? "4-BET" : spot.scenario === "vs_rfi" ? "3-BET" : "RAISE")
    : a === "allin" ? "SHOVE" : a.toUpperCase();

const ctxLine = () => {
  const p = spot.position, vs = spot.vs_position;
  if (spot.scenario === "rfi") return `${p} · ${spot.stack_bb}bb · todos foldaram`;
  if (spot.scenario === "vs_rfi") return `${p} · ${spot.stack_bb}bb · ${vs} abriu`;
  return `${p} · ${spot.stack_bb}bb · ${vs} deu 3-bet`;
};

const HeroCards: React.FC = () => (
  <div style={{ display: "flex", gap: 18 }}>
    {(spot.hero_cards as { rank: string; suit: string }[]).map((c, i) => (
      <CardFace key={i} rank={c.rank} suit={c.suit} w={200} />
    ))}
  </div>
);

const Chip: React.FC<{ label: string; state?: "idle" | "right" | "dim" }> = ({ label, state = "idle" }) => {
  const right = state === "right";
  return (
    <div style={{
      padding: "22px 0", width: 300, textAlign: "center", borderRadius: 20,
      fontFamily: THEME.heading, fontWeight: 700, fontSize: 44,
      background: right ? THEME.teal : "rgba(255,255,255,0.06)",
      color: right ? "#04121a" : state === "dim" ? THEME.muted : THEME.light,
      border: `3px solid ${right ? THEME.teal : "rgba(255,255,255,0.12)"}`,
      opacity: state === "dim" ? 0.4 : 1,
      boxShadow: right ? `0 0 40px ${THEME.teal}` : "none",
    }}>{label}</div>
  );
};

const Hook: React.FC = () => {
  const f = useCurrentFrame();
  const s = spring({ frame: f, fps: FPS, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 30 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 34, letterSpacing: 8, color: THEME.teal, opacity: fade(f) }}>GRINDLAB</div>
      <div style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 150, color: THEME.light, transform: `scale(${0.6 + s * 0.4})`, textAlign: "center", lineHeight: 1 }}>
        SPOT<br />DO DIA
      </div>
      <div style={{ fontFamily: THEME.body, fontSize: 40, color: THEME.muted, opacity: fade(f, 20) }}>você joga certo?</div>
    </AbsoluteFill>
  );
};

const Setup: React.FC<{ pollMode?: boolean }> = ({ pollMode }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 48 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 40, color: THEME.teal, opacity: fade(f) }}>{ctxLine()}</div>
      <div style={{ opacity: fade(f, 8), transform: `translateY(${interpolate(fade(f, 8), [0, 1], [30, 0])}px)` }}><HeroCards /></div>
      <div style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 72, color: THEME.light, opacity: fade(f, 20) }}>O que você faz?</div>
      {pollMode ? (
        // variante Stories: NÃO cravar nada aqui. Só reserva o espaço em branco pro sticker de Quiz
        // nativo do Instagram (fold/call/raise/shove), que você coloca na hora de publicar.
        <div style={{ width: 620, height: 248 }} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 20, opacity: fade(f, 28) }}>
          {(spot.options as string[]).map((a) => <Chip key={a} label={actLabel(a)} />)}
        </div>
      )}
    </AbsoluteFill>
  );
};

// Cabeçalho persistente: logo GrindLab + selo "Desafio Diário" (identidade da marca).
const Header: React.FC = () => (
  <div style={{ position: "absolute", top: 90, left: 0, right: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: 20 }}>
    <Img src={staticFile("brand/logo-horizontal.svg")} style={{ width: 460 }} />
    <div style={{ padding: "12px 34px", borderRadius: 999, background: "rgba(45,212,191,0.12)", border: `2px solid ${THEME.teal}`,
      fontFamily: THEME.mono, fontSize: 32, letterSpacing: 4, color: THEME.teal, textTransform: "uppercase" }}>
      Desafio Diário
    </div>
  </div>
);

const Suspense: React.FC = () => {
  const f = useCurrentFrame();
  const n = 3 - Math.floor(f / FPS);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 40 }}>
      <HeroCards />
      <div style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 220, color: THEME.amber }}>{Math.max(1, n)}</div>
    </AbsoluteFill>
  );
};

const Reveal: React.FC = () => {
  const f = useCurrentFrame();
  const legs = spot.gto_strategy as { action: string; freq: number }[];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 40, padding: 60 }}>
      <div style={{ fontFamily: THEME.mono, fontSize: 34, letterSpacing: 6, color: THEME.teal }}>RESPOSTA GTO</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {(spot.options as string[]).map((a) => (
          <Chip key={a} label={actLabel(a)} state={a === spot.best_action ? "right" : "dim"} />
        ))}
      </div>
      {/* mix real em barras */}
      <div style={{ width: 640, display: "flex", flexDirection: "column", gap: 16, opacity: fade(f, 18) }}>
        {legs.filter((l) => l.freq > 0.01).map((l) => (
          <div key={l.action} style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ width: 130, fontFamily: THEME.heading, fontWeight: 700, fontSize: 32, color: THEME.light }}>{actLabel(l.action)}</span>
            <div style={{ flex: 1, height: 26, borderRadius: 13, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${Math.round(l.freq * 100)}%`, background: l.action === spot.best_action ? THEME.teal : THEME.sky }} />
            </div>
            <span style={{ width: 90, textAlign: "right", fontFamily: THEME.mono, fontSize: 32, color: THEME.muted }}>{Math.round(l.freq * 100)}%</span>
          </div>
        ))}
      </div>
      <div style={{ maxWidth: 900, textAlign: "center", fontFamily: THEME.body, fontSize: 40, lineHeight: 1.35, color: THEME.light, opacity: fade(f, 28) }}>
        {spot.why}
      </div>
    </AbsoluteFill>
  );
};

const CTA: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 40 }}>
      <div style={{ fontFamily: THEME.heading, fontWeight: 700, fontSize: 96, color: THEME.light, textAlign: "center", transform: `scale(${0.8 + fade(f) * 0.2})` }}>
        Desafio novo<br />todo dia
      </div>
      <div style={{ padding: "26px 60px", borderRadius: 18, background: THEME.teal, color: "#04121a", fontFamily: THEME.heading, fontWeight: 700, fontSize: 48, opacity: fade(f, 14) }}>
        grindlabpoker.com
      </div>
      <div style={{ fontFamily: THEME.body, fontSize: 40, color: THEME.muted, opacity: fade(f, 24) }}>link na bio</div>
    </AbsoluteFill>
  );
};

export const DailyChallengeShort: React.FC<{ pollMode?: boolean }> = ({ pollMode = false }) => (
  <AbsoluteFill style={{ background: THEME.bg }}>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 35%, rgba(45,212,191,0.10), transparent 60%)" }} />
    <Series>
      <Series.Sequence durationInFrames={3 * FPS}><Hook /></Series.Sequence>
      <Series.Sequence durationInFrames={5 * FPS}><Setup pollMode={pollMode} /></Series.Sequence>
      <Series.Sequence durationInFrames={3 * FPS}><Suspense /></Series.Sequence>
      <Series.Sequence durationInFrames={7 * FPS}><Reveal /></Series.Sequence>
      <Series.Sequence durationInFrames={3 * FPS}><CTA /></Series.Sequence>
    </Series>
    <Header />
  </AbsoluteFill>
);

export const SHORT_DURATION = (3 + 5 + 3 + 7 + 3) * FPS;

const Bg: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: THEME.bg }}>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 35%, rgba(45,212,191,0.10), transparent 60%)" }} />
    {children}
    <Header />
  </AbsoluteFill>
);

// ── Variante Stories (Quiz nativo do Instagram) ──────────────────────────────
// No Stories o sticker de Quiz flutua a DURAÇÃO INTEIRA da story, então o vídeo
// NÃO pode conter a resposta (ela ficaria embaixo do sticker). Por isso o Quiz é
// em DUAS stories: 1) a PERGUNTA (segura no spot, área do sticker limpa o tempo
// todo); 2) a RESPOSTA (Suspense + veredito + CTA), postada em seguida, sem sticker.
export const DailyChallengeQuestion: React.FC = () => (
  <Bg>
    <Series>
      <Series.Sequence durationInFrames={3 * FPS}><Hook /></Series.Sequence>
      <Series.Sequence durationInFrames={7 * FPS}><Setup pollMode /></Series.Sequence>
    </Series>
  </Bg>
);
export const QUESTION_DURATION = (3 + 7) * FPS;

export const DailyChallengeReveal: React.FC = () => (
  <Bg>
    <Series>
      <Series.Sequence durationInFrames={3 * FPS}><Suspense /></Series.Sequence>
      <Series.Sequence durationInFrames={7 * FPS}><Reveal /></Series.Sequence>
      <Series.Sequence durationInFrames={3 * FPS}><CTA /></Series.Sequence>
    </Series>
  </Bg>
);
export const REVEAL_DURATION = (3 + 7 + 3) * FPS;
