"""
academy_questions.py — exercícios que exigem DECIDIR, não lembrar.

Por que este módulo existe (auditoria de 2026-07-28): doze aulas da Academia tinham 3 perguntas
fixas cada, com distratores que se descartam sozinhos ("é igual em qualquer posição", "você tem
qualquer Ás"). Isso testa leitura, não poker, e o jogador percebe em três exercícios.

A régua daqui:

  1. toda alternativa errada é uma crença que jogador real tem;
  2. a resposta certa costuma ser a CONTRAINTUITIVA;
  3. a explicação ensina o princípio transferível, não o gabarito daquele spot;
  4. se dá para acertar sem saber a matéria, o exercício não vale a vaga.

Ficam separados de `academy.py` porque aquele arquivo já passa de 2900 linhas e porque a régua
acima é o que os une, não a aula a que pertencem.

Os `correct_index` aqui podem ser quaisquer: `academy.shuffle_options` embaralha na entrega. Antes
dela, 54 das 59 perguntas tinham a resposta na posição 0 e o quiz era vencível sem ler.
"""
from __future__ import annotations

import random


def _q(tipo: str, pergunta: str, opcoes: list[str], certa: int,
       explicacao: str, dica: str, xp: int = 25) -> dict:
    return {
        'type': tipo, 'question': pergunta, 'options': opcoes, 'correct_index': certa,
        'explanation': explicacao, 'mental_tip': dica, 'context': {}, 'xp_value': xp,
    }


# ── Blind vs blind ────────────────────────────────────────────────────────────────────────────

def bvb_postflop_position() -> dict:
    return _q(
        'bvb_postflop_position',
        'SB abre, BB paga, e os dois vão ao flop. Quem age primeiro no pós-flop?',
        ['O SB, então quem tem posição no pós-flop é o BB',
         'O BB, porque o BB sempre age primeiro',
         'Alterna a cada street'],
        0,
        'No pré-flop o SB age antes do BB, mas no pós-flop a ordem segue o botão, e o SB é o '
        'primeiro assento depois dele. Ou seja, em blind vs blind o BB tem POSIÇÃO, a única '
        'situação em que isso acontece. É por causa disso que o BB pode pagar bem mais largo aqui '
        'do que contra um open de qualquer outra posição.',
        '**Blind vs blind é a única vez em que o BB tem posição. Defenda mais largo por isso.**')


def bvb_defense_price() -> dict:
    return _q(
        'bvb_defense_price',
        'SB abre para 3bb e você está no BB. Fora a equity da sua mão, o que mais justifica '
        'defender largo?',
        ['Você tem posição no pós-flop e o range de abertura do SB é largo por obrigação',
         'Porque você já postou 1bb, e essa ficha precisa ser defendida',
         'Porque o SB só abre com mão forte, então o pote vale mais'],
        0,
        'Dois motivos somam. O SB é obrigado a abrir largo, porque só há um jogador atrás e foldar '
        'demais entregaria os blinds de graça; e o BB joga o pós-flop em posição, o que aumenta a '
        'equity que ele consegue realizar. Defender "porque já paguei" é custo afundado: aquele bb '
        'não é mais seu, é do pote, e não entra na conta.',
        '**Defender é por preço e posição, nunca por já ter postado.**')


def bvb_limp() -> dict:
    return _q(
        'bvb_limp',
        'Por que completar (limpar) do SB faz parte de estratégia sólida, enquanto limpar de '
        'qualquer outra posição é erro?',
        ['Porque só resta um jogador para agir, então limpar não convida vários adversários ao pote',
         'Porque o SB tem posição no pós-flop e controla o tamanho do pote',
         'Porque limpar esconde a força da mão'],
        0,
        'O problema clássico do limp é dar preço barato para muita gente entrar, e pote multiway '
        'destrói o valor de mãos medianas. No SB isso não existe: falta um jogador só. Por isso a '
        'estratégia de solver mantém um range de complete no SB em várias profundidades. O SB '
        'segue FORA de posição no pós-flop, então não é isso que justifica, e esconder força não '
        'justifica linha nenhuma.',
        '**Limp só se defende onde não convida multiway. Isso só acontece no SB.**')


def bvb_3bet() -> dict:
    return _q(
        'bvb_3bet',
        'BB contra open do SB. Comparado a enfrentar um open do UTG, o seu range de 3-bet aqui '
        'deve ser:',
        ['Mais largo, porque o range dele é muito mais fraco e você tem posição nos potes que ele pagar',
         'Igual, porque o range de 3-bet depende da sua mão',
         'Mais apertado, porque em blind vs blind os stacks efetivos ficam altos'],
        0,
        'A força de um 3-bet não sai da sua mão isolada, sai do confronto entre ranges. O SB abre '
        'muito mais largo que o UTG, então a mesma mão fica bem melhor aqui. E como você tem '
        'posição no pós-flop, os potes que ele paga são mais fáceis de jogar. Tratar o range de '
        '3-bet como lista fixa de mãos, igual em todo spot, é exatamente o erro que esta pergunta '
        'expõe.',
        '**3-bet é sobre o range dele, não sobre uma lista fixa da sua mão.**')


# ── Posição ───────────────────────────────────────────────────────────────────────────────────

