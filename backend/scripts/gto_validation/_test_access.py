import requests, json, sys

ACCESS = sys.argv[1] if len(sys.argv) > 1 else ""

params = {
    "gametype": "MTTGeneral_8m",
    "depth": 20.125,
    "stacks": "20.125-20.125-20.125-20.125-20.125-20.125-20.125-20.125",
    "preflop_actions": "R2-F-C-F-F-F-F-R6.5-C-F",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "Ad6h5d",
}
headers = {
    "Authorization": f"Bearer {ACCESS}",
    "Accept": "application/json, text/plain, */*",
    "gwclientid": "790ab864-ed0c-4545-9e5a-97efe89672cd",
    "Origin": "https://app.gtowizard.com",
    "Referer": "https://app.gtowizard.com/",
}
r = requests.get("https://api.gtowizard.com/v4/solutions/spot-solution/", params=params, headers=headers, timeout=15)
print(f"Status: {r.status_code}")
if r.ok:
    data = r.json()
    actions = data.get("action_solutions", [])
    print(f"Actions: {len(actions)}")
    for a in actions:
        typ = a["action"]["type"]
        freq = a["total_frequency"]
        print(f"  {typ}: {freq*100:.1f}%")
else:
    print(f"Body: {r.text[:300]}")
