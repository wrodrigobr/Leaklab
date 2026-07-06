import React from "react";
import { THEME } from "../theme";

const GLYPH: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
const RED = new Set(["h", "d"]);

// Carta grande pro Short (rank + naipe colorido).
export const CardFace: React.FC<{ rank: string; suit: string; w?: number }> = ({ rank, suit, w = 180 }) => {
  const red = RED.has(suit);
  return (
    <div style={{
      width: w, height: w * 1.4, borderRadius: w * 0.09, background: "#fff",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      boxShadow: "0 12px 40px rgba(0,0,0,0.5)", color: red ? "#e03131" : "#141821",
      fontFamily: THEME.heading, fontWeight: 700,
    }}>
      <span style={{ fontSize: w * 0.62, lineHeight: 1 }}>{rank}</span>
      <span style={{ fontSize: w * 0.5, lineHeight: 1 }}>{GLYPH[suit] ?? suit}</span>
    </div>
  );
};
