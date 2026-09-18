# -*- coding: utf-8 -*-
"""test_nome_do_remetente.py - o e-mail chega assinado por GrindLab, e nao por "noreply".

── O caso (18/09) ───────────────────────────────────────────────────────────────────────────

O dono fotografou a caixa de entrada: a mensagem chegava com o remetente **noreply**. O `From`
recebia o endereco CRU (`noreply@grindlabpoker.com`), e cliente de e-mail sem nome de exibicao
mostra a parte local do endereco.

── Por que este arquivo existe, alem do conserto ───────────────────────────────────────────

O conserto tem DUAS metades, e so uma e visivel:

1. O CABECALHO ganha o nome (`GrindLab <noreply@...>`), que e o que o jogador ve.
2. O ENVELOPE, que vai no `sendmail`, tem de seguir sendo o endereco PURO. Servidor de SMTP
   recusa envelope com nome de exibicao, e ai a mensagem inteira falha -- trocar "nome errado"
   por "nao chega" seria a regra 7 da casa: o conserto causando dano que o defeito nao causava.

Um teste que olhasse so o cabecalho passaria verde com o envio quebrado. Por isso os casos abaixo
cobram as duas metades, e a segunda com o `sendmail` dublado.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("  FAIL: %s" % msg)


from leaklab.email_digest import NOME_DO_REMETENTE, _montar_mensagem

ENDERECO = "noreply@grindlabpoker.com"


# ── 1. O CABECALHO tem nome, e o endereco continua la ────────────────────────────────────────
msg = _montar_mensagem("Assunto", ENDERECO, "jogador@exemplo.com", "<p>corpo</p>")
cabecalho = str(msg["From"])

check("GrindLab" in cabecalho, 'o `From` chegou sem o nome: %r' % cabecalho)
check(ENDERECO in cabecalho, 'o `From` perdeu o endereco: %r' % cabecalho)
# a forma importa: `Nome <endereco>` e o que o cliente sabe separar
check(cabecalho.strip().endswith("<%s>" % ENDERECO),
      'o `From` nao esta no formato `Nome <endereco>`: %r' % cabecalho)
check(NOME_DO_REMETENTE == "GrindLab",
      'o nome padrao deixou de ser a marca: %r' % NOME_DO_REMETENTE)

# CONTROLE: sem ele, um `From` cravado na string "GrindLab" passaria nos casos acima sem o
# endereco de verdade -- e o e-mail nao sairia.
check(cabecalho != "GrindLab", 'o `From` virou so o nome, sem endereco')


# ── 2. O ENVELOPE continua PURO ──────────────────────────────────────────────────────────────
#
# A metade invisivel. Quem envia passa `from_addr` ao `sendmail`, e ele tem de ser o endereco sem
# nome. Este caso dubla o SMTP e olha o que foi entregue ao servidor.
import smtplib
import unittest.mock as mock

from leaklab import email_digest


class _ServidorFalso:
    def __init__(self, *a, **k):
        self.enviados = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, *a):
        pass

    def sendmail(self, envelope, destinos, corpo):
        _ServidorFalso.ultimo = (envelope, destinos, corpo)


_ServidorFalso.ultimo = None

ambiente = {
    "SMTP_HOST": "smtp.exemplo.com",
    "SMTP_USER": "u",
    "SMTP_PASSWORD": "p",
    "DIGEST_FROM": ENDERECO,
}
with mock.patch.dict(os.environ, ambiente), \
        mock.patch.object(smtplib, "SMTP", _ServidorFalso):
    ok = email_digest.send_transactional_email("jogador@exemplo.com", "Assunto", "<p>corpo</p>")

check(ok, 'o envio falhou com o SMTP dublado')
check(_ServidorFalso.ultimo is not None, 'o `sendmail` nao foi chamado')
if _ServidorFalso.ultimo:
    envelope, destinos, corpo = _ServidorFalso.ultimo
    check(envelope == ENDERECO,
          'o ENVELOPE saiu com nome de exibicao, e servidor de SMTP recusa isso: %r' % envelope)
    check("<" not in envelope and ">" not in envelope,
          'o envelope tem os sinais do formato `Nome <endereco>`: %r' % envelope)
    # e o CORPO, que carrega o cabecalho, tem o nome
    check("GrindLab" in corpo, 'a mensagem entregue nao carrega o nome do remetente')


# ── 3. O nome e configuravel, e cai na marca quando ninguem configura ────────────────────────
check(NOME_DO_REMETENTE == os.environ.get("MAIL_FROM_NAME", "GrindLab"),
      'o nome deixou de sair de `MAIL_FROM_NAME`')

print("\n" + "=" * 50)
print("Total: %d | Passed: %d | Failed: %d" % (passed + failed, passed, failed))
sys.exit(1 if failed else 0)