def pos_realization_gap() -> dict:
    return _q(
        'pos_realization_gap',
        'Mão A tem 54% de equity e joga fora de posição. Mão B tem 50% e joga em posição. Qual '
        'costuma render mais fichas no longo prazo?',
        ['A mão B, porque em posição você realiza uma fatia maior da equity que tem',
         'A mão A, porque equity é equity e 54 é maior que 50',
         'Depende só de quem apostar primeiro no flop'],
        0,
        'Equity é quanto você ganharia se todas as cartas saíssem sem mais apostas. O que entra no '
        'seu bolso é a equity REALIZADA, e a posição é o maior fator dela: agindo por último você '
        'folda mais barato quando erra, extrai mais quando acerta e controla o tamanho do pote. '
        'Fora de posição, uma vantagem de poucos pontos evapora nas decisões difíceis que você é '
        'obrigado a tomar primeiro.',
        '**Equity é o que você tem. Realização é o que você leva. A posição decide a diferença.**',
        xp=30)


def pos_coldcall() -> dict:
    return _q(
        'pos_coldcall',
        'UTG abre e você tem JTs. Em qual assento essa mão vale MENOS como call?',
        ['No HJ, com CO, botão e blinds ainda por agir atrás',
         'No botão, com só os blinds atrás',
         'É a mesma coisa, o open foi do UTG nos dois casos'],
        0,
        'Pagar com gente atrás traz dois problemas que não existem no botão: alguém pode dar '
        'squeeze e te obrigar a abandonar o investimento, e mesmo sem squeeze você pode acabar '
        'jogando o pote fora de posição contra quem entrar depois. No botão você fecha a ação com '
        'quase todos já fora e garante posição. A mesma mão, contra o mesmo open, muda de valor '
        'conforme quantas cadeiras faltam.',
        '**Contar quem falta agir atrás vale mais que olhar quem abriu.**')


def pos_steal_target() -> dict:
    return _q(
        'pos_steal_target',
        'Você está no botão pensando em roubar os blinds. Qual informação muda mais a decisão?',
        ['Com que frequência aquele BB específico defende, porque é ele quem fecha a ação',
         'A força exata da sua mão dentro do range de roubo',
         'Quantas mãos você já ganhou nessa órbita'],
        0,
        'O roubo é rentável quando os blinds foldam o suficiente, e quem fecha a ação é o BB. Um BB '
        'que defende 60% transforma o seu open largo em prejuízo; um que defende 25% faz quase '
        'qualquer duas cartas valerem. A sua mão importa, mas dentro do range de roubo a diferença '
        'entre uma e outra é pequena perto do impacto de quem está no BB.',
        '**Roubo se decide olhando quem defende, não a sua mão.**')


def pos_oop_bluff() -> dict:
    return _q(
        'pos_oop_bluff',
        'Por que blefar em várias streets FORA de posição é bem mais caro que blefar em posição?',
        ['Porque você aposta sem saber o que ele fará, e ele pode só pagar e te obrigar a decidir '
         'de novo no escuro na street seguinte',
         'Porque fora de posição as suas mãos são estatisticamente piores',
         'Porque quem está em posição sempre paga mais'],
        0,
        'Em posição, o blefe recebe informação antes de continuar: se ele checar de novo, você '
        'decide sabendo mais. Fora de posição, cada barril é tomado no escuro, e o adversário tem a '
        'opção barata de só pagar e te deixar sangrando por duas ou três streets. É por isso que os '
        'solvers blefam bem menos multi-street OOP, e por isso o custo de estar fora de posição '
        'aparece justamente nas mãos que você queria transformar em blefe.',
        '**Blefe OOP paga o pedágio da informação em toda street.**')


# ── 3-bet ─────────────────────────────────────────────────────────────────────────────────────

def tb_size() -> dict:
    return _q(
        'tb_size',
        'Você vai dar 3-bet. Em qual situação o tamanho deve ser MAIOR?',
        ['Fora de posição, para cobrar caro de quem teria a vantagem posicional no pós-flop',
         'Em posição, para aproveitar a vantagem e construir o pote',
         'O tamanho não muda com a posição, muda só com o stack'],
        0,
        'Fora de posição você quer duas coisas: reduzir quantos adversários continuam e evitar '
        'jogar potes grandes agindo primeiro. Um 3-bet maior faz as duas. Em posição é o contrário: '
        'tamanho menor convida mais calls, e você fica feliz de jogar mais potes com vantagem '
        'posicional. Daí a régua clássica de cerca de 3x o open em posição e 4x fora dela.',
        '**3-bet maior fora de posição. Você compra o direito de não jogar OOP.**')


def tb_flat() -> dict:
    return _q(
        'tb_flat',
        'Você tem QQ no botão, o CO abre e os blinds parecem soltos. Quando pagar pode bater '
        '3-betar?',
        ['Quando manter os blinds no pote com mãos piores rende mais que isolar o CO, e você joga '
         'tudo em posição',
         'Nunca, QQ sempre 3-beta',
         'Quando você quer esconder que tem mão forte'],
        0,
        'O 3-bet isola e limpa o pote, ótimo contra um range de open. Mas quando há jogadores '
        'fracos atrás dispostos a entrar, deixar o pote multiway com uma mão forte que joga bem em '
        'posição pode render mais fichas do que ganhar um pote pequeno na hora. Não é sobre '
        'esconder força: é uma escolha entre isolar e faturar de mais gente, e ela depende de quem '
        'está atrás.',
        '**3-bet isola. Call convida. A escolha depende de quem você quer no pote.**',
        xp=30)


def tb_squeeze() -> dict:
    return _q(
        'tb_squeeze',
        'UTG abre e o HJ paga. Você está no botão. Por que o squeeze funciona bem aqui, mesmo com '
        'mãos que não seriam 3-bet contra um open sozinho?',
        ['Porque quem só pagou um open quase nunca tem o topo do range, e o abridor ainda enfrenta '
         'gente viva atrás, então os dois desistem com frequência alta',
         'Porque o pote já está grande e vale a pena arriscar',
         'Porque quem paga um open normalmente tem mão fraca'],
        0,
        'O squeeze ataca uma fraqueza estrutural: quem apenas pagou raramente tem mão muito forte, '
        'porque com as melhores ele teria 3-betado. Some que o abridor agora enfrenta um raise com '
        'um jogador ainda vivo entre vocês, e você tem duas chances de levar o pote na hora. É o '
        'FORMATO do range dele, não o tamanho do pote, que faz a jogada.',
        '**Quem só paga um open tem range sem topo. É isso que o squeeze explora.**',
        xp=30)


