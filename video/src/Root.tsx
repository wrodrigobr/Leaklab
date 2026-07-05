import React from "react";
import { Composition } from "remotion";
import { Aula1Conceitos, AULA1_DURATION } from "./compositions/Aula1Conceitos";
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
      />
    </>
  );
};
