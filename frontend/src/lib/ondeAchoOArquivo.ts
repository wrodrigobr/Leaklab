/**
 * Onde fica o arquivo de hand history, por site. FONTE ÚNICA.
 *
 * ── O muro que o onboarding precisa derrubar ──────────────────────────────────────────────────
 *
 * O estado vazio de hoje diz *"faça upload do seu arquivo de hand history (.txt de PokerStars,
 * GGPoker, ACR ou CoinPoker)"*, com o "onde" entre parênteses. Quem chega do Instagram não sabe o
 * que é esse arquivo, muito menos onde ele está, e em alguns sites ele **nem existe** até a pessoa
 * ligar a opção. Esse é o primeiro e maior ponto de desistência, e nenhum tour pela tela o resolve:
 * antes do upload o dashboard é vazio por construção.
 *
 * ── Por que os caminhos daqui são confiáveis ─────────────────────────────────────────────────
 *
 * Os do PokerStars e da ACR foram **verificados numa máquina real** (2026-07-31), não deduzidos:
 * `AppData\Local\PokerStars\HandHistory\<nick>` e `C:\ACR Poker\handHistory\<nick>` existem, com a
 * pasta do jogador dentro. Onde não houve verificação, o campo é `null` e a tela mostra a
 * instrução sem inventar um caminho — caminho errado é pior que caminho ausente, porque manda a
 * pessoa procurar onde não tem e ela conclui que o produto não serve para o site dela.
 */
export type SiteSuportado = "pokerstars" | "ggpoker" | "acr" | "coinpoker";

export interface ComoAcharArquivo {
  /** Caminho verificado numa máquina real, ou null quando não foi possível verificar. */
  caminho: string | null;
  /** O site precisa que a pessoa LIGUE a gravação antes? Muda a primeira instrução. */
  precisaLigar: boolean;
}

export const ONDE_ACHO: Record<SiteSuportado, ComoAcharArquivo> = {
  pokerstars: {
    caminho: "C:\\Users\\<seu usuário>\\AppData\\Local\\PokerStars\\HandHistory\\<seu nick>",
    precisaLigar: true,
  },
  acr: {
    caminho: "C:\\ACR Poker\\handHistory\\<seu nick>",
    precisaLigar: false,
  },
  // Não verificados numa máquina. `null` faz a tela mostrar só a instrução, sem afirmar pasta.
  ggpoker:   { caminho: null, precisaLigar: true },
  coinpoker: { caminho: null, precisaLigar: false },
};

export const SITES: SiteSuportado[] = ["pokerstars", "ggpoker", "acr", "coinpoker"];

export const NOME_DO_SITE: Record<SiteSuportado, string> = {
  pokerstars: "PokerStars",
  ggpoker: "GGPoker",
  acr: "ACR",
  coinpoker: "CoinPoker",
};