def tb_vs4bet() -> dict:
    return _q(
        'tb_vs4bet',
        'Você deu 3-bet com A5s como blefe e levou 4-bet. Por que essa mão é candidata melhor a '
        'continuar do que, digamos, 87s?',
        ['Porque o Ás reduz as combinações de AA, AK e AQ que ele pode ter, e ainda sobra equity '
         'contra pares',
         'Porque A5s tem mais equity bruta que 87s contra qualquer mão',
         'Porque mão suited com Ás não se folda'],
        0,
        'Contra um range de 4-bet, o que mais importa não é equity bruta e sim quais mãos você '
        'impede que ele tenha. Segurar um Ás corta combinações de AA, AK e AQ, o que muda de '
        'verdade o formato do range dele. Some o potencial de fazer nuts com a roda e a suitedness, '
        'e A5s vira o blefe padrão. 87s tem equity razoável, mas não bloqueia nada do que importa.',
        '**Contra 4-bet, blefe com o que BLOQUEIA o topo dele, não com o que tem mais equity.**',
        xp=30)


# ── Barrel ────────────────────────────────────────────────────────────────────────────────────

def tr_card_choice() -> dict:
    return _q(
        'tr_card_choice',
        'Você apostou no flop K72 rainbow e foi pago. Em qual turn o segundo barril é melhor?',
        ['Um A ou um Q, cartas que melhoram o SEU range de abertura mais que o range de call dele',
         'Um 2 ou um 7, porque emparelham o board e assustam',
         'Qualquer carta baixa, porque não ajuda ninguém'],
        0,
        'A pergunta certa no turn não é "essa carta me ajudou?", é "essa carta ajuda mais o meu '
        'range ou o dele?". Você abriu o pote, então tem muito mais Ás e Dama que alguém que só '
        'pagou uma aposta em K72. Quando essas cartas caem, a sua história é crível e a dele fica '
        'difícil. Cartas que emparelham o board costumam ajudar mais quem pagou, e cartas baixas '
        'não movem nada.',
        '**Barril bom é o que melhora o SEU range, não a sua mão.**',
        xp=30)


def tr_giveup_choice() -> dict:
    return _q(
        'tr_giveup_choice',
        'Você blefou o flop e o turn com dois projetos e errou tudo no river. Entre suas mãos '
        'mortas, qual é a MELHOR para blefar no river?',
        ['A que bloqueia as mãos com que ele pagaria, mesmo que ela não tenha equity nenhuma',
         'A que tem mais chance de ganhar no showdown, para ter duas formas de vencer',
         'A que tem a carta mais alta, para ganhar se ele também não tiver nada'],
        0,
        'No river não existe mais equity, só duas perguntas: com que ele paga e o que a sua mão '
        'impede que ele tenha. Blefar com a mão que ainda ganharia alguma coisa é queimar valor de '
        'showdown; blefar com a que bloqueia os calls dele aumenta a chance de o blefe passar. Por '
        'isso o blefe de river ideal é a mão mais morta possível que segure as cartas certas.',
        '**No river, blefe com a mão mais morta que bloqueie os calls dele.**',
        xp=30)


def tr_sizing_polar() -> dict:
    return _q(
        'tr_sizing_polar',
        'Por que apostas grandes em turn e river costumam vir com um range POLARIZADO?',
        ['Porque só mãos muito fortes e blefes puros lucram cobrando caro, mãos medianas preferem '
         'chegar barato ao showdown',
         'Porque aposta grande sempre gera mais fold equity',
         'Porque com mão mediana você quer construir o pote'],
        0,
        'Um tamanho grande separa naturalmente o range: com mão muito forte você quer o pote máximo, '
        'com blefe puro você precisa de fold equity máxima, e mão mediana não quer nenhuma das duas, '
        'ela quer showdown barato. Apostar grande com mão mediana só constrói pote para ser pago por '
        'algo melhor e foldado por tudo pior. É o erro que transforma valor em prejuízo.',
        '**Tamanho grande é para nuts e blefe. Mão mediana quer showdown barato.**',
        xp=30)


def tr_range_advantage() -> dict:
    return _q(
        'tr_range_advantage',
        'O flop veio A K 7. Você abriu do UTG e o BB pagou. Por que você aposta com quase todo o '
        'seu range aqui?',
        ['Porque o seu range tem muito mais AK, AQ e AJ do que o dele, que teria 3-betado essas mãos',
         'Porque board com Ás sempre favorece quem apostou por último',
         'Porque o BB quase nunca acerta um flop assim'],
        0,
        'A vantagem não vem do board em si, vem de como ele interage com os DOIS ranges. Você abriu '
        'de UTG, então tem uma concentração enorme de mãos que ligam com A e K. O BB, que só pagou, '
        'já 3-betaria a maior parte dessas mesmas mãos, então o topo do range dele está capado. Com '
        'essa diferença, apostar barato com quase tudo lucra, porque ele não tem como te punir com '
        'frequência.',
        '**Aposte com o range quando o topo dele estiver capado. Isso é vantagem de range.**',
        xp=30)


# ── Projetos ──────────────────────────────────────────────────────────────────────────────────

