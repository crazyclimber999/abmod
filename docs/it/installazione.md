# Installazione da zero

*[In English](../en/install.md)* · [torna al README](../../README.it.md)

Per una macchina su cui OpenWebRX non c'è. Se OpenWebRX ce l'hai già, usa
[aggiornamento.md](aggiornamento.md), che conserva la tua configurazione.

## Prima di cominciare

- Un sistema di tipo Debian: Raspberry Pi OS, Debian, Ubuntu. Provato su un
  Raspberry Pi 3 con Raspberry Pi OS bullseye.
- Un SDR fra quelli supportati dalla documentazione di OpenWebRX.
- Accesso root, tramite `sudo`.

## Installazione

```bash
git clone <questo repository> abmod
cd abmod
sudo ./install/install.sh
```

Lo script installa OpenWebRX dai suoi pacchetti, fa un backup
dell'installazione intatta, applica ABMod, verifica che ogni file python
compili, riavvia, e aspetta che il ricevitore risponda prima di dirti che è
andata bene.

Se il pacchetto `openwebrx` non è disponibile sulla tua macchina, lo script si
ferma e lo dice. Aggiungi il repository di OpenWebRX — le istruzioni aggiornate
sono nel [suo wiki](https://github.com/jketterl/openwebrx/wiki) — e rilancia lo
script, che riprende da lì. ABMod di proposito non porta con sé una copia di
quegli indirizzi: un URL vecchio incorporato qui fallirebbe in modo confuso fra
un anno.

## Poi, in quest'ordine

**1. Crea il primo amministratore.** I settings e le memorie richiedono il
login, e senza questo passaggio non entra nessuno:

```bash
sudo openwebrx admin adduser <nome>
```

**2. Apri `http://<la macchina>:8073/settings`** e imposta almeno:

- **Receiver details** — nome, località e le coordinate. Le coordinate non sono
  decorative: decidono dove si centra la mappa, dove il beacon APRS dice che sei,
  e il punto da cui il filtro di ricevibilità misura ogni percorso.
- **SDR devices and profiles** — il tuo ricevitore e le bande che vuoi.
- **Receiving antenna** — almeno l'altezza dal suolo.

**3. Facoltativo, sotto General settings:**

- una **chiave API aprs.fi**, per mostrare stazioni che non senti direttamente
- una **passcode APRS-IS**, per inoltrare ciò che senti
- il **raggio dei dati altimetrici**, se vuoi il filtro di ricevibilità

In [configurazione.md](configurazione.md) c'è cosa fa ogni impostazione.

## Se qualcosa va storto

Lo script stampa la cartella del backup. Per annullare tutto:

```bash
sudo ./install/rollback.sh /root/abmod-backup-AAAAmmgg-HHMMSS
```

Per vedere di cosa si lamenta il ricevitore:

```bash
journalctl -u openwebrx -n 50
```
