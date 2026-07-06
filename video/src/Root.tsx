import React from "react";
import { Composition } from "remotion";
import { Aula1Conceitos, AULA1_DURATION } from "./compositions/Aula1Conceitos";
import { DailyChallengeShort, SHORT_DURATION } from "./compositions/DailyChallengeShort";
import { CoachReplay, COACH_REPLAY_DURATION } from "./compositions/CoachReplay";
import script from "./data/aula1_script.json";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Aula1Conceitos"
        component={Aula1Conceitos}
        durationInFrames={AULA1_DURATION}
        fps={script.fps}
        width={script.width}
        height={script.height}
        defaultProps={{ hideCaptions: false }}
      />
      <Composition
        id="DailyChallengeShort"
        component={DailyChallengeShort}
        durationInFrames={SHORT_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="CoachReplay"
        component={CoachReplay}
        durationInFrames={COACH_REPLAY_DURATION}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