def draw_odds() -> dict:
    """DINÂMICO: outs viram equity e equity vira decisão. Números novos a cada chamada.

    O distrator principal é a regra do 4 aplicada quando ela não vale: multiplicar por 4 supõe ver
    DUAS cartas, o que só acontece se você for all-in agora. Enfrentando aposta no flop com stack
    atrás, a conta certa é por UMA carta."""
    outs = random.choice([8, 9, 12, 13, 15])
    pote = random.choice([6, 8, 10, 12, 14])
    aposta = random.choice([3, 4, 5, 6])
    preco = aposta / (pote + aposta + aposta)
    por_uma = outs * 2
    por_duas = outs * 4
    nome = {8: 'straight draw aberto', 9: 'flush draw', 12: 'flush draw com gutshot',
            13: 'flush draw com par', 15: 'flush draw com straight draw'}[outs]
    return _q(
        'draw_odds',
        f'Flop. Você tem {nome} ({outs} outs) e o vilão aposta {aposta}bb num pote de {pote}bb. '
        f'Sobra stack para as duas ruas. Qual equity você deve usar para decidir o call AGORA?',
        [f'Cerca de {por_uma}%, contando só a próxima carta',
         f'Cerca de {por_duas}%, contando turn e river',
         f'{outs} outs sempre valem 50%, é coin flip'],
        0,
        f'A regra do 4 vale quando você vai ver as DUAS cartas sem pagar de novo, ou seja, quando '
        f'está all-in. Aqui você paga o turn e pode ter que pagar o river também, então a decisão '
        f'de agora é sobre UMA carta: {outs} outs valem cerca de {por_uma}%. Você precisa de '
        f'{preco * 100:.0f}% pelo preço do pote, e o que fecha a conta é o que sobra em implied '
        f'odds. Usar {por_duas}% aqui é o erro que faz projeto pagar caro demais.',
        '**Regra do 4 só quando for all-in. Enfrentando aposta com stack atrás, use a do 2.**',
        xp=30)


def draw_implied_fake() -> dict:
    return _q(
        'draw_implied_fake',
        'Você tem flush draw e o preço não fecha sozinho. Em qual situação as implied odds NÃO '
        'salvam o call?',
        ['Quando os stacks são curtos, porque não sobra dinheiro para você ganhar se acertar',
         'Quando o vilão é agressivo, porque ele vai apostar de novo',
         'Quando o board tem cartas altas, porque ele pode ter mão forte'],
        0,
        'Implied odds são o dinheiro que você espera GANHAR DEPOIS de acertar. Se o stack atrás é '
        'pequeno, esse dinheiro simplesmente não existe, e o call precisa fechar pelo preço direto. '
        'Vilão agressivo, ao contrário, costuma AUMENTAR as implied odds, porque ele mesmo põe '
        'fichas no pote. É a matemática mais ignorada em stack curto, e a razão de tanto projeto '
        'pago virar prejuízo em MTT.',
        '**Sem stack atrás não há implied odds. O preço tem que fechar sozinho.**',
        xp=30)


def draw_which_bluff() -> dict:
    return _q(
        'draw_which_bluff',
        'Você tem dois projetos e quer semi-blefar com um só. Qual escolher?',
        ['O que tem menos valor de showdown, guardando o outro para chegar barato ao river',
         'O mais forte, porque tem mais equity se for pago',
         'Tanto faz, os dois têm equity parecida'],
        0,
        'Semi-blefe transforma em fichas a equity de uma mão que, sozinha, quase nunca ganharia no '
        'showdown. Quando você blefa com o projeto mais forte, joga fora a chance de simplesmente '
        'chegar barato e ganhar. Guardar as mãos com algum valor de showdown para check-call e '
        'blefar com as mortas é o que faz o range inteiro render, em vez de uma mão isolada.',
        '**Blefe com o projeto mais morto. Guarde o que ainda ganharia sozinho.**',
        xp=30)


def draw_multiway() -> dict:
    return _q(
        'draw_multiway',
        'Você tem flush draw num pote de quatro jogadores. Comparado ao heads-up, o que muda?',
        ['O semi-blefe piora, porque é muito mais difícil que TODOS foldem, mas o preço para pagar '
         'melhora, porque há mais gente pagando',
         'Melhora tudo, porque o pote está maior',
         'Piora tudo, porque mais gente pode ter mão melhor'],
        0,
        'Multiway separa as duas fontes de lucro em direções opostas. A fold equity despenca: '
        'precisar que três pessoas desistam é muito mais difícil que uma. Mas as pot odds melhoram, '
        'porque cada jogador extra engorda o pote que você leva ao acertar. Por isso a jogada '
        'multiway com projeto costuma ser pagar bem, não blefar. Quem trata "pote maior" como bom '
        'para tudo perde justamente aqui.',
        '**Multiway mata a fold equity e melhora o preço. Pague mais, blefe menos.**',
        xp=30)


# ── Exploit ───────────────────────────────────────────────────────────────────────────────────

def exploit_sample() -> dict:
    return _q(
        'exploit_sample',
        'Você viu um jogador foldar o BB três vezes seguidas. Qual a conclusão correta?',
        ['Nenhuma ainda: três mãos não distinguem um jogador apertado de um que recebeu lixo',
         'Ele folda demais, ataque com qualquer duas cartas',
         'Ele está esperando mão forte, aperte contra ele'],
        0,
        'Um jogador com defesa perfeitamente normal folda o BB umas duas vezes a cada três de '
        'qualquer jeito, então três folds seguidos acontecem o tempo todo por puro acaso. Ajustar '
        'com base nisso é ler ruído, e o custo do exploit errado é maior que o do exploit não '
        'feito. Leitura comportamental precisa de dezenas de observações da MESMA situação para '
        'valer alguma coisa.',
        '**Exploit com amostra pequena é achismo caro. Sem amostra, jogue o padrão.**',
        xp=30)


