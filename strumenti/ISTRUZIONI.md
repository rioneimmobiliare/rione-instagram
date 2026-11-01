# Istruzioni per il controllo settimanale (Claude)

## Fonte
- Cartella Google Drive "IG --> Rione" (id in `registro.json` → `cartella_drive_id`), account luxantia.immobiliare@gmail.com.
- Ogni post è uno zip `Rione_Post_NN_JPEG.zip` (oppure una cartella "Post NN - …") con: JPG in ordine, `Descrizione.txt`, `Testi_slide.txt` e/o `Note_per_Claude.txt` / `Note_e_fonti.txt`.
- Un post è "nuovo" se il suo numero NN non è in `registro.json` → `post`.

## Scaricare da Drive
`download_file_content` restituisce base64; se il risultato è troppo grande viene salvato su file JSON `{content,title,…}`: decodificarlo con Python (`base64.b64decode`). Estrarre gli zip in una cartella vuota, solo i nomi base dei file.

## Slide
- Le slide generate da codice (sfondo perfettamente piatto) sono già nitide: NON pulirle.
- Le slide fatte come immagine AI (sfondo con grana) vanno pulite con `python3 strumenti/clean_slide.py src dst`.
  Test grana: media di `abs(diff)` orizzontale sul riquadro y 10-60, x 1000-1070; > 0.1 ⇒ immagine AI.
- Dopo la pulizia guardare SEMPRE prima/dopo: le foto devono restare identiche, nessuna macchia, nessun riquadro chiaro sparito. In caso di difetto, rimettere l'originale in quella zona.
- Requisiti Instagram: JPEG, da 1 a 10 immagini per post.

## Descrizione (stile approvato da Cristiano)
Usare come modello `strumenti/esempio_descrizione.txt`. Struttura:
1. Gancio con domanda o situazione concreta + 1 emoji.
2. 1-2 frasi di contesto.
3. Elenco con 🔹 (dai testi delle slide).
4. "E attenzione: …" con la distinzione chiave del post.
5. Elenco numerato 1️⃣ 2️⃣ 3️⃣ con i passi pratici.
6. Frase di chiusura.
7. 📌 invito a salvare/inviare + 📩 "Scrivici "PAROLA" in DM" (parola chiave in maiuscolo, a tema).
8. Avvertenze di GPT (immagini illustrative, schemi non in scala, fonti).
9. 5-6 hashtag minuscoli: tema + #casaroma #immobiliareroma #agenziaimmobiliare.
Non inventare dati, cifre o promesse; restare fedeli ai testi delle slide. Max 2200 caratteri.

## Messa in coda
- Un post al giorno, in ordine di numero, a partire dal giorno dopo l'ultima data presente in `coda/` o `pubblicati/` (mai prima di domani).
- Cartella `coda/AAAA-MM-GG/` con `01.jpg, 02.jpg, …`, `descrizione.txt`, `info.json` `{"post": NN}`.
- Aggiungere il post a `registro.json` con `drive_ids` (zip o cartella) e `data`.
- Se un post ha un problema non risolvibile (slide mancanti, conti che non tornano, testo incoerente): NON metterlo in coda, saltarlo e avvisare.

## Pulizia dopo 30 giorni
Per ogni post in `registro.json` la cui `pubblicati/AAAA-MM-GG/esito.json` ha `pubblicato_alle` da ≥ 30 giorni e `drive_ids` non ancora cestinati: `trash_file` su ogni id, poi segnare `"cestinato": true`. (Le immagini su GitHub le toglie già `pubblica.py`.)
