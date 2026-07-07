// Renderiza em lote os posts do Desafio do Dia (Stories quiz): pra cada spot na fila
// src/data/challenge_queue/*.json, gera a story da PERGUNTA + a story da RESPOSTA.
// O composition lê src/data/short_spot.json no bundle, então trocamos o arquivo por spot.
import { execSync } from "node:child_process";
import { readdirSync, copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join, basename } from "node:path";

const ROOT = process.cwd();
const QUEUE = join(ROOT, "src", "data", "challenge_queue");
const ACTIVE = join(ROOT, "src", "data", "short_spot.json");
const OUT = join(ROOT, "out");

if (!existsSync(QUEUE)) { console.error(`Fila não encontrada: ${QUEUE}`); process.exit(1); }
if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true });

const spots = readdirSync(QUEUE).filter((f) => f.endsWith(".json")).sort();
if (!spots.length) { console.error("Nenhum spot na fila (challenge_queue/*.json)."); process.exit(1); }

console.log(`Renderizando ${spots.length} posts (pergunta + resposta cada)...\n`);
for (const file of spots) {
  const name = basename(file, ".json");           // ex.: dia1
  copyFileSync(join(QUEUE, file), ACTIVE);         // ativa esse spot pro bundle
  for (const [comp, suffix] of [["DailyChallengeQuestion", "pergunta"], ["DailyChallengeReveal", "resposta"]]) {
    const out = join("out", `${name}-${suffix}.mp4`);
    console.log(`  ${name} · ${suffix} ...`);
    execSync(`npx remotion render ${comp} ${out}`, { stdio: "inherit" });
  }
}
console.log("\nPronto. Vídeos em video/out/ (diaN-pergunta.mp4 + diaN-resposta.mp4).");
