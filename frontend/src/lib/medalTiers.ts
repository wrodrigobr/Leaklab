/**
 * medalTiers — fonte ÚNICA da escala de tier (bronze/prata/ouro/diamante).
 *
 * ── Por que isto é um módulo e não duas tabelas ───────────────────────────────────────────────
 *
 * As mesmas quatro palavras já apareciam em DOIS lugares da tela de treino: nas barras de
 * "domínio por habilidade" e, agora, nas medalhas de conquista. Duas tabelas de cor com os mesmos
 * nomes viram duas escalas homônimas, e o aluno que vê uma barra dourada e uma medalha dourada
 * assume que medem a mesma coisa. É a dualidade que já custou caro aqui (card discordando do
 * badge sobre a mesma mão).
 *
 * A decisão, e ela já estava declarada no código: **tier é gamificação de ESFORÇO praticado**.
 * Quem decide progressão é o gate de domínio, não o tier. Então existe UMA escala, usada nas duas
 * superfícies, e as cores saem daqui.
 *
 * Os rótulos NÃO moram aqui: vêm do i18n (`training:tiers.*`), porque toda string visível precisa
 * existir em PT/EN/ES.
 */
export const MEDAL_TIERS = ["bronze", "silver", "gold", "diamond"] as const;
export type MedalTier = (typeof MEDAL_TIERS)[number];

/**
 * `light` é o tom que carrega o desenho; `deep` é a sombra do metal.
 *
 * Os valores são os MESMOS que as barras de habilidade já usavam, de propósito: se a medalha de
 * ouro tivesse outro amarelo, as duas superfícies pareceriam escalas diferentes mesmo usando a
 * mesma palavra.
 */
export const TIER_COLORS: Record<MedalTier, { light: string; deep: string }> = {
  bronze:  { light: "#d9a86a", deep: "#8a6636" },
  silver:  { light: "#dfe6ee", deep: "#8f9aa6" },
  gold:    { light: "#f5c542", deep: "#a97d10" },
  diamond: { light: "#7fe0ff", deep: "#2a8fb5" },
};

/** Chave i18n do rótulo do tier. Nunca devolver texto: PT/EN/ES são obrigatórios. */
export const tierLabelKey = (tier: MedalTier) => `tiers.${tier}`;
