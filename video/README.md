# GrindLab Vídeo-aulas (Remotion)

Vídeos de teoria de poker gerados por **código** (Remotion → MP4). Formato: voz + gráficos, sem avatar. Os dados das demonstrações são **reais**, extraídos do banco (ranges GTO keeper + perfis de oponente), nunca inventados.

Piloto: **Módulo 1, Aula 1 — Conceitos (Posição)**.

## Pré-requisitos
- Node 18+ (tem `fetch` global).
- Primeira instalação baixa o Chromium do Remotion (é normal demorar).

## Passo a passo

```bash
cd video
npm install

# 1) Ver/editar no estúdio (preview ao vivo no navegador)
npm run studio

# 2) Renderizar o MP4 (sai em out/aula1-conceitos.mp4)
npm run render
```

O vídeo **renderiza mesmo sem áudio** (as legendas carregam o conteúdo). Quando tiver a voz:

```bash
# 3) Gerar a narração (precisa da chave ElevenLabs)
ELEVENLABS_API_KEY=xxx ELEVENLABS_VOICE_ID=yyy npm run voiceover
# isso cria public/audio/*.mp3 + src/data/audio_manifest.json
# depois é só renderizar de novo: npm run render
```

## Como está montado
- `src/data/aula1_script.json` — **fonte única**: narração + timing + tipo de visual de cada cena. Editar aqui muda o vídeo e a narração juntos.
- `src/data/module1_demos.json` — os **dados reais** (cópia de `backend/scripts/out/module1_demos.json`). Regenerar com `python backend/scripts/build_module1_demos.py 50`.
- `src/components/RangeGrid.tsx` — o range grid 13x13 colorido por frequência real.
- `src/components/Scenes.tsx` — as cenas (título, assentos, IP/OOP, comparação de ranges, exercício, resumo).
- `src/compositions/Aula1Conceitos.tsx` — sequência das cenas + legenda + áudio (quando existir).
- `scripts/generate_voiceover.mjs` — narração via ElevenLabs.

## Multilíngue
Pra EN/ES: duplique `aula1_script.json` trocando `narration` e `caption`, gere a voz com a mesma voz multilíngue, e registre outra Composition. Os gráficos (números) não mudam.

## Ajuste de timing
As durações das cenas (`seconds`) são estimadas. Com áudio real, o `audio_manifest.json` sobrepõe com a duração de cada narração. Se algo cortar, ajuste `seconds` no roteiro ou no manifest.
