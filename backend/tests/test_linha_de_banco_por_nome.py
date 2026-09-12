# -*- coding: utf-8 -*-
"""Linha de banco se le por NOME, nunca por indice nem desempacotando (07/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Na homologacao do pacote de 07/09 contra Postgres de verdade, o modal "contra quem" dava 500:
"could not convert string to float: 'effective_stack_bb'". No Postgres a linha e um dict
(RealDictCursor): desempacotar (`for a, b, c in rows`) itera as CHAVES, e `r[0]` e KeyError.
No SQLite (`sqlite3.Row`) os dois funcionam, entao a suite inteira passou verde com tres
funcoes novas quebradas em prod. E a classe de bug numero 8 da lista de "SQLite tolera,
Postgres rejeita" (ver memoria project_production_live).

── A segunda volta (12/09), e o que ela ensinou ───────────────────────────────────────────

A varredura olhava SO `repositories.py`, e o bug voltou fora dele — DUAS vezes:

  1. `scripts/limpa_perfis_sem_identidade.py` estourou `KeyError: 0` EM PRODUCAO, na linha que
     existia justamente para CONFERIR que o DELETE pegou. O DELETE ja tinha commitado, entao o
     dado ficou certo e quem morreu foi a conferencia.
  2. Ampliando a varredura, apareceu um bug VIVO e MUDO: `leaklab/preflop_autocapture.py` lia
     `row[0]` para pegar o `raw_text`, o erro subia para um `except Exception` que so escreve
     warning, e **a captura automatica de preflop nunca capturou nada em producao** desde que o
     Postgres entrou. Provado chamando a funcao dentro do container: `KeyError 0`.

Agora: ZERO no codigo de aplicacao, e a divida dos scripts CONGELADA (nao pode crescer).

Tres licoes de guarda, todas de quebra-de-proposito no mesmo dia:

  · **Guarda que le fonte le CODIGO.** Grep pega comentario, docstring e mensagem de erro. Um
    comentario meu absolveu uma porta no guarda do score; outro acusou uma fiacao intacta no
    guarda do `reveals`; e a docstring de `um_numero`, que cita o bug para explica-lo, foi
    acusada por ESTE guarda. Tokenizar resolve os tres.
  · **Tokenizar apagando a linha inteira cega o guarda.** A forma real do bug
    (`conn.execute("SELECT ...").fetchone()[0]`) tem SQL inline na MESMA linha do indice: apagar
    a linha por ela conter string faz o varredor nao ver nada. Apaga-se o TRECHO, por coluna.
  · **Testar o regex nao e testar o varredor.** O regex passava verde com o pipeline cego. O
    guarda precisa de um caso que atravesse o caminho inteiro.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))
# FONTE UNICA da leitura "so codigo": `test_row_access` varre o MESMO padrao e usava outra
# varredura; em 12/09 so uma das duas aprendeu a ignorar comentario, e a outra acusou os
# comentarios do proprio conserto. Ver `tests/_fonte.py`.
from leitura_de_fonte import so_codigo as _so_codigo                                     # noqa: E402
_RAIZ = os.path.join(os.path.dirname(__file__), '..')

#: Os arquivos varridos. Ate 12/09 a varredura olhava SO `repositories.py`, e o bug voltou num
#: SCRIPT: a conferencia final de `limpa_perfis_sem_identidade.py` estourou `KeyError: 0` EM
#: PRODUCAO, depois do DELETE ja commitado (o dado ficou certo, morreu quem ia conferir).
#: Regra 5: o padrao vive em N lugares, a varredura tem de cobrir os N+1.
_ALVOS = ['database/repositories.py', 'api/app.py', 'leaklab/preflop_autocapture.py',
          'leaklab/opponent_stats.py', 'leaklab/coach_replay.py']

#: Scripts: TODOS, menos os declarados aqui COM MOTIVO. Lista de exclusao sem motivo e o
#: problema de novo (mesma politica do `FORA_DA_SUITE` do runner de testes).
_SCRIPTS_FORA = {
    '_check_gto_nodes.py': 'usa PRAGMA table_info, que so existe no SQLite: e script de dev '
                           'local e nunca roda contra o Postgres',
}

_INDICE = re.compile(r"\b(r|row|linha|d)\[\d\]")
#: `fetchone()[0]` / `fetchall()[0]` — a forma exata que escapou em 12/09. O regex de cima exige
#: um NOME de variavel antes do indice, e aqui o indice vem direto do metodo.
_FETCH_INDICE = re.compile(r"fetch(?:one|all)\(\)\s*\[\d\]")
_DESEMPACOTA = re.compile(r"^\s*for\s+[a-z_0-9]+(?:\s*,\s*[a-z_0-9]+)+\s+in\s+rows\s*:")   # `is_3bet` tem digito


def _arquivos():
    alvos = [(rel, os.path.join(_RAIZ, *rel.split('/'))) for rel in _ALVOS]
    pasta = os.path.join(_RAIZ, 'scripts')
    for nome in sorted(os.listdir(pasta)):
        if nome.endswith('.py') and nome not in _SCRIPTS_FORA:
            alvos.append(('scripts/' + nome, os.path.join(pasta, nome)))
    return alvos


def _ocorrencias():
    achados = []
    for rel, caminho in _arquivos():
        fonte = open(caminho, encoding='utf-8').read()
        cru = {n: l for n, l in enumerate(fonte.splitlines(), 1)}
        for n, codigo in sorted(_so_codigo(fonte).items()):
            # Guardado quando a PROPRIA linha distingue os backends. `isinstance(x, dict)` e
            # `hasattr(x, 'keys')` sao as duas formas usadas no projeto.
            if 'isinstance' in codigo or 'hasattr' in codigo:
                continue
            if _INDICE.search(codigo) or _FETCH_INDICE.search(codigo):
                achados.append((rel, n, 'indice', cru[n].strip()[:90]))
            if _DESEMPACOTA.match(codigo):
                achados.append((rel, n, 'desempacota', cru[n].strip()[:90]))
    return achados


def test_nenhuma_linha_de_banco_lida_por_indice_ou_desempacotada():
    """ZERO no codigo de APLICACAO: e o que roda a cada request e a cada upload."""
    achados = [a for a in _ocorrencias() if not a[0].startswith('scripts/')]
    assert not achados, 'linha de banco por indice/desempacotamento (quebra no Postgres):\n' + '\n'.join(
        '  %s:%d [%s] %s' % a for a in achados)


#: DIVIDA CONGELADA dos scripts, por arquivo. Ampliar a varredura para `scripts/` em 12/09
#: encontrou 26 arquivos com o padrao — a maioria diagnostico ad-hoc de uma ocasiao, alguns
#: rodando so em SQLite local. Consertar os 26 agora seria mexer em muita coisa sem pedido, e
#: deixar o guarda vermelho para sempre e pior que nao ter guarda: ensina a ignorar.
#:
#: Entao a divida fica REGISTRADA e nao pode crescer: numero novo em arquivo desta lista, ou
#: arquivo novo com o padrao, faz o teste falhar. Baixar um numero e sempre bem-vindo (o teste
#: avisa para atualizar o baseline).
#:
#: `scripts/run_gto_worker.py` NAO entra aqui: ele roda em producao (o worker do solver) e foi
#: consertado junto com os outros tres que rodam no container.
_DIVIDA_SCRIPTS = 68


def test_a_divida_dos_scripts_nao_cresce():
    achados = [a for a in _ocorrencias() if a[0].startswith('scripts/')]
    assert len(achados) <= _DIVIDA_SCRIPTS, (
        'apareceram %d ocorrencias em scripts/, acima do baseline de %d. As novas:\n%s'
        % (len(achados), _DIVIDA_SCRIPTS,
           '\n'.join('  %s:%d [%s] %s' % a for a in achados[-12:])))
    if len(achados) < _DIVIDA_SCRIPTS:
        print('OK  a divida CAIU para %d (era %d): atualize `_DIVIDA_SCRIPTS`'
              % (len(achados), _DIVIDA_SCRIPTS))


def test_a_varredura_cobre_os_scripts_e_nao_so_repositories():
    """CONTROLE DA VARREDURA. O bug de 12/09 passou porque ela olhava um arquivo so; se ela
    voltar a varrer pouco, o guarda fica verde sem cobrir nada."""
    rels = [rel for rel, _ in _arquivos()]
    assert 'database/repositories.py' in rels
    assert 'api/app.py' in rels
    scripts = [r for r in rels if r.startswith('scripts/')]
    assert len(scripts) >= 30, 'a varredura parou de cobrir os scripts (%d)' % len(scripts)
    assert 'scripts/limpa_perfis_sem_identidade.py' in rels, \
        'o script que quebrou em producao saiu da varredura'


def test_o_VARREDOR_acha_a_forma_com_SQL_inline():
    """PIPELINE, nao regex.

    `test_o_padrao_do_fetchone_por_indice_e_acusado` exercita o regex isolado, e ele passava
    verde enquanto o varredor INTEIRO estava cego: `_so_codigo` apagava a linha toda por ela
    conter a string do SQL, e a forma real do bug tem SQL inline na mesma linha do indice.

    Quem achou foi a quebra de proposito: um script forjado com essa exata forma nao movia o
    contador da divida. Guarda exercitado so por dentro e guarda nao exercitado."""
    linhas = [
        'from database.schema import get_conn',
        'conn = get_conn()',
        'n = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]',
        'row = conn.execute("SELECT a FROM b").fetchone()',
        'x = row[0]',
        '# comentario com fetchone()[0] nao conta',
    ]
    codigo = _so_codigo(chr(10).join(linhas) + chr(10))
    assert _FETCH_INDICE.search(codigo[3]), ('o SQL inline apagou a linha inteira', repr(codigo[3]))
    assert _INDICE.search(codigo[5]), repr(codigo[5])
    # comentario nao e evidencia, nem a favor nem contra
    assert not _FETCH_INDICE.search(codigo[6]), ('comentario virou evidencia', repr(codigo[6]))
    # e a linha que pega a LINHA (sem indice) e a forma certa: nao pode acusar
    assert not _INDICE.search(codigo[4]) and not _FETCH_INDICE.search(codigo[4]), repr(codigo[4])


def test_o_padrao_do_fetchone_por_indice_e_acusado():
    """A forma exata que escapou: `...fetchone()[0]`, sem nome de variavel antes do indice."""
    assert _FETCH_INDICE.search('resta = conn.execute(sql).fetchone()[0]')
    assert _FETCH_INDICE.search("n = conn.execute('SELECT COUNT(*) FROM x').fetchall()[0]")
    # e o que NAO deve acusar
    assert not _FETCH_INDICE.search('linha = conn.execute(sql).fetchone()')
    assert not _FETCH_INDICE.search("return um_numero(conn, 'SELECT COUNT(*) FROM x')")


def test_o_varredor_acha_os_tres_casos_reais():
    """Os tres trechos que quebraram na homologacao, forjados: o varredor tem de acusar."""
    forjado = [
        "        if r[0] in vistas:",
        "        return [(r[0], r[1], r[2]) for r in rows]",
        "    for vs, vs_chart, pos_chart, stack, acao, is_3bet in rows:",
        "        spot = row['spot'] if isinstance(row, dict) else row[0]",      # guardado: nao acusa
        "    for r in rows:",                                                    # certo: nao acusa
    ]
    acusa = [l for l in forjado if (_INDICE.search(l) and 'isinstance' not in l) or _DESEMPACOTA.match(l)]
    assert acusa == forjado[:3], acusa


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