def exploit_overfolder() -> dict:
    return _q(
        'exploit_overfolder',
        'Você identificou com amostra sólida que um vilão folda demais no river. Como explorar?',
        ['Blefe mais e faça MENOS value bet fina, porque as mãos medianas dele não pagam mais',
         'Blefe mais e faça mais value bet fina, aproveitando tudo',
         'Só blefe mais, o value bet não muda'],
        0,
        'Quem folda demais no river está foldando exatamente as mãos medianas que pagariam a sua '
        'value bet fina. Então o mesmo desvio abre uma porta e fecha outra: os blefes passam mais, '
        'e as apostas finas de valor deixam de ser pagas por pior, passando a ser pagas só por '
        'melhor. Explorar bem é ajustar as DUAS pontas, não só a mais divertida.',
        '**Contra quem folda demais: mais blefe e MENOS value fina. O desvio corta dos dois lados.**',
        xp=30)


def exploit_cost() -> dict:
    return _q(
        'exploit_cost',
        'Qual o custo real de fazer um ajuste exploitativo baseado numa leitura ERRADA?',
        ['Você fica desbalanceado sem ganhar nada em troca, e vira alvo fácil de quem observa',
         'Nenhum, porque o GTO é apenas um dos jogos possíveis',
         'Pequeno, porque exploits sempre rendem mais que jogar equilibrado'],
        0,
        'Todo exploit é uma troca: você abre mão de estar equilibrado para lucrar de um desvio '
        'específico do adversário. Se o desvio não existe, você pagou o preço sem receber nada, e '
        'ainda ficou previsível para quem estiver prestando atenção. É por isso que o padrão '
        'sólido é o ponto de partida, e o exploit só entra quando a evidência sustenta.',
        '**Exploit é uma aposta. Sem leitura confiável, você paga o preço sem o prêmio.**',
        xp=30)


def exploit_limper() -> dict:
    return _q(
        'exploit_limper',
        'Um jogador fraco limpa muito de posição inicial. Qual a exploração mais rentável?',
        ['Isolar com raise, em posição e com range largo, para jogar potes heads-up contra ele',
         'Limpar atrás para ver flop barato junto',
         'Esperar mão premium para punir de vez'],
        0,
        'O limp dele entrega duas coisas: um range fraco e fichas mortas no pote. O jeito de '
        'converter isso em dinheiro é isolar, ficar heads-up e usar a posição em todas as streets '
        'seguintes. Limpar atrás desperdiça a vantagem e convida mais gente; esperar mão premium '
        'joga fora quase todas as oportunidades, que é o erro mais comum contra jogador fraco.',
        '**Contra limper fraco: isole em posição. Esperar premium é deixar dinheiro na mesa.**',
        xp=30)


# ── Desequilíbrios ────────────────────────────────────────────────────────────────────────────

def imb_capped() -> dict:
    return _q(
        'imb_capped',
        'O vilão checou flop e turn num board seco. O que significa dizer que o range dele está '
        '"capado"?',
        ['Que ele quase não tem mãos muito fortes, porque teria apostado com elas em algum momento',
         'Que ele tem poucas mãos no range, porque foldou muito antes',
         'Que ele só tem mãos fracas e vai foldar tudo'],
        0,
        'Capado quer dizer sem topo: as mãos muito fortes teriam apostado, então o que sobra tem um '
        'teto. Isso não significa que ele só tem lixo, ele ainda tem pares medianos que pagam. A '
        'consequência prática é que você pode apostar grande com muito mais liberdade, porque o '
        'risco de encontrar a mão que te quebra caiu bastante.',
        '**Capado é sem topo, não sem mão. Ataque o teto, não espere fold de tudo.**',
        xp=30)


def imb_overbet() -> dict:
    return _q(
        'imb_overbet',
        'Quando o overbet (apostar mais que o pote) é a jogada correta?',
        ['Quando você tem mais mãos NUT que ele naquele board, e o range dele está capado',
         'Quando você quer que ele folde e o pote está pequeno',
         'Quando você tem uma mão forte e quer o máximo de valor'],
        0,
        'Overbet não é sobre ter mão forte, é sobre a distribuição dos dois ranges. Ele lucra quando '
        'você tem mãos que ele simplesmente NÃO pode ter, e ele não tem como continuar sem risco de '
        'estar contra a nuts. Se os dois ranges são parecidos no topo, o overbet vira uma aposta '
        'cara que só é paga quando você está atrás. Ter mão forte, sozinho, não basta.',
        '**Overbet exige vantagem de NUTS, não só mão forte.**',
        xp=30)


def imb_bluff_ratio() -> dict:
    return _q(
        'imb_bluff_ratio',
        'Você aposta o river. Comparando um tamanho pequeno e um tamanho grande, qual permite mais '
        'BLEFES no seu range?',
        ['O grande, porque ele oferece um preço pior para o call e sustenta mais blefes por mão de valor',
         'O pequeno, porque é mais barato blefar',
         'Os dois igual, o tamanho não altera a proporção'],
        0,
        'A proporção sai do preço que você oferece: quanto maior a aposta, melhor o preço que o pote '
        'dá ao seu blefe, e mais blefes o range aguenta sem ficar explorável. Um tamanho pequeno '
        'convida call barato, então suporta poucos blefes. Blefar mais só porque a aposta é barata '
        'é exatamente o inverso do que a matemática pede.',
        '**Aposta grande sustenta mais blefe. Aposta pequena, menos. O preço é que manda.**',
        xp=30)


