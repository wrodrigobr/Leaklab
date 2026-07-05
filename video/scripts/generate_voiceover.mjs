/**
 * generate_voiceover.mjs — gera a narração de cada cena via ElevenLabs e monta o manifest
 * de áudio que a composição consome. Rode quando tiver a chave.
 *
 *   ELEVENLABS_API_KEY=xxx ELEVENLABS_VOICE_ID=yyy node scripts/generate_voiceover.mjs
 *
 * Saída: public/audio/<id>.mp3  +  src/data/audio_manifest.json
 * Sem a chave, o vídeo renderiza mesmo assim (só com as legendas na tela).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");
const KEY = process.env.ELEVENLABS_API_KEY;
const VOICE = process.env.ELEVENLABS_VOICE_ID;
const MODEL = process.env.ELEVENLABS_MODEL || "eleven_multilingual_v2";

if (!KEY || !VOICE) {
  console.error("Defina ELEVENLABS_API_KEY e ELEVENLABS_VOICE_ID no ambiente.");
  process.exit(1);
}

const script = JSON.parse(fs.readFileSync(path.join(ROOT, "src/data/aula1_script.json"), "utf8"));
const outDir = path.join(ROOT, "public/audio");
fs.mkdirSync(outDir, { recursive: true });

// duração da cena = fala (~14 char/s em PT) + respiro de 2s (ritmo p/ iniciante, não corrido).
const estSeconds = (t) => Math.max(4, Math.round((t.length / 14 + 2.0) * 10) / 10);

const manifest = {};
for (const scene of script.scenes) {
  const text = scene.narration?.trim();
  if (!text) continue;
  console.log(`gerando: ${scene.id} (${text.length} chars)`);
  const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE}`, {
    method: "POST",
    headers: { "xi-api-key": KEY, "Content-Type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify({
      text,
      model_id: MODEL,
      voice_settings: { stability: 0.5, similarity_boost: 0.75, style: 0.1 },
    }),
  });
  if (!res.ok) {
    console.error(`  falhou (${res.status}): ${await res.text()}`);
    process.exit(1);
  }
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(path.join(outDir, `${scene.id}.mp3`), buf);
  manifest[scene.id] = { file: `audio/${scene.id}.mp3`, seconds: estSeconds(text) };
}

fs.writeFileSync(
  path.join(ROOT, "src/data/audio_manifest.json"),
  JSON.stringify(manifest, null, 2)
);
console.log(`\nOK. ${Object.keys(manifest).length} narrações + manifest.`);
console.log("Dica: as durações são estimadas. Se algum áudio cortar, ajuste 'seconds' no manifest (ou use ffprobe pra medir).");
