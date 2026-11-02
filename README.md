# Rione Immobiliare – pubblicazione automatica su Instagram

- `coda/AAAA-MM-GG/` – un post per giorno: `01.jpg`, `02.jpg`, … e `descrizione.txt`.
  Per fermare un post basta aggiungere nella sua cartella un file chiamato `STOP`.
- `orari.json` – ora di uscita per giorno della settimana (0 = lunedì … 6 = domenica), fuso di Roma.
- `pubblicati/` – archivio dei post usciti, con link e ora di pubblicazione.
- Azione **Pubblica post del giorno** – gira ogni 30 minuti e pubblica quando è l'ora.
- Azione **Verifica collegamento** – test manuale, non pubblica nulla.

Per ora si pubblica un giorno sì e uno no: i giorni intermedi restano vuoti nella coda.