def imb_check_range() -> dict:
    return _q(
        'imb_check_range',
        'Por que é importante ter mãos FORTES no seu range de check no flop?',
        ['Porque sem elas o seu check anuncia fraqueza, e o vilão pode apostar impunemente',
         'Porque assim você ganha mais potes pequenos',
         'Porque mão forte deve sempre dar slow play'],
        0,
        'Se todo check seu significa mão fraca, o adversário aposta sempre e você não tem defesa. '
        'Manter algumas mãos fortes na linha de check faz o check virar uma linha com dentes, o que '
        'protege todas as suas mãos médias e fracas. Não é slow play por gosto: é a proteção do '
        'range inteiro, e é a diferença entre um check que passa e um check que é atacado toda vez.',
        '**Check sem mão forte é bandeira branca. Proteja a linha, não a mão.**',
        xp=30)


# ── PKO ───────────────────────────────────────────────────────────────────────────────────────

def pko_call_gap() -> dict:
    return _q(
        'pko_call_gap',
        'Num PKO, um jogador que você COBRE dá shove. Comparado a um torneio normal, seu call deve '
        'ser:',
        ['Mais largo, porque além do pote você fatura o bounty dele se ganhar',
         'Mais apertado, porque perder fichas num PKO custa mais',
         'Igual, porque o bounty não muda a equity da mão'],
        0,
        'O bounty é dinheiro que entra somente se você eliminar o jogador, e você só pode eliminar '
        'quem cobre. Isso funciona como um prêmio extra pago ao vencedor daquele confronto, então a '
        'equity que o call precisa cai. É o ajuste mais importante do formato, e o mais ignorado: '
        'muita gente joga PKO com range de torneio normal e deixa bounty na mesa a torneio inteiro.',
        '**Cobrindo o adversário, o bounty baixa a equity exigida. Pague mais largo.**',
        xp=30)


def pko_bounty_size() -> dict:
    return _q(
        'pko_bounty_size',
        'O mesmo shove de 12bb, o mesmo adversário. Em qual caso você paga mais largo?',
        ['Quando o bounty dele vale muito em relação ao pote, por exemplo metade de um buy-in num '
         'pote pequeno',
         'Quando o pote já está grande, porque aí compensa mais',
         'O tamanho do bounty não muda o range de call'],
        0,
        'O ajuste é proporcional: o que importa é o bounty COMPARADO ao pote em disputa. Um bounty '
        'gordo num pote pequeno muda drasticamente a conta, porque o prêmio extra pesa mais que as '
        'fichas. Num pote já grande, o mesmo bounty representa uma fração menor e mexe pouco. Tratar '
        'o ajuste como fixo é o erro de quem decorou "em PKO paga mais largo" sem entender por quê.',
        '**O que conta é o bounty EM RELAÇÃO ao pote, não o bounty em si.**',
        xp=30)


def pko_target() -> dict:
    return _q(
        'pko_target',
        'Você tem 40bb. Na mesa há um jogador com 8bb e outro com 60bb, ambos com bounty igual. '
        'Contra quem vale mais construir potes?',
        ['Contra o de 8bb, porque você o cobre e pode faturar o bounty dele',
         'Contra o de 60bb, porque o pote potencial é maior',
         'Tanto faz, o bounty é o mesmo nos dois'],
        0,
        'Bounty só é pago a quem elimina, e você não pode eliminar quem tem mais fichas que você. '
        'Contra o de 60bb, o bounty dele está fora do seu alcance naquele confronto, e você ainda '
        'arrisca o seu próprio. Contra o curto, cada confronto é uma chance real de faturar. É por '
        'isso que a dinâmica de PKO gira em torno de cobrir, e não do tamanho do pote.',
        '**Você só fatura o bounty de quem cobre. É isso que escolhe o alvo.**',
        xp=30)


def pko_late() -> dict:
    return _q(
        'pko_late',
        'Por que perto da mesa final de um PKO o ajuste por bounty costuma DIMINUIR?',
        ['Porque os saltos de premiação ficam grandes e a pressão de ICM passa a pesar mais que o bounty',
         'Porque os bounties já foram quase todos coletados',
         'Porque com poucos jogadores ninguém cobre ninguém'],
        0,
        'O bounty continua valendo o mesmo, mas ele deixa de ser o maior número em jogo: perto do '
        'fim, cada posição vale saltos de premiação altos, e ser eliminado custa muito mais do que '
        'custava no meio do torneio. Quando o ICM cresce, ele domina o ajuste de bounty. Continuar '
        'pagando largo por bounty na mesa final é trocar um prêmio pequeno por um risco grande.',
        '**No fim, ICM vence bounty. O ajuste encolhe justamente quando você mais quer usá-lo.**',
        xp=30)


# ── Valor de showdown ─────────────────────────────────────────────────────────────────────────

def sdv_bluff_pick() -> dict:
    return _q(
        'sdv_bluff_pick',
        'Você chegou ao river com Ás-alto sem par e com 7-alto sem par. Qual usar como blefe?',
        ['O 7-alto, porque o Ás-alto ainda ganha de alguns blefes dele no showdown',
         'O Ás-alto, porque tem mais chance de ganhar se ele pagar',
         'Qualquer um, os dois perdem para qualquer par'],
        0,
        'Blefar com uma mão que ainda ganharia às vezes é gastar duas vezes: você perde o pote que '
        'poderia levar de graça e ainda arrisca fichas. O 7-alto não ganha de nada, então o único '
        'valor que ele tem é o de fazer o adversário desistir. Escolher o blefe pelo que a mão NÃO '
        'vale é uma das ideias que mais separam níveis no river.',
        '**Blefe com o que não ganha nada. Guarde o que ainda ganha de blefe.**',
        xp=30)


