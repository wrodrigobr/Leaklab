# -*- coding: utf-8 -*-
"""Saúde do DNS que decide se nosso e-mail chega na caixa de entrada ou no spam.

Por que isto existe: em 20/08/2026 medimos 7 contas presas na confirmação de cadastro, todas
com ZERO tentativas de digitar o código — ninguém tinha recebido o e-mail. O relay autenticava
normalmente (a credencial do Brevo funcionava), então o log dizia "enviado". O que estava
errado era o DNS do nosso próprio domínio:

  SPF   -> autorizava só o Cloudflare, não o Brevo, que é quem envia de fato
  DKIM  -> nenhum seletor publicado
  DMARC -> p=quarantine, isto é, "se falhar SPF e DKIM, jogue no spam"

Ou seja, o domínio instruía o Gmail/Hotmail a quarentenar o próprio produto. "SMTP OK" não é
evidência de entrega — é evidência de que o relay aceitou o envio.

A avaliação aqui é uma função PURA sobre registros já resolvidos, para poder ser testada sem
rede. Quem resolve o DNS é `scripts/verificar_dns_email.py`.
"""
from __future__ import annotations

# Como cada provedor de envio se declara no DNS do domínio do cliente.
PROVEDORES = {
    'brevo': {
        'nome': 'Brevo',
        'spf_include': 'spf.brevo.com',
        # Os seletores REAIS que o Brevo manda publicar são `brevo1` e `brevo2` (dois CNAMEs
        # para b1./b2.<dominio>.dkim.brevo.com). A primeira versão deste arquivo procurou em
        # `brevo` e `mail` e reportou "DKIM ausente" com os dois publicados e casando — um
        # alarme falso, que custa tanto quanto o silêncio: manda consertar o que já está certo.
        # `mail` é o seletor legado do Sendinblue e fica na lista por causa de contas antigas.
        'seletores_dkim': ('brevo1', 'brevo2', 'brevo', 'mail'),
    },
    'sendgrid': {
        'nome': 'SendGrid',
        'spf_include': 'sendgrid.net',
        'seletores_dkim': ('s1', 's2'),
    },
    'ses': {
        'nome': 'Amazon SES',
        'spf_include': 'amazonses.com',
        'seletores_dkim': (),  # SES usa 3 CNAMEs com nome gerado por domínio
    },
}

CRITICO = 'critico'
AVISO = 'aviso'


def _politica_dmarc(dmarc_txt: str | None) -> str | None:
    """Extrai o `p=` do registro DMARC. None se não houver registro ou não houver p=."""
    if not dmarc_txt:
        return None
    for parte in dmarc_txt.split(';'):
        parte = parte.strip()
        if parte.lower().startswith('p='):
            return parte[2:].strip().lower() or None
    return None


