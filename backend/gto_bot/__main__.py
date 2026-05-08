"""
CLI do GTO Bot — ponto de entrada via  python -m gto_bot  <comando>

COMANDOS:
  discover          Abre browser e loga TODAS as chamadas JSON do GTO Wizard
                    → identifica o endpoint de solução correto
                    → salva em discovery_log.jsonl

  analyze-discovery Mostra resumo do discovery_log.jsonl gerado acima

  passive           Abre browser e captura soluções automaticamente
                    (requer parser.py configurado com o endpoint correto)

  har <arquivo.har> Importa nós GTO de um arquivo HAR exportado do DevTools

  har-discover <f>  Modo discovery via HAR (lista chamadas JSON sem parsear)

  stats             Mostra estatísticas da base GTO no LeakLabs

  missing           Lista spots sem GTO data (para priorizar a coleta)

  test-parser       Testa o parser com dados sintéticos

EXEMPLOS:
  python -m gto_bot discover
  python -m gto_bot analyze-discovery
  python -m gto_bot har ~/Downloads/capture.har
  python -m gto_bot stats
  python -m gto_bot missing
"""
from __future__ import annotations
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('gto_bot')


def _cmd_discover():
    from .crawler import run_passive
    run_passive(discover=True)


def _cmd_analyze_discovery():
    from .config import DISCOVERY_LOG
    p = Path(DISCOVERY_LOG)
    if not p.exists():
        print(f'Arquivo não encontrado: {DISCOVERY_LOG}')
        print('Execute primeiro: python -m gto_bot discover')
        return

    entries = []
    with open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass

    if not entries:
        print('discovery_log.jsonl está vazio.')
        return

    print(f'\n{len(entries)} chamadas JSON capturadas:\n')
    seen_urls: dict[str, int] = {}
    for e in entries:
        base = e['url'].split('?')[0]
        seen_urls[base] = seen_urls.get(base, 0) + 1

    print('URLs únicas (mais frequentes primeiro):')
    for url, count in sorted(seen_urls.items(), key=lambda x: -x[1])[:20]:
        print(f'  {count:>4}x  {url}')

    print('\nPrimeiras 5 entradas com detalhes:')
    for e in entries[:5]:
        print(f'\n  {e["method"]} {e["url"][:80]}')
        print(f'  Keys: {e["keys"]}')
        print(f'  Preview: {e["preview"][:150]}')

    print(f'\nARQUIVO COMPLETO: {DISCOVERY_LOG}')
    print('Abra-o em qualquer editor para ver o JSON completo de cada chamada.')
    print('\nPróximo passo: atualize SOLUTION_URL_PATTERNS e parse_response()')
    print('no arquivo parser.py com o endpoint e formato que você identificou.')


def _cmd_passive():
    from .crawler import run_passive
    run_passive(discover=False)


def _cmd_har(args: list[str]):
    if not args:
        print('Uso: python -m gto_bot har <arquivo.har> [--dry-run]')
        return
    har_path = args[0]
    dry_run  = '--dry-run' in args
    from .har_importer import import_har
    import_har(har_path, dry_run=dry_run)


def _cmd_har_discover(args: list[str]):
    if not args:
        print('Uso: python -m gto_bot har-discover <arquivo.har>')
        return
    from .har_importer import discover_har
    discover_har(args[0])


def _cmd_stats():
    from .sender import get_stats
    stats = get_stats()
    if not stats:
        print('Não foi possível conectar ao LeakLabs backend.')
        print('Verifique LEAKLAB_URL e LEAKLAB_ADMIN_TOKEN no .env')
        return
    print(f'\nBase GTO — LeakLabs')
    print(f'  Total de nós : {stats.get("total", 0)}')
    by_s = stats.get('by_street', {})
    by_p = stats.get('by_position', {})
    if by_s:
        print('  Por street   :', {k: v for k, v in sorted(by_s.items())})
    if by_p:
        print('  Por posição  :', {k: v for k, v in sorted(by_p.items())})


def _cmd_missing():
    from .sender import get_missing_spots
    spots = get_missing_spots(limit=20)
    if not spots:
        print('Nenhum spot faltante encontrado (ou backend inacessível).')
        return
    print(f'\nTop {len(spots)} spots para coletar no GTO Wizard:\n')
    print(f'  {"Hash":<18} {"Street":<8} {"Pos":<5} {"Stack BB":>9} {"Freq":>5}')
    print(f'  {"-"*18} {"-"*8} {"-"*5} {"-"*9} {"-"*5}')
    for s in spots:
        print(f'  {s["spot_hash"]:<18} {s["street"]:<8} {s["position"]:<5} '
              f'{s["stack_bb"]:>9.1f} {s.get("frequency", 1):>5}')


def _cmd_test_parser():
    from .parser import parse_response
    from .models import GtoNode

    # Teste com Formato B
    mock_response = {
        'spot': {'street': 'flop', 'pos': 'BTN', 'board': ['Ah','Kd','2c'],
                 'hand': ['As','Ks'], 'stack': 25.0},
        'strategy': {'fold': 0.05, 'call': 0.28, 'raise': 0.67},
        'ev': {'fold': 0.0, 'call': 0.8, 'raise': 1.2},
    }
    nodes = parse_response('https://app.gtowizard.com/api/strategy', None, mock_response)

    if nodes:
        n = nodes[0]
        print(f'\nParser OK — nó gerado:')
        print(f'  Street  : {n.street}')
        print(f'  Position: {n.position}')
        print(f'  Action  : {n.gto_action}  ({n.gto_freq:.0%})')
        print(f'  EV diff : {n.ev_diff}')
        print('\nSe os valores acima fazem sentido, o parser está funcionando.')
        print('Ajuste parse_response() no parser.py conforme o formato real do GTO Wizard.')
    else:
        print('Parser retornou lista vazia com o mock de Formato B.')
        print('Verifique parse_response() em parser.py.')


def main():
    args = sys.argv[1:]
    cmd  = args[0] if args else ''

    from .config import validate
    errs = validate()

    commands_no_validate = {'stats', 'missing', 'test-parser', 'har-discover',
                             'analyze-discovery', ''}
    if errs and cmd not in commands_no_validate:
        print('\n[AVISO] Configuração incompleta:')
        for e in errs:
            print(f'  • {e}')
        print(f'\nCopie .env.example para .env e preencha os valores:')
        print(f'  copy backend\\gto_bot\\.env.example backend\\gto_bot\\.env\n')

    if cmd == 'discover':
        _cmd_discover()
    elif cmd == 'analyze-discovery':
        _cmd_analyze_discovery()
    elif cmd == 'passive':
        _cmd_passive()
    elif cmd == 'har':
        _cmd_har(args[1:])
    elif cmd == 'har-discover':
        _cmd_har_discover(args[1:])
    elif cmd == 'stats':
        _cmd_stats()
    elif cmd == 'missing':
        _cmd_missing()
    elif cmd == 'test-parser':
        _cmd_test_parser()
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
