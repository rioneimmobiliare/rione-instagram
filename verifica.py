"""Test di collegamento: NON pubblica nulla.
Controlla che il token funzioni e trova l'ID dell'account Instagram di Rione."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v23.0"


def get(path, **params):
    params["access_token"] = os.environ["IG_TOKEN"]
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"errore": e.code, "dettaglio": json.loads(e.read() or b"{}").get("error", {}).get("message")}


def show(title, data):
    print(f"\n== {title}\n{json.dumps(data, indent=2, ensure_ascii=False)}")


me = get("me", fields="id,name")
show("Utente del token", me)

candidates = set()
if os.environ.get("IG_USER_ID"):
    candidates.add(os.environ["IG_USER_ID"])
if os.path.exists("account.json"):
    candidates.add(json.load(open("account.json"))["ig_user_id"])

pages = get("me/accounts", fields="name,instagram_business_account{id,username}")
show("Pagine collegate", pages)
for p in pages.get("data", []):
    if p.get("instagram_business_account"):
        candidates.add(p["instagram_business_account"]["id"])

biz = get("me/businesses", fields="id,name")
show("Portfolio business", biz)
for b in biz.get("data", []):
    for edge in ("owned_instagram_accounts", "instagram_accounts"):
        r = get(f"{b['id']}/{edge}", fields="id,username")
        show(f"{b.get('name')} / {edge}", r)
        for a in r.get("data", []):
            candidates.add(a["id"])

ok = []
for cid in sorted(candidates):
    info = get(cid, fields="id,username,media_count")
    lim = get(f"{cid}/content_publishing_limit", fields="quota_usage,config")
    show(f"Account {cid}", {"profilo": info, "limite_pubblicazione": lim})
    if "errore" not in info and "errore" not in lim:
        ok.append((cid, info.get("username")))

print("\n==========")
if ok:
    for cid, user in ok:
        print(f"OK: @{user} -> IG_USER_ID = {cid}")
else:
    print("Nessun account Instagram utilizzabile trovato con questo token.")
