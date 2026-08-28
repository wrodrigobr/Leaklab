// GERADO por `backend/scripts/gerar_miniaturas_de_treino.py`. NAO editar a mao.
//
// Um caractere por celula da grade 13x13, na ordem de leitura:
//   r = raise   c = call   a = all-in   m = misto   f = fold
//
// Servem de ILUSTRACAO nos cards de treino: o formato da range diz o que o drill e mais
// rapido do que qualquer frase. Nao sao ferramenta de consulta -- para isso existe
// /ranges, com frequencia, combos e os seletores.
export const MINIATURAS_DE_TREINO: Record<string, string> = {
  abrir: "rrrrrrrrrrrrrrrrrrrrrrrrffrrrrrrrrrrfffrrrrrrrrfffffrrrrrrrrfffffrrrrmrrrfffffrfffffrrfffffrffffffrmffffrfffffffrffffrffffffffrfffmfffffffffrffffffffffffffffffffffffffff",
  defender: "rraraccccccccarcccccaaccccaarccccccccccaccarccccccccacccammccccccaccccacccccccccccccaccccccaccccccacccccccccccccaccccaccccccccaccccccccffcccaccccccmfffcccacacccfffffcffa",
  vs_3bet: "ccaccccccccccaccccccccmfffacccccmffffffaccaccfffffffcmmfcccffffffmffffccffffffffffffccffffffffffffacffffffffffffcmffffffffffffcfffffffffffffmfffffffffffffmffffffffffffff",
};
