"""Raccoglie gli Insights dell'account Instagram di Rione e li salva in
insights/AAAA-MM-GG.json (NON pubblica nulla).

Contiene: profilo (follower, n. post), metriche dell'account giorno per giorno
degli ultimi 28 giorni, demografia dei follower (se disponibile) e le metriche
di ogni post degli ultimi 60 giorni. Le metriche che Meta non restituisce
vengono registrate in "errori" invece di fermare lo script.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://graph.facebook.com/v23.0"
TZ = ZoneInfo("Europe/Rome")
ROOT = Path(__file__).resolve().parent
errori = []


def get(path, **params):
    params["access_token"] = os.environ["IG_TOKEN"]
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read() or b"{}").get("error", {}).get("message")
        except Exception:
            msg = None
        errori.append({"chiamata": path, "parametri": {k: v for k, v in params.items() if k != "access_token"},
                       "codice": e.code, "messaggio": msg})
        return None


def paged(path, limite=200, **params):
    out, r = [], get(path, **params)
    while r and r.get("data"):
        out += r["data"]
        nxt = r.get("paging", {}).get("next")
        if not nxt or len(out) >= limite:
            break
        try:
            with urllib.request.urlopen(nxt, timeout=60) as resp:
                r = json.loads(resp.read())
        except urllib.error.HTTPError:
            break
    return out


ig = os.environ.get("IG_USER_ID") or json.load(open(ROOT / "account.json"))["ig_user_id"]
ora = datetime.now(timezone.utc)
dati = {"raccolto_il": ora.astimezone(TZ).isoformat(), "account_id": ig}

dati["profilo"] = get(ig, fields="username,followers_count,follows_count,media_count")

# --- Account: valori giornalieri degli ultimi 28 giorni ---
fine = int(ora.timestamp())
inizio = int((ora - timedelta(days=28)).timestamp())
giornaliere = {}
for m in ["reach", "follower_count"]:
    r = get(f"{ig}/insights", metric=m, period="day", since=inizio, until=fine)
    if r:
        for serie in r.get("data", []):
            giornaliere[serie["name"]] = [{"giorno": v["end_time"][:10], "valore": v["value"]}
                                          for v in serie.get("values", [])]
dati["account_giornaliero"] = giornaliere

# Totali per finestre di 7 giorni (ultime 4 settimane), per confrontare l'andamento
totali_metriche = ["reach", "views", "accounts_engaged", "total_interactions", "likes", "comments",
                   "shares", "saves", "replies", "follows_and_unfollows", "profile_links_taps"]
settimane = []
for i in range(4):
    a = ora - timedelta(days=7 * (i + 1))
    b = ora - timedelta(days=7 * i)
    sett = {"dal": a.astimezone(TZ).date().isoformat(), "al": b.astimezone(TZ).date().isoformat()}
    for m in totali_metriche:
        r = get(f"{ig}/insights", metric=m, period="day", metric_type="total_value",
                since=int(a.timestamp()), until=int(b.timestamp()))
        if r and r.get("data"):
            tv = r["data"][0].get("total_value", {})
            sett[m] = tv.get("value")
            if tv.get("breakdowns"):
                sett[m + "_dettaglio"] = tv["breakdowns"]
    settimane.append(sett)
dati["account_settimane"] = settimane

# Da dove arriva la copertura (follower / non follower) e tipo di contenuto, ultimi 28 giorni
dettagli = {}
for m, bd in [("reach", "follow_type"), ("reach", "media_product_type"),
              ("views", "follow_type"), ("total_interactions", "media_product_type"),
              ("profile_links_taps", "contact_button_type")]:
    r = get(f"{ig}/insights", metric=m, period="day", metric_type="total_value", breakdown=bd,
            since=inizio, until=fine)
    if r and r.get("data"):
        dettagli[f"{m}_per_{bd}"] = r["data"][0].get("total_value")
dati["account_dettagli_28gg"] = dettagli

# Demografia (Meta la dà solo sopra i 100 follower)
demo = {}
for m in ["follower_demographics", "engaged_audience_demographics"]:
    for bd in ["city", "age", "gender"]:
        r = get(f"{ig}/insights", metric=m, period="lifetime", timeframe="this_month",
                metric_type="total_value", breakdown=bd)
        if r and r.get("data"):
            demo[f"{m}_{bd}"] = r["data"][0].get("total_value")
dati["demografia"] = demo

# Orari in cui i follower sono online (può non essere disponibile)
r = get(f"{ig}/insights", metric="online_followers", period="lifetime",
        since=int((ora - timedelta(days=2)).timestamp()), until=fine)
dati["follower_online"] = r.get("data") if r else None

# --- Post degli ultimi 60 giorni ---
media = paged(f"{ig}/media", fields="id,caption,media_type,media_product_type,timestamp,permalink,"
                                    "like_count,comments_count")
limite_data = ora - timedelta(days=60)
post = []
for p in media:
    quando = datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
    if quando < limite_data:
        continue
    metriche = ["reach", "views", "likes", "comments", "shares", "saved", "total_interactions",
                "profile_visits", "follows", "profile_activity"]
    if p.get("media_product_type") == "REELS":
        metriche += ["ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
    valori = {}
    for m in metriche:  # una per volta: se una non è supportata le altre arrivano lo stesso
        r = get(f"{p['id']}/insights", metric=m)
        if r and r.get("data"):
            d = r["data"][0]
            valori[m] = d.get("values", [{}])[0].get("value", d.get("total_value", {}).get("value"))
    post.append({
        "id": p["id"],
        "pubblicato": quando.astimezone(TZ).isoformat(),
        "giorno_settimana": quando.astimezone(TZ).strftime("%A"),
        "tipo": p.get("media_type"),
        "formato": p.get("media_product_type"),
        "link": p.get("permalink"),
        "caption": (p.get("caption") or "")[:600],
        "like": p.get("like_count"),
        "commenti": p.get("comments_count"),
        "insights": valori,
    })
    time.sleep(0.2)
dati["post"] = post
dati["errori"] = errori

out = ROOT / "insights" / f"{ora.astimezone(TZ).date().isoformat()}.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(dati, indent=2, ensure_ascii=False))
print(f"Salvato {out.name}: {len(post)} post, {len(errori)} metriche non disponibili")
for e in errori[:15]:
    print(" -", e["chiamata"], e["parametri"].get("metric"), e["codice"], e["messaggio"])
