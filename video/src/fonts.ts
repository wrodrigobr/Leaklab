// Carrega as MESMAS fontes do site (Google Fonts) dentro do Remotion:
// heading = Chakra Petch, body = Space Grotesk, mono = JetBrains Mono.
import { loadFont as loadChakra } from "@remotion/google-fonts/ChakraPetch";
import { loadFont as loadGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const FONT_HEADING = loadChakra("normal", { weights: ["600", "700"] }).fontFamily;
export const FONT_BODY = loadGrotesk("normal", { weights: ["400", "500", "600"] }).fontFamily;
export const FONT_MONO = loadMono("normal", { weights: ["400", "500", "600"] }).fontFamily;