def sdv_thin_value() -> dict:
    return _q(
        'sdv_thin_value',
        'Você tem par de meio no river. Quando apostar por valor magro bate checar atrás?',
        ['Quando existem mãos piores que pagam com frequência suficiente para cobrir as vezes em '
         'que você é pago por melhor',
         'Sempre, porque par de meio é mão feita',
         'Nunca, par de meio é mão de showdown'],
        0,
        'Value bet fina se justifica por uma conta simples: entre as mãos que pagam, quantas são '
        'piores que a sua? Se a maioria dos calls vem de pior, aposte. Se ele só paga com melhor e '
        'folda todo o resto, você está apostando para ser pago apenas quando está atrás, o que é '
        'pior que checar. Nem regra fixa de sempre nem de nunca resolve, o que resolve é olhar o '
        'range de call dele.',
        '**Value fina se decide pelo range que PAGA, não pela força da sua mão.**',
        xp=30)


def sdv_bluffcatch() -> dict:
    return _q(
        'sdv_bluffcatch',
        'Você tem um bluff-catcher no river e precisa decidir o call. O que mais importa?',
        ['Quantos blefes ele consegue ter naquela linha, e não o quão forte a sua mão parece',
         'Se a sua mão é boa o suficiente para pagar',
         'Se você já perdeu muitos potes na sessão'],
        0,
        'Bluff-catcher, por definição, só ganha de blefe. Então a força relativa da sua mão dentro '
        'dos bluff-catchers é irrelevante: par de nove e par de dama ganham exatamente do mesmo '
        'conjunto de mãos. A pergunta é sobre ELE: aquela linha comporta blefes suficientes? Se '
        'ele nunca blefa ali, todo bluff-catcher folda, por melhor que pareça.',
        '**Bluff-catcher só ganha de blefe. Conte os blefes dele, não a força da sua mão.**',
        xp=30)


def sdv_protect() -> dict:
    return _q(
        'sdv_protect',
        'Você tem top pair num flop com muitos projetos. Por que apostar bate checar, mesmo sem '
        'esperar call de mão pior?',
        ['Porque negar a equity dos projetos vale fichas: cada mão que folda tinha chance de te '
         'ultrapassar de graça',
         'Porque top pair é sempre mão de aposta',
         'Porque assim você descobre onde está na mão'],
        0,
        'Nem toda aposta é por valor ou blefe. Num board molhado, deixar o adversário ver a próxima '
        'carta de graça entrega equity que era sua: mãos que teriam foldado passam a ganhar às '
        'vezes. Isso se chama negação de equity, e sozinho já justifica apostar mesmo quando quase '
        'nada pior paga. Apostar "para descobrir onde está" é o inverso, é pagar para receber '
        'informação de qualidade duvidosa.',
        '**Negar equity é motivo suficiente. Board molhado, aposte mesmo sem call de pior.**',
        xp=30)


# ── Bankroll ──────────────────────────────────────────────────────────────────────────────────

def bk_downswing() -> dict:
    """DINÂMICO: números diferentes a cada chamada, e a conclusão é sempre desconfortável."""
    campo = random.choice([180, 300, 500, 1000])
    itm = 15
    torneios = random.choice([100, 200, 300])
    seca = int(torneios * 0.6)
    return _q(
        'bk_downswing',
        f'Você joga MTT de {campo} entradas, com cerca de {itm}% de ITM. Numa amostra de '
        f'{torneios} torneios, uma sequência de {seca} sem prêmio nenhum é:',
        ['Perfeitamente normal, MTT tem variância enorme e sequências assim acontecem com jogador vencedor',
         'Sinal claro de que algo está errado no seu jogo',
         'Praticamente impossível, indica que o campo está mais forte'],
        0,
        f'Com {itm}% de ITM, você fica fora do prêmio em {100 - itm}% dos torneios. Sequências '
        f'longas sem prêmio não são exceção, são o formato: a maior parte do retorno em MTT vem de '
        f'poucos resultados grandes, e eles chegam agrupados de forma imprevisível. Ler downswing '
        f'como diagnóstico técnico é a causa mais comum de jogador vencedor abandonar uma '
        f'estratégia correta, ou subir de limite na hora errada tentando recuperar.',
        '**Downswing longo em MTT é o normal, não um sintoma. Diagnóstico vem do jogo, não do saldo.**',
        xp=30)


def bk_roi_sample() -> dict:
    return _q(
        'bk_roi_sample',
        'Depois de quantos torneios o seu ROI começa a significar alguma coisa em MTT de campo grande?',
        ['Milhares, porque o resultado é dominado por poucos deep runs raros',
         'Cerca de cem, se você jogar concentrado',
         'Não importa o número, o que importa é a consistência'],
        0,
        'Em MTT de campo grande, a maior parte do lucro vem de um punhado de resultados muito '
        'grandes. Enquanto eles não acontecem, o ROI medido diz mais sobre a sorte da amostra que '
        'sobre a sua habilidade, e a conta só estabiliza na casa dos milhares de torneios. É por '
        'isso que avaliar jogo por resultado é inviável nesse formato, e por que avaliar por '
        'QUALIDADE DE DECISÃO é o único caminho prático.',
        '**ROI em MTT precisa de milhares de torneios. Julgue decisão, não resultado.**',
        xp=30)


def bk_shot() -> dict:
    return _q(
        'bk_shot',
        'Você quer dar um tiro num limite acima. Qual regra protege melhor?',
        ['Definir ANTES quantos buy-ins você aceita perder e voltar sem discussão ao atingir o limite',
         'Subir quando estiver ganhando, porque é quando você está jogando bem',
         'Subir quando estiver perdendo, para recuperar mais rápido'],
        0,
        'A única proteção que funciona é a que você define antes, quando ainda não há dinheiro nem '
        'emoção em jogo. Subir "porque está ganhando" confunde variância com forma; subir "para '
        'recuperar" é a definição de perseguir perdas, e é o jeito mais rápido de transformar um '
        'downswing normal em quebra de banca. O tiro é uma decisão de gestão, não de humor.',
        '**Defina o limite de perda antes de subir. Depois de subir, já é tarde para decidir.**',
        xp=30)


