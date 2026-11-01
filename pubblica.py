"""Pubblica su Instagram il post di oggi, se è in coda e se è arrivata l'ora.

Struttura attesa:
  coda/AAAA-MM-GG/01.jpg, 02.jpg, ...   (JPEG, 1080x1350, in ordine)
  coda/AAAA-MM-GG/descrizione.txt       (la didascalia)
  coda/AAAA-MM-GG/STOP                  (facoltativo: se c'è, il post NON esce)
  orari.json                            (ora di uscita per giorno della settimana)

Segreti / variabili (GitHub > Settings > Secrets and variables > Actions):
  IG_TOKEN    (secret)    token dell'utente di sistema Meta
  account.json            ID dell'account Instagram di Rione
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://graph.facebook.com/v23.0"
TZ = ZoneInfo("Europe/Rome")
ROOT = Path(__file__).resolve().parent


def call(method, path, **params):
    params["access_token"] = os.environ["IG_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data.decode()}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"Errore API {e.code} su {path}: {body}")


def wait_ready(container_id):
    for _ in range(30):
        st = call("GET", container_id, fields="status_code")
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Contenitore {container_id} in stato {code}")
        time.sleep(5)
    raise SystemExit(f"Contenitore {container_id} non pronto dopo 150 secondi")


def git(*args):
    subprocess.run(["git", *args], check=True, cwd=ROOT)


def pulizia(now):
    """Dopo 30 giorni dalla pubblicazione tiene solo esito.json e info.json."""
    changed = False
    for d in sorted((ROOT / "pubblicati").glob("*/esito.json")):
        quando = datetime.fromisoformat(json.loads(d.read_text())["pubblicato_alle"])
        if (now - quando).days >= 30:
            for f in d.parent.iterdir():
                if f.name not in ("esito.json", "info.json"):
                    f.unlink()
                    changed = True
    return changed


def main():
    now = datetime.now(TZ)
    if pulizia(now):
        git("config", "user.name", "rione-bot")
        git("config", "user.email", "rione-bot@users.noreply.github.com")
        git("add", "-A", "pubblicati")
        git("commit", "-m", "Pulizia post pubblicati da oltre 30 giorni")
        git("push")
    day = now.strftime("%Y-%m-%d")
    folder = ROOT / "coda" / day
    if not folder.is_dir():
        print(f"Nessun post in coda per {day}.")
        return
    if (folder / "STOP").exists():
        print(f"Post del {day} fermato (file STOP presente).")
        return

    orari = json.loads((ROOT / "orari.json").read_text())
    hh, mm = map(int, orari[str(now.weekday())].split(":"))
    if (now.hour, now.minute) < (hh, mm):
        print(f"Post del {day} previsto alle {hh:02d}:{mm:02d}, ora sono le {now:%H:%M}.")
        return

    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg"))
    if not images or len(images) > 10:
        raise SystemExit(f"Servono da 1 a 10 JPEG in {folder}, trovati {len(images)}.")
    caption = (folder / "descrizione.txt").read_text(encoding="utf-8").strip()
    if len(caption) > 2200:
        raise SystemExit(f"Descrizione troppo lunga: {len(caption)} caratteri (max 2200).")

    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["GITHUB_SHA"]
    url = lambda p: f"https://raw.githubusercontent.com/{repo}/{sha}/coda/{day}/{urllib.parse.quote(p.name)}"
    ig = os.environ.get("IG_USER_ID") or json.loads((ROOT / "account.json").read_text())["ig_user_id"]

    if len(images) == 1:
        c = call("POST", f"{ig}/media", image_url=url(images[0]), caption=caption)["id"]
    else:
        children = []
        for p in images:
            cid = call("POST", f"{ig}/media", image_url=url(p), is_carousel_item="true")["id"]
            wait_ready(cid)
            children.append(cid)
        c = call("POST", f"{ig}/media", media_type="CAROUSEL",
                 children=",".join(children), caption=caption)["id"]
    wait_ready(c)
    media_id = call("POST", f"{ig}/media_publish", creation_id=c)["id"]
    link = call("GET", media_id, fields="permalink").get("permalink", "")
    print(f"Pubblicato: {link}")

    dest = ROOT / "pubblicati" / day
    dest.parent.mkdir(exist_ok=True)
    shutil.move(str(folder), str(dest))
    (dest / "esito.json").write_text(json.dumps(
        {"media_id": media_id, "permalink": link, "pubblicato_alle": now.isoformat()},
        indent=2, ensure_ascii=False))
    git("config", "user.name", "rione-bot")
    git("config", "user.email", "rione-bot@users.noreply.github.com")
    git("add", "-A", "coda", "pubblicati")
    git("commit", "-m", f"Pubblicato post del {day}")
    git("push")


if __name__ == "__main__":
    main()
