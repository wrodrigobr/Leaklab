# GTO Bot — Especificação de Integração

Este documento descreve o protocolo para o bot que coleta dados do GTO Wizard e popula a base `gto_nodes` do LeakLabs.

## Endpoint de destino

```
POST /admin/gto/nodes
Authorization: Bearer <admin_token>
Content-Type: application/json
```

## Payload

```json
{
  "nodes": [
    {
      "street":        "flop",
      "position":      "BTN",
      "board":         ["Ah", "Kd", "2c"],
      "hero_hand":     ["As", "Ks"],
      "hero_stack_bb": 25.0,
      "gto_action":    "raise",
      "gto_freq":      0.67,
      "ev_diff":       1.2
    }
  ]
}
```

### Campos

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `street` | string | sim | `"preflop"`, `"flop"`, `"turn"`, `"river"` |
| `position` | string | sim | `"BTN"`, `"CO"`, `"MP"`, `"UTG"`, `"SB"`, `"BB"` |
| `board` | string[] | sim | Cartas do board — lista vazia no preflop |
| `hero_hand` | string[] | sim | Duas cartas do hero, ex: `["As","Ks"]` |
| `hero_stack_bb` | float | sim | Stack do hero em big blinds |
| `gto_action` | string | sim | Ação GTO recomendada: `"fold"`, `"call"`, `"raise"`, `"jam"` |
| `gto_freq` | float | sim | Frequência GTO da ação (0.0–1.0) |
| `ev_diff` | float | não | Diferença de EV em BBs entre esta ação e a segunda melhor |

**Observação:** o `spot_hash` é computado pelo backend — não enviar.

## Buckets de stack

O backend discretiza o stack em 6 buckets:

| Range | Bucket |
|---|---|
| 0–9.99 BB | `0-10bb` |
| 10–19.99 BB | `10-20bb` |
| 20–34.99 BB | `20-35bb` |
| 35–59.99 BB | `35-60bb` |
| 60–99.99 BB | `60-100bb` |
| 100+ BB | `100bb+` |

## Limites

- Máximo de **500 nós por request**
- Envios repetidos do mesmo spot (mesmo hash) substituem o registro anterior (`INSERT OR REPLACE`)

## Resposta

```json
{ "inserted": 23 }
```

## Endpoints auxiliares

### Verificar stats da base

```
GET /admin/gto/stats
Authorization: Bearer <admin_token>
```

```json
{
  "total": 1250,
  "by_street": { "flop": 820, "turn": 300, "river": 130 },
  "by_position": { "BTN": 400, "CO": 300, "MP": 200, "BB": 350 }
}
```

### Spots prioritários para coletar

```
GET /admin/gto/missing-spots?limit=100
Authorization: Bearer <admin_token>
```

Retorna spots que aparecem frequentemente nas decisões dos usuários mas ainda não têm nó GTO, ordenados por frequência descendente:

```json
{
  "spots": [
    {
      "spot_hash":  "a3f8b2c1d4e5f6a7",
      "street":     "flop",
      "position":   "BTN",
      "board":      ["Ah", "Kd", "2c"],
      "hero_hand":  ["As", "Ks"],
      "stack_bb":   25.0,
      "frequency":  87
    }
  ]
}
```

## Hash determinístico (para validação)

O mesmo spot deve produzir o mesmo hash em qualquer linguagem. Algoritmo:

```python
import hashlib, json

def compute_spot_hash(street, position, board, hero_hand, hero_stack_bb):
    BUCKETS = [
        (0, 10, "0-10bb"), (10, 20, "10-20bb"), (20, 35, "20-35bb"),
        (35, 60, "35-60bb"), (60, 100, "60-100bb"), (100, float("inf"), "100bb+"),
    ]
    bucket = next(label for lo, hi, label in BUCKETS if lo <= hero_stack_bb < hi)
    canonical = {
        "board":        sorted(board),
        "hand":         sorted(hero_hand),
        "position":     position.upper(),
        "stack_bucket": bucket,
        "street":       street.lower(),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True).encode()
    ).hexdigest()[:16]
```

Para outras linguagens: serializar `canonical` como JSON com chaves em ordem alfabética (`sort_keys=True`), encodar em UTF-8, aplicar SHA256, e tomar os primeiros 16 caracteres hex.
