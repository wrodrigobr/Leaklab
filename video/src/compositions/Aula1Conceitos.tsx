import React from "react";
import { AbsoluteFill, Series, Audio, staticFile } from "remotion";
import { THEME } from "../theme";
import { Caption } from "../components/Caption";
import {
  TitleScene, PokerTableScene, TwoPanelScene, RangeCompareScene, ExerciseScene, RecapScene,
} from "../components/Scenes";
import script from "../data/aula1_script.json";
import audioManifest from "../data/audio_manifest.json";

const FPS = script.fps;
const manifest = audioManifest as Record<string, { file: string; seconds?: number }>;

// Duração da cena: se já existe áudio gerado (manifest), usa a duração dele; senão o seconds do roteiro.
function sceneFrames(id: string, seconds: number): number {
  const a = manifest[id];
  const s = a?.seconds ?? seconds;
  return Math.round(s * FPS);
}

function renderVisual(v: any) {
  switch (v.type) {
    case "title": return <TitleScene eyebrow={v.eyebrow} title={v.title} subtitle={v.subtitle} />;
    case "pokerTable": return <PokerTableScene highlight={v.highlight} />;
    case "twoPanel": return <TwoPanelScene left={v.left} leftDesc={v.leftDesc} right={v.right} rightDesc={v.rightDesc} />;
    case "rangeCompare": return <RangeCompareScene leftPos={v.leftPos} rightPos={v.rightPos} hand={v.hand} />;
    case "exercise": return <ExerciseScene question={v.question} options={v.options} answer={v.answer} explain={v.explain} />;
    case "recap": return <RecapScene bullets={v.bullets} cta={v.cta} />;
    default: return null;
  }
}

// hideCaptions=true exporta os clipes SEM a nossa legenda (o HeyGen põe a própria).
export const Aula1Conceitos: React.FC<{ hideCaptions?: boolean }> = ({ hideCaptions = false }) => {
  return (
    <AbsoluteFill style={{ background: THEME.bg }}>
      {/* leve textura de fundo (scanline sutil da marca) */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 30%, rgba(45,212,191,0.06), transparent 60%)" }} />
      <Series>
        {script.scenes.map((s: any) => {
          const cap = s.visual.caption as string | undefined;
          const audio = manifest[s.id];
          return (
            <Series.Sequence key={s.id} durationInFrames={sceneFrames(s.id, s.seconds)}>
              <AbsoluteFill>
                {renderVisual(s.visual)}
                {!hideCaptions && cap && <Caption text={cap} />}
                {audio && <Audio src={staticFile(audio.file)} />}
              </AbsoluteFill>
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};

// Duração total (frames), pra registrar a Composition.
export const AULA1_DURATION = script.scenes.reduce(
  (acc: number, s: any) => acc + sceneFrames(s.id, s.seconds),
  0
);
