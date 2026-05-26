import json, os
with open(os.path.join(os.path.dirname(__file__), '..', 'docs', 'leaklab_gto_ranges.json')) as f:
    data = json.load(f)

print('=== STACK BUCKET BOUNDS ===')
for bk, bounds in data['stack_buckets'].items():
    print(f'  {bk}: {bounds}')

print()
print('=== BTN RFI per bucket ===')
for bk in ['10bb','14bb','20bb','30bb']:
    rfi = data['ranges'][bk].get('RFI',{}).get('BTN',{})
    hands = rfi.get('hands','')[:100]
    print(f'  [{bk}] pct={rfi.get("pct")} acoes={rfi.get("acoes")} hands={hands}')

print()
print('=== CO RFI per bucket ===')
for bk in ['10bb','14bb','20bb','30bb']:
    rfi = data['ranges'][bk].get('RFI',{}).get('CO',{})
    hands = rfi.get('hands','')[:100]
    print(f'  [{bk}] pct={rfi.get("pct")} acoes={rfi.get("acoes")} hands={hands}')
