"""Pubblica su Instagram il post di oggi, se è in coda e se è arrivata l'ora.

Struttura attesa:
  coda/AAAA-MM-GG/01.jpg, 02.jpg, ...   (JPEG, 1080x1350, in ordine)
  coda/AAAA-MM-GG/descrizione.txt       (la didascalia)
  coda/AAAA-MM-GG/STOP                  (facoltativo: se c'è, il post NON esce)
  coda/AAAA-MM-GG/TENTATIVO_FALLITO.txt (creato dallo script se Instagram rifiuta:
                                         blocca i nuovi tentativi; cancellalo per riprovare)
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
ANTICIPO_MAX = 2 * 60 * 60  # secondi


class ApiError(Exception):
    def __init__(self, status, path, body):
        super().__init__(f"Errore API {status} su {path}: {body}")
        self.status, self.path, self.body = status, path, body


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
        raise ApiError(e.code, path, body)


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


def salva(paths, msg):
    git("config", "user.name", "rione-bot")
    git("config", "user.email", "rione-bot@users.noreply.github.com")
    git("add", "-A", *paths)
    git("commit", "-m", msg)
    for _ in range(3):
        try:
            git("push")
            return
        except subprocess.CalledProcessError:
            git("pull", "--rebase")
    git("push")


def _norm(t):
    return " ".join((t or "").split())


def gia_pubblicato(ig, caption, dopo):
    """Cerca tra gli ultimi post dell'account uno con la stessa didascalia,
    uscito dopo `dopo`. Restituisce (media_id, permalink) oppure None."""
    try:
        recenti = call("GET", f"{ig}/media", fields="id,caption,timestamp,permalink", limit=10)
    except ApiError as e:
        print(f"Impossibile controllare i post recenti: {e}")
        return None
    for m in recenti.get("data", []):
        quando = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        if quando >= dopo and _norm(m.get("caption")) == _norm(caption):
            return m["id"], m.get("permalink", "")
    return None


def archivia(folder, day, media_id, link, quando, nota=None):
    dest = ROOT / "pubblicati" / day
    dest.parent.mkdir(exist_ok=True)
    shutil.move(str(folder), str(dest))
    esito = {"media_id": media_id, "permalink": link, "pubblicato_alle": quando.isoformat()}
    if nota:
        esito["nota"] = nota
    (dest / "esito.json").write_text(json.dumps(esito, indent=2, ensure_ascii=False))
    salva(["coda", "pubblicati"], f"Pubblicato post del {day}")


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
        salva(["pubblicati"], "Pulizia post pubblicati da oltre 30 giorni")
    day = now.strftime("%Y-%m-%d")
    folder = ROOT / "coda" / day
    if not folder.is_dir():
        print(f"Nessun post in coda per {day}.")
        return
    if (folder / "STOP").exists():
        print(f"Post del {day} fermato (file STOP presente).")
        return
    fallito = folder / "TENTATIVO_FALLITO.txt"
    if fallito.exists():
        print(f"Post del {day}: un tentativo è già fallito, non riprovo da solo "
              f"(cancella {fallito.name} per riprovare).\n" + fallito.read_text(encoding="utf-8"))
        return

    orari = json.loads((ROOT / "orari.json").read_text())
    hh, mm = map(int, orari[str(now.weekday())].split(":"))
    if (now.hour, now.minute) < (hh, mm):
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        attesa = (target - now).total_seconds()
        # GitHub avvia i controlli programmati anche con un'ora di ritardo:
        # parto in anticipo (fino a 2 ore prima) e aspetto qui l'orario esatto.
        if attesa > ANTICIPO_MAX:
            print(f"Post del {day} previsto alle {hh:02d}:{mm:02d}, ora sono le {now:%H:%M}.")
            return
        print(f"Post del {day} previsto alle {hh:02d}:{mm:02d}: attendo {attesa / 60:.0f} minuti.")
        time.sleep(attesa)
        now = datetime.now(TZ)
        if not folder.is_dir() or (folder / "STOP").exists():
            print("Post rimosso o fermato durante l'attesa.")
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

    # Il post potrebbe essere già uscito (es. errore dopo la pubblicazione o push fallito):
    # in quel caso lo registro e basta, senza ripubblicarlo.
    inizio_giorno = now.replace(hour=0, minute=0, second=0, microsecond=0)
    trovato = gia_pubblicato(ig, caption, inizio_giorno)
    if trovato:
        print(f"Il post del {day} risulta già pubblicato: {trovato[1]} — lo registro senza ripubblicarlo.")
        archivia(folder, day, trovato[0], trovato[1], now, nota="trovato già pubblicato")
        return

    try:
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
    except ApiError as e:
        # Instagram a volte pubblica comunque e risponde con errore: aspetto e controllo.
        time.sleep(20)
        trovato = gia_pubblicato(ig, caption, inizio_giorno)
        if trovato:
            print(f"Instagram ha risposto con errore ma il post è uscito: {trovato[1]}\n({e})")
            archivia(folder, day, trovato[0], trovato[1], now,
                     nota=f"pubblicato nonostante errore API: {e}")
            return
        # Non è uscito: blocco i nuovi tentativi automatici per non insistere con Instagram.
        (folder / "TENTATIVO_FALLITO.txt").write_text(
            f"{now:%Y-%m-%d %H:%M} — {e}\n", encoding="utf-8")
        salva(["coda"], f"Tentativo fallito per il post del {day}")
        raise SystemExit(str(e))

    print(f"Pubblicato: {link}")
    archivia(folder, day, media_id, link, now)

if __name__ == "__main__":
    main()