def bk_variance_stakes() -> dict:
    return _q(
        'bk_variance_stakes',
        'Por que MTT exige muito mais buy-ins de banca que cash game do mesmo valor?',
        ['Porque a distribuição de resultados é muito mais desigual: você perde pouco quase sempre '
         'e ganha muito raramente',
         'Porque os torneios são mais caros no total',
         'Porque em MTT você enfrenta jogadores melhores'],
        0,
        'Em cash game, os resultados se distribuem de forma relativamente equilibrada em torno da '
        'média. Em MTT, não: você perde o buy-in na maioria das vezes e o retorno se concentra em '
        'poucos resultados enormes. Essa forma de distribuição é que produz downswings longos e '
        'exige uma banca muito maior para sobreviver a eles, mesmo com edge idêntico.',
        '**A forma da distribuição, não o preço, é o que exige mais buy-ins em MTT.**',
        xp=30)


# ── Termos ────────────────────────────────────────────────────────────────────────────────────

def tm_spr_apply() -> dict:
    """DINÂMICO: aplica SPR em vez de pedir a definição."""
    pote = random.choice([6, 8, 10, 12])
    stack = random.choice([12, 20, 40, 80])
    spr = stack / pote
    baixo = spr <= 3
    return _q(
        'tm_spr_apply',
        f'Flop, pote de {pote}bb e stack efetivo de {stack}bb. O SPR é {spr:.1f}. O que isso muda '
        f'na prática com top pair?',
        ['Com SPR baixo, top pair já é mão de se comprometer; com SPR alto, ela vira mão de pote '
         'controlado' if baixo else
         'Com SPR alto, top pair vira mão de pote controlado; com SPR baixo, é mão de se comprometer',
         'O SPR só serve para calcular quantas apostas cabem até o all-in',
         'SPR não muda a força da mão, então não muda a decisão'],
        0,
        f'SPR é o stack dividido pelo pote, aqui {stack} sobre {pote}, ou seja {spr:.1f}. Ele diz '
        f'quanta manobra existe: com SPR baixo, o pote é grande em relação ao que resta e top pair '
        f'costuma valer o stack; com SPR alto, sobra dinheiro demais para pagar três apostas com uma '
        f'mão só, e ela vira candidata a pote controlado. A força da mão não mudou, o que mudou foi '
        f'o que ela aguenta.',
        '**SPR não muda a mão, muda o quanto ela aguenta. É por isso que ele decide a linha.**',
        xp=30)


def tm_mdf_apply() -> dict:
    return _q(
        'tm_mdf_apply',
        'O vilão aposta o tamanho do pote no river. Pela MDF, quanto do seu range você precisa '
        'defender para ele não lucrar blefando com qualquer coisa?',
        ['Cerca de metade, porque uma aposta do tamanho do pote precisa funcionar em metade das vezes',
         'Cerca de dois terços, porque o pote está maior depois da aposta',
         'Cerca de um terço, porque você tem posição para escolher'],
        0,
        'A MDF vem do preço que o blefe recebe. Apostando o pote, ele arrisca 1 para ganhar 1, então '
        'precisa dar certo em metade das vezes. Se você defender menos que isso, blefar com qualquer '
        'duas cartas passa a ser lucrativo para ele. A régua se inverte com o tamanho: quanto maior '
        'a aposta, menos você precisa defender, porque o blefe fica mais caro.',
        '**MDF vem do preço do blefe. Aposta maior, defesa menor.**',
        xp=30)


def tm_range_thinking() -> dict:
    return _q(
        'tm_range_thinking',
        'O que significa, na prática, "pensar em ranges" em vez de pensar em mãos?',
        ['Decidir com base em TODAS as mãos que ele poderia ter naquela linha, e não em adivinhar '
         'qual delas é',
         'Colocar o vilão numa mão específica e jogar contra ela',
         'Assumir que ele tem a mão mais forte possível e se proteger'],
        0,
        'Ninguém tem como saber qual mão o adversário tem, mas dá para saber quais ele PODERIA ter, '
        'dada a linha que ele tomou. A decisão certa é a que rende mais contra esse conjunto '
        'inteiro, ponderado por quantas combinações de cada. Adivinhar uma mão específica acerta às '
        'vezes e erra sistematicamente; assumir sempre a mais forte é a receita para foldar demais.',
        '**Você joga contra o conjunto, não contra uma mão. É isso que range thinking quer dizer.**',
        xp=30)


def tm_ev_apply() -> dict:
    return _q(
        'tm_ev_apply',
        'Você fez um call +EV e perdeu o pote. O que isso diz sobre a decisão?',
        ['Nada: EV é a média de muitas repetições, e uma mão isolada não avalia a escolha',
         'Que o call foi errado, porque o resultado provou',
         'Que o call foi certo, porque o resultado não importa nunca'],
        0,
        'EV positivo significa que, repetida muitas vezes, aquela decisão ganha dinheiro. Um único '
        'resultado é uma amostra de tamanho um, e não distingue decisão boa de sorte ruim. Isso não '
        'quer dizer que resultado nunca importe: ele importa em VOLUME, quando já não é ruído. '
        'Julgar uma escolha pelo que aconteceu daquela vez é o hábito que mais atrapalha a evolução '
        'em poker.',
        '**Uma mão não avalia uma decisão. EV é média, e média precisa de volume.**',
        xp=30)
