"""
E-mail de cobrança: a régua dispara com fato e cala sem fato — testada nos dois sentidos.

── Por que este arquivo existe ───────────────────────────────────────────────────────────────

Spec cobranca-proximo-passo.md §5. Esta é a única parte do produto que ALCANÇA a pessoa fora do
app, e erro aqui não dá para desfazer: código sobe e desce, e-mail enviado fica na caixa dela.

Duas famílias de teste, e a segunda é a que importa mais:

  · DISPARA quando deve (senão a Fase 2 não existe);
  · CALA quando não deve — teto semanal, ausência de evento, revisão que venceu hoje de manhã,
    inatividade de quem não tem missão aberta. Cobrança sem fato novo gasta a credibilidade de
    todas as seguintes, e é a mesma lição que o relatório por calendário já pagou.

O interruptor (`ENGAGEMENT_EMAIL_ENABLED`) também é testado: um deploy não pode disparar e-mail
para a base inteira como efeito colateral.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.cobranca_email import (decidir_email_cobranca, emails_habilitados,
                                    montar_email, FORCA, TETO_DIAS)

AGORA  = '2026-07-29T12:00:00'
SEMANA = '2026-07-24T12:00:00'   # 5 dias atrás — DENTRO do teto
VELHO  = '2026-07-10T12:00:00'   # 19 dias atrás — fora do teto

_E_REABERTO = {'tipo': 'leak_reaberto', 'dados': {'titulo': 'Abertura de HJ · 50bb'}}
_E_RELATO   = {'tipo': 'relatorio_gerado', 'dados': {'id': 1, 'motivo': 'veredito'}}
_E_REVISAO  = {'tipo': 'revisao_vencida', 'dados': {'total': 3, 'drills': 1, 'ranges': 2}}
_E_INATIVO  = {'tipo': 'inatividade',
               'dados': {'missao': {'titulo': 'BB vs LJ · 30bb', 'ev_loss_bb': 14.4,
                                    'hands': 21}, 'dias': 9}}


# ── Dispara quando deve ───────────────────────────────────────────────────────────────────────

def test_primeiro_email_passa_sem_historico():
    """Sem envio anterior o teto não pode bloquear — é o caso de todo aluno novo."""
    e = decidir_email_cobranca(AGORA, [_E_RELATO], None)
    assert e and e['tipo'] == 'relatorio_gerado'


def test_o_gatilho_mais_FORTE_vence():
    """Quatro eventos na mesma varredura, um e-mail. A ordem espelha a precedência do próximo
    passo de propósito: o e-mail e a tela têm que concordar sobre o que é urgente."""
    e = decidir_email_cobranca(AGORA, [_E_INATIVO, _E_REVISAO, _E_RELATO, _E_REABERTO], VELHO)
    assert e['tipo'] == 'leak_reaberto'


def test_a_ordem_de_forca_e_a_da_precedencia():
    assert FORCA['leak_reaberto'] > FORCA['relatorio_gerado'] > FORCA['revisao_vencida'] \
        > FORCA['inatividade']


# ── Cala quando não deve mandar (a família que protege a caixa de entrada) ────────────────────

def test_teto_semanal_vence_ATE_o_gatilho_mais_forte():
    """Quem joga muito mudaria de estado toda semana; sem o teto o e-mail viraria ruído com
    cara de urgência. O teto vence inclusive o leak reaberto."""
    assert decidir_email_cobranca(AGORA, [_E_REABERTO], SEMANA) is None


def test_sem_evento_nao_manda_nada():
    assert decidir_email_cobranca(AGORA, [], VELHO) is None
    assert decidir_email_cobranca(AGORA, None, VELHO) is None


def test_evento_desconhecido_e_ignorado():
    """Tipo novo sem força declarada não pode virar e-mail por acidente."""
    assert decidir_email_cobranca(AGORA, [{'tipo': 'inventado', 'dados': {}}], VELHO) is None


def test_exatamente_no_limite_do_teto():
    """Fronteira explícita: 7 dias cravados já libera, 6 dias e 23h não."""
    assert decidir_email_cobranca('2026-07-31T12:00:00', [_E_RELATO],
                                  '2026-07-24T12:00:00') is not None      # 7d
    assert decidir_email_cobranca('2026-07-31T11:00:00', [_E_RELATO],
                                  '2026-07-24T12:00:00') is None          # 6d23h
    assert TETO_DIAS == 7


def test_data_ilegivel_nao_trava_o_aluno_para_sempre():
    """Se o histórico vier corrompido, o certo é tratar como 'nunca enviado' e deixar passar —
    o oposto silenciaria o aluno indefinidamente sem ninguém perceber."""
    assert decidir_email_cobranca(AGORA, [_E_RELATO], 'lixo') is not None


# ── O interruptor ─────────────────────────────────────────────────────────────────────────────

def test_desligado_por_padrao():
    """Um deploy não pode disparar e-mail para a base inteira como efeito colateral."""
    antes = os.environ.pop('ENGAGEMENT_EMAIL_ENABLED', None)
    try:
        assert emails_habilitados() is False
        for v in ('1', 'true', 'on', 'YES'):
            os.environ['ENGAGEMENT_EMAIL_ENABLED'] = v
            assert emails_habilitados() is True, v
        os.environ['ENGAGEMENT_EMAIL_ENABLED'] = '0'
        assert emails_habilitados() is False
    finally:
        os.environ.pop('ENGAGEMENT_EMAIL_ENABLED', None)
        if antes is not None:
            os.environ['ENGAGEMENT_EMAIL_ENABLED'] = antes


# ── O corpo ───────────────────────────────────────────────────────────────────────────────────

def test_os_quatro_tipos_montam_corpo_em_PT_com_unsubscribe():
    """Corpo só PT é regra do projeto. O link de descadastro em TODOS não é estética: é LGPD, e
    um e-mail de cobrança sem saída é o que transforma cobrança em spam."""
    for tipo, dados in (('leak_reaberto', _E_REABERTO['dados']),
                        ('relatorio_gerado', _E_RELATO['dados']),
                        ('revisao_vencida', _E_REVISAO['dados']),
                        ('inatividade', _E_INATIVO['dados'])):
        m = montar_email(tipo, dados, 'phpro', 'https://x.test', 'https://x.test/unsub')
        assert m, tipo
        assunto, html = m
        assert assunto and len(assunto) < 90, (tipo, assunto)
        assert 'https://x.test/unsub' in html, f'{tipo} sem link de descadastro'
        assert 'origem=email' in html, f'{tipo} sem origem no CTA (quebra a métrica 1)'
        assert '—' not in html, f'{tipo} tem travessão na copy (regra do projeto)'


def test_o_numero_em_bb_aparece_quando_existe():
    """A primeira linha tem que carregar o FATO. 'Você tem treinos pendentes' é ruído."""
    _, html = montar_email('inatividade', _E_INATIVO['dados'], 'phpro',
                           'https://x.test', 'https://x.test/u')
    assert '14.4bb' in html and '21 mãos' in html


def test_singular_e_plural_da_revisao():
    """Detalhe pequeno que denuncia automação: '1 revisões te esperando'."""
    a, _ = montar_email('revisao_vencida', {'total': 1}, 'p', 'https://x.test', 'https://x.test/u')
    b, _ = montar_email('revisao_vencida', {'total': 4}, 'p', 'https://x.test', 'https://x.test/u')
    assert '1 revisão' in a and '4 revisões' in b


def test_tipo_sem_corpo_devolve_None():
    assert montar_email('inventado', {}, 'p', 'https://x.test', 'https://x.test/u') is None


# ── Ponta a ponta, com banco ──────────────────────────────────────────────────────────────────

def test_relatorio_novo_vira_email_e_o_teto_segura_o_segundo():
    """O 'pronto quando' da Fase 2, forjado: relatório gerado hoje dispara; o evento seguinte,
    na mesma semana, cala."""
    os.environ.pop('DATABASE_URL', None)
    from datetime import datetime
    from database.schema import init_db, get_conn
    from database.repositories import (_adapt, ultimo_email_de_cobranca,
                                       registrar_email_de_cobranca, ultimo_relatorio_de_evolucao)
    from leaklab.cobranca_email import coletar_eventos
    init_db()
    u = 990020
    c = get_conn()
    try:
        c.execute(_adapt('INSERT INTO users (id, email, username, password_hash) VALUES (?,?,?,?)'),
                  (u, 'cob@t.local', 'cob', 'x'))
    except Exception:
        pass
    c.execute(_adapt('DELETE FROM engagement_emails WHERE user_id = ?'), (u,))
    c.execute(_adapt('DELETE FROM evolution_reports WHERE user_id = ?'), (u,))
    agora = datetime.utcnow().isoformat()
    c.execute(_adapt('INSERT INTO evolution_reports (user_id, motivo, snapshot, n_decisoes, '
                     'created_at) VALUES (?,?,?,?,?)'), (u, 'veredito', '{}', 400, agora))
    c.commit(); c.close()

    assert ultimo_relatorio_de_evolucao(u), 'o relatório forjado não foi lido'
    eventos = coletar_eventos(u, agora)
    assert any(e['tipo'] == 'relatorio_gerado' for e in eventos), eventos

    escolhido = decidir_email_cobranca(agora, eventos, ultimo_email_de_cobranca(u))
    assert escolhido and escolhido['tipo'] == 'relatorio_gerado'

    registrar_email_de_cobranca(u, 'relatorio_gerado')
    # Segundo evento na mesma semana: o teto tem que segurar.
    assert decidir_email_cobranca(agora, eventos, ultimo_email_de_cobranca(u)) is None


def test_opt_out_sai_da_varredura_na_ORIGEM():
    """O opt-out é filtrado na consulta, e não no envio: assim nenhum caminho novo pode
    esquecer de checá-lo."""
    os.environ.pop('DATABASE_URL', None)
    from database.schema import init_db, get_conn
    from database.repositories import _adapt, alunos_para_varredura_de_cobranca
    init_db()
    u = 990021
    c = get_conn()
    try:
        c.execute(_adapt('INSERT INTO users (id, email, username, password_hash, role, '
                         'email_opt_in, email_verified) VALUES (?,?,?,?,?,?,?)'),
                  (u, 'optout@t.local', 'optout', 'x', 'player', 1, 1))
    except Exception:
        pass
    c.execute(_adapt('UPDATE users SET email_opt_in = 1, email_verified = 1, role = ? '
                     'WHERE id = ?'), ('player', u))
    c.commit()
    assert any(a['id'] == u for a in alunos_para_varredura_de_cobranca(limite=5000))
    c.execute(_adapt('UPDATE users SET email_opt_in = 0 WHERE id = ?'), (u,))
    c.commit(); c.close()
    assert not any(a['id'] == u for a in alunos_para_varredura_de_cobranca(limite=5000))


if __name__ == '__main__':
    falhas = 0
    testes = (test_primeiro_email_passa_sem_historico,
              test_o_gatilho_mais_FORTE_vence,
              test_a_ordem_de_forca_e_a_da_precedencia,
              test_teto_semanal_vence_ATE_o_gatilho_mais_forte,
              test_sem_evento_nao_manda_nada,
              test_evento_desconhecido_e_ignorado,
              test_exatamente_no_limite_do_teto,
              test_data_ilegivel_nao_trava_o_aluno_para_sempre,
              test_desligado_por_padrao,
              test_os_quatro_tipos_montam_corpo_em_PT_com_unsubscribe,
              test_o_numero_em_bb_aparece_quando_existe,
              test_singular_e_plural_da_revisao,
              test_tipo_sem_corpo_devolve_None,
              test_relatorio_novo_vira_email_e_o_teto_segura_o_segundo,
              test_opt_out_sai_da_varredura_na_ORIGEM)
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
