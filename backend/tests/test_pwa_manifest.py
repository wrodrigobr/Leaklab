# -*- coding: utf-8 -*-
"""O manifest que faz o Chrome oferecer "instalar aplicativo" — e o que ele promete.

── Por que este guarda existe (27/08) ─────────────────────────────────────────────────────

O dono viu no concorrente a opção de instalar como aplicativo e perguntou se dava para fazer.
Medido antes de responder: **nós já tínhamos** o manifest servido em produção (HTTP 200) e os
ícones de 192 e 512 no ar. Pelo critério atual do Chrome (HTTPS + manifest com nome, ícones de
192/512, `start_url` e `display`) já éramos instaláveis, e service worker não é requisito.

Mas a conferência achou três defeitos reais:

  1. `start_url` era `/` — o app instalado abria a LANDING de marketing, não o produto.
  2. o ícone `maskable` reusava o quadrado comum. O Android recorta maskable num círculo
     inscrito, então a borda da marca era cortada. Agora existe um ícone próprio, com a marca
     a 62% sobre o `background_color`.
  3. faltavam `id` e `lang`.

Nada aqui é cosmético: `start_url` errado é a primeira tela que o usuário instalado vê.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_PUB = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..', 'frontend', 'public'))


def _manifest():
    caminho = os.path.join(_PUB, 'manifest.webmanifest')
    assert os.path.exists(caminho), 'manifest sumiu de frontend/public'
    with open(caminho, encoding='utf-8') as fh:
        return json.load(fh)


def test_atende_os_criterios_de_instalabilidade_do_chrome():
    """Os campos sem os quais o Chrome não oferece instalar. Cada um conferido sozinho."""
    m = _manifest()
    assert m.get('name') or m.get('short_name'), 'sem name/short_name: não instala'
    assert m.get('start_url'), 'sem start_url: não instala'
    assert m.get('display') in ('standalone', 'fullscreen', 'minimal-ui',
                                'window-controls-overlay'), \
        'display %r não é um modo instalável' % m.get('display')
    assert not m.get('prefer_related_applications'), (
        'prefer_related_applications manda o usuário para a loja em vez de instalar o PWA')
    tamanhos = {i.get('sizes') for i in m.get('icons') or []}
    for exigido in ('192x192', '512x512'):
        assert exigido in tamanhos, 'falta ícone %s: o Chrome não oferece instalar' % exigido
    print('OK  test_atende_os_criterios_de_instalabilidade_do_chrome')


def test_o_app_instalado_abre_o_PRODUTO_nao_a_landing():
    """O defeito nº 1. `start_url: "/"` faz o ícone na área de trabalho abrir a página de vendas
    — a tela que existe para converter quem AINDA não é usuário."""
    m = _manifest()
    assert m['start_url'] != '/', (
        'start_url voltou para "/": o app instalado abre a landing de marketing em vez do produto')
    assert m['start_url'].startswith('/'), 'start_url precisa ser um caminho do próprio site'
    print('OK  test_o_app_instalado_abre_o_PRODUTO_nao_a_landing (%s)' % m['start_url'])


def test_o_icone_maskable_e_PROPRIO_e_existe_em_disco():
    """O defeito nº 2. Android recorta maskable num círculo inscrito: reusar o ícone quadrado
    corta a borda da marca. Guarda em duas metades — declarado no manifest E presente no disco."""
    m = _manifest()
    mask = [i for i in m.get('icons') or [] if 'maskable' in (i.get('purpose') or '')]
    assert mask, 'nenhum ícone maskable declarado'
    comuns = {i['src'] for i in m['icons'] if (i.get('purpose') or '') == 'any'}
    for i in mask:
        assert i['src'] not in comuns, (
            'o maskable %s é o MESMO arquivo do ícone comum — volta a ser cortado no Android'
            % i['src'])
        arq = os.path.join(_PUB, i['src'].lstrip('/'))
        assert os.path.exists(arq), 'maskable declarado e ausente do disco: %s' % i['src']
    print('OK  test_o_icone_maskable_e_PROPRIO_e_existe_em_disco')


def test_todo_icone_declarado_existe():
    """CONTROLE do teste acima: ele confere o caminho do maskable; este varre TODOS. Ícone
    declarado e ausente é 404 silencioso — o Chrome simplesmente deixa de oferecer instalar."""
    m = _manifest()
    faltando = [i['src'] for i in m.get('icons') or []
                if not os.path.exists(os.path.join(_PUB, i['src'].lstrip('/')))]
    assert not faltando, 'ícones declarados e ausentes do disco: %s' % ', '.join(faltando)
    print('OK  test_todo_icone_declarado_existe (%d ícones)' % len(m.get('icons') or []))


def test_o_index_html_LINKA_o_manifest():
    """Fiação. O manifest mais correto do mundo não faz nada se a página não o referenciar."""
    caminho = os.path.join(_PUB, '..', 'index.html')
    with open(caminho, encoding='utf-8') as fh:
        html = fh.read()
    assert 'rel="manifest"' in html, (
        'o index.html parou de linkar o manifest: o Chrome deixa de oferecer instalar')
    print('OK  test_o_index_html_LINKA_o_manifest')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