def avaliar_dns_email(spf_txt: str | None,
                      dkim_por_seletor: dict[str, str | None] | None,
                      dmarc_txt: str | None,
                      provedor: str = 'brevo') -> dict:
    """Diz se o domínio autoriza nosso provedor a enviar em nome dele.

    `dkim_por_seletor` mapeia seletor -> valor publicado (TXT ou CNAME), com None/'' para
    "não existe". Devolve {'ok', 'entrega_em_risco', 'problemas': [...], 'resumo'}.

    `ok` é falso com QUALQUER problema. `entrega_em_risco` é o veredito que importa na
    prática: verdadeiro quando a combinação faz o provedor de caixa descartar ou quarentenar.
    """
    cfg = PROVEDORES.get(provedor)
    if cfg is None:
        raise ValueError(f'provedor desconhecido: {provedor!r}')
    problemas: list[dict] = []
    dkim_por_seletor = dkim_por_seletor or {}

    # ── SPF ──────────────────────────────────────────────────────────────────
    spf = (spf_txt or '').strip()
    spf_ok = False
    if not spf:
        problemas.append({
            'codigo': 'spf_ausente', 'gravidade': CRITICO,
            'detalhe': 'O domínio não publica nenhum registro SPF.',
            'conserto': f"Publicar TXT na raiz: v=spf1 include:{cfg['spf_include']} ~all",
        })
    elif cfg['spf_include'] not in spf:
        problemas.append({
            'codigo': 'spf_sem_provedor', 'gravidade': CRITICO,
            'detalhe': (f"O SPF existe mas não autoriza o {cfg['nome']}, que é quem envia. "
                        f'Registro atual: {spf}'),
            'conserto': (f"Acrescentar include:{cfg['spf_include']} ao TXT de SPF da raiz "
                         '(um domínio só pode ter UM registro SPF: edite o existente, '
                         'não crie um segundo).'),
        })
    else:
        spf_ok = True

    # ── DKIM ─────────────────────────────────────────────────────────────────
    esperados = cfg['seletores_dkim']
    publicados = [s for s in esperados if (dkim_por_seletor.get(s) or '').strip()]
    dkim_ok = bool(publicados) if esperados else None
    if esperados and not publicados:
        problemas.append({
            'codigo': 'dkim_ausente', 'gravidade': CRITICO,
            'detalhe': (f"Nenhum seletor DKIM do {cfg['nome']} está publicado "
                        f"(procurados: {', '.join(s + '._domainkey' for s in esperados)}). "
                        'Sem DKIM o e-mail sai sem assinatura verificável.'),
            'conserto': (f'Validar o domínio no painel do {cfg["nome"]} e publicar os '
                         'registros DKIM que ele fornece.'),
        })

    # ── DMARC ────────────────────────────────────────────────────────────────
    politica = _politica_dmarc(dmarc_txt)
    if politica is None:
        problemas.append({
            'codigo': 'dmarc_ausente', 'gravidade': AVISO,
            'detalhe': 'Sem DMARC o tratamento fica a critério de cada provedor de caixa.',
            'conserto': 'Publicar TXT em _dmarc: v=DMARC1; p=none; rua=mailto:...',
        })

    # ── A combinação letal ───────────────────────────────────────────────────
    # DMARC exige que SPF **ou** DKIM passe e esteja alinhado. Com os dois quebrados e uma
    # política de quarantine/reject, é o próprio domínio mandando descartar o e-mail — e
    # isso é pior do que não ter DMARC nenhum, porque vira instrução explícita.
    autentica = spf_ok or bool(publicados)
    if politica in ('quarantine', 'reject') and not autentica:
        problemas.append({
            'codigo': 'dmarc_pune_sem_autenticacao', 'gravidade': CRITICO,
            'detalhe': (f'DMARC está em p={politica} mas nem SPF nem DKIM autorizam o '
                        f"{cfg['nome']}. O domínio instrui as caixas a "
                        f"{'rejeitar' if politica == 'reject' else 'quarentenar'} "
                        'todo e-mail que enviamos.'),
            'conserto': ('Corrigir SPF e DKIM ANTES de mexer no DMARC. Baixar para p=none '
                         'sem consertar a autenticação só esconde o problema dos relatórios.'),
        })

    # `entrega_em_risco` é reservado para quando NADA autentica — aí o e-mail de fato tende
    # a não chegar. Com um dos dois válido, o DMARC já passa e a entrega funciona: chamar
    # isso de "em risco" seria alarme exagerado, e alarme exagerado que o operador descobre
    # ser exagerado desmoraliza o instrumento tanto quanto o silêncio de um falso negativo.
    entrega_em_risco = not autentica
    criticos = sum(1 for p in problemas if p['gravidade'] == CRITICO)
    if not problemas:
        resumo = f"DNS de e-mail saudável para {cfg['nome']}."
    elif entrega_em_risco:
        resumo = (f'ENTREGA EM RISCO: {criticos} problema(s) crítico(s) no DNS — '
                  'o e-mail tende a cair em spam ou ser recusado.')
    elif criticos:
        resumo = (f'{criticos} problema(s) crítico(s) no DNS, mas a autenticação que resta '
                  f'({"SPF" if spf_ok else "DKIM"}) segura a entrega. Corrigir mesmo assim: '
                  'com uma única perna, qualquer mudança do outro lado derruba tudo.')
    else:
        resumo = f'{len(problemas)} ajuste(s) recomendado(s) no DNS de e-mail.'

    return {
        'ok': not problemas,
        'entrega_em_risco': entrega_em_risco,
        'spf_ok': spf_ok,
        'dkim_ok': dkim_ok,
        'dmarc_politica': politica,
        'problemas': problemas,
        'resumo': resumo,
    }
