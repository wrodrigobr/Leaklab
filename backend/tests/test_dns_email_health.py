# -*- coding: utf-8 -*-
"""Guarda de entrega de e-mail (20/08).

O caso real que originou isto: 7 contas presas na confirmação de cadastro, TODAS com zero
tentativas de digitar o código. O log dizia "e-mail enviado" e a credencial SMTP autenticava
— o que faltava era o DNS do domínio autorizar o Brevo. O domínio ainda por cima publicava
p=quarantine, mandando as caixas jogarem no spam o e-mail do próprio produto.

O teste central é `test_estado_real_de_20_08_e_acusado`: ele congela os registros que
estavam publicados naquele dia e exige que o guarda ACUSE. Sem isso eu teria um avaliador
que devolve "ok" para o cenário que já nos custou 7 contas — o zero tranquilizador.

Cada guarda também é quebrado de propósito (regra 2): o cenário são corrigido tem que
devolver ok, senão o teste passaria por acusar tudo.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.dns_email_health import avaliar_dns_email  # noqa: E402

# O que estava publicado em grindlabpoker.com em 20/08/2026, verificado por DoH.
SPF_REAL = 'v=spf1 include:_spf.mx.cloudflare.net ~all'
DMARC_REAL = 'v=DMARC1; p=quarantine; adkim=r; aspf=r; rua=mailto:dmarc_rua@onsecureserver.net;'
DKIM_REAL = {'brevo': None, 'mail': None}

# O mesmo domínio depois do conserto que este guarda pede.
SPF_BOM = 'v=spf1 include:_spf.mx.cloudflare.net include:spf.brevo.com ~all'
DKIM_BOM = {'brevo': 'k=rsa; p=MIGfMA0GCS...', 'mail': None}


def _codigos(res):
    return {p['codigo'] for p in res['problemas']}


def test_estado_real_de_20_08_e_acusado():
    """O cenário que custou 7 contas TEM que acusar — é a prova de que o guarda detecta."""
    r = avaliar_dns_email(SPF_REAL, DKIM_REAL, DMARC_REAL)
    assert not r['ok'], 'guarda calou no cenário que já quebrou em produção'
    assert r['entrega_em_risco'], 'não marcou entrega em risco com SPF e DKIM quebrados'
    assert 'spf_sem_provedor' in _codigos(r)
    assert 'dkim_ausente' in _codigos(r)
    assert 'dmarc_pune_sem_autenticacao' in _codigos(r)


def test_dominio_corrigido_passa():
    """Contraprova: se acusasse tudo, o teste acima não valeria nada."""
    r = avaliar_dns_email(SPF_BOM, DKIM_BOM, DMARC_REAL)
    assert r['ok'], f'acusou domínio saudável: {r["problemas"]}'
    assert not r['entrega_em_risco']
    assert r['spf_ok'] and r['dkim_ok']


def test_quebra_deliberada_do_spf():
    """Desfaz só o SPF do cenário bom: o guarda tem que acusar exatamente isso."""
    r = avaliar_dns_email(SPF_REAL, DKIM_BOM, DMARC_REAL)
    assert 'spf_sem_provedor' in _codigos(r)
    assert 'dkim_ausente' not in _codigos(r), 'acusou DKIM que estava publicado'
    # DKIM sozinho já autentica, então o DMARC não pune.
    assert 'dmarc_pune_sem_autenticacao' not in _codigos(r)
    # Mas continua em risco: DKIM salva o DMARC e o SPF falhando ainda pesa na reputação
    # do domínio. Marcar "em risco" aqui é a escolha conservadora, e é deliberada.
    assert r['entrega_em_risco'], 'SPF quebrado deixou de contar como risco'


def test_quebra_deliberada_do_dkim():
    r = avaliar_dns_email(SPF_BOM, DKIM_REAL, DMARC_REAL)
    assert 'dkim_ausente' in _codigos(r)
    assert 'spf_sem_provedor' not in _codigos(r), 'acusou SPF que estava correto'
    assert 'dmarc_pune_sem_autenticacao' not in _codigos(r), 'SPF válido já autentica'


def test_spf_ausente_e_diferente_de_spf_errado():
    """Os dois consertos são diferentes: publicar um registro vs editar o que existe
    (um domínio só pode ter UM SPF — criar um segundo invalida os dois)."""
    r = avaliar_dns_email(None, DKIM_BOM, DMARC_REAL)
    assert 'spf_ausente' in _codigos(r) and 'spf_sem_provedor' not in _codigos(r)
    conserto = next(p['conserto'] for p in r['problemas'] if p['codigo'] == 'spf_ausente')
    assert 'spf.brevo.com' in conserto


def test_dmarc_so_pune_quando_nada_autentica():
    """p=reject com autenticação boa é o estado DESEJÁVEL, não um problema."""
    r = avaliar_dns_email(SPF_BOM, DKIM_BOM, 'v=DMARC1; p=reject;')
    assert r['ok'], 'acusou o alvo final (DMARC forte COM autenticação funcionando)'
    assert r['dmarc_politica'] == 'reject'


def test_dmarc_ausente_e_aviso_nao_critico():
    r = avaliar_dns_email(SPF_BOM, DKIM_BOM, None)
    assert 'dmarc_ausente' in _codigos(r)
    assert not r['entrega_em_risco'], 'sem DMARC a entrega não está em risco por si só'
    assert all(p['gravidade'] == 'aviso' for p in r['problemas'])


def test_provedor_desconhecido_erra_alto():
    """Silêncio aqui viraria 'ok' para um provedor que ninguém checou (regra 6)."""
    try:
        avaliar_dns_email(SPF_BOM, DKIM_BOM, DMARC_REAL, provedor='inventado')
    except ValueError:
        return
    raise AssertionError('provedor desconhecido passou calado')


def test_txt_de_spf_partido_em_pedacos_ainda_casa():
    """TXT longo chega concatenado; o include não pode escapar por causa de espaçamento."""
    r = avaliar_dns_email('v=spf1  include:spf.brevo.com   ~all', DKIM_BOM, DMARC_REAL)
    assert r['spf_ok']


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
