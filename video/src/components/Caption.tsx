import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { THEME } from "../theme";

// Legenda inferior (fade in e out). Enquanto não há voz, ela carrega o texto na tela.
export const Caption: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = interpolate(
    frame,
    [0, 12, durationInFrames - 12, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return (
    <div
      style={{
        position: "absolute",
        bottom: 70,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity,
      }}
    >
      <div
        style={{
          maxWidth: 1400,
          textAlign: "center",
          fontFamily: THEME.body,
          fontSize: 40,
          lineHeight: 1.35,
          color: THEME.light,
          background: "rgba(10,14,26,0.72)",
          padding: "18px 34px",
          borderRadius: 14,
          border: `1px solid rgba(45,212,191,0.25)`,
        }}
      >
        {text}
      </div>
    </div>
  );
};
