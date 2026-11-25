# Aggiornamento di un ricevitore esistente

*[In English](../en/upgrade.md)* · [torna al README](../../README.it.md)

Per una macchina che fa già girare OpenWebRX. Configurazione, memorie e utenti
vengono conservati.

## Prima di cominciare

- **OpenWebRX v1.2.2.** ABMod è stato costruito e provato su quella versione.
  Lo script avvisa e chiede conferma su qualunque altra.
- Accesso root, tramite `sudo`.
- Due minuti di interruzione mentre il servizio riparte.

## Aggiornamento

```bash
git clone <questo repository> abmod
cd abmod
sudo ./install/upgrade.sh
```

Cosa fa, in ordine:

1. **Trova OpenWebRX** invece di dare per scontato dove sia — Debian, pip e
   versioni diverse di python lo mettono in posti diversi.
2. **Controlla la versione** e chiede conferma se non è la 1.2.2.
3. **Fa il backup** di `owrx/` e `htdocs/`, più `settings.json`,
   `bookmarks.json`, `users.json` e `bands.json`, in
   `/root/abmod-backup-<data>` — e **rilegge l'archivio** prima di proseguire.
   Un backup che nessuno ha verificato non è un backup.
4. **Installa i file di ABMod** e verifica che ogni file python compili. Un
   errore di sintassi qui manda giù tutto il ricevitore, ed è molto più
   economico scoprirlo adesso.
5. **Propone `python3-xlrd`**, che serve solo a importare vecchi file `.xls`.
6. **Riavvia e aspetta che il ricevitore risponda**, poi segnala eventuali
   traceback nel log.
7. **Svuota la cache di Varnish**, se ne hai una.

Niente viene modificato prima che il passo 3 sia riuscito.

## Dopo l'aggiornamento

**Memorie e settings ora richiedono il login.** Se non hai ancora utenti,
creane uno prima di averne bisogno:

```bash
sudo openwebrx admin adduser <nome>
```

**Imposta l'altezza dell'antenna** in Settings → General → Receiving antenna.
Il filtro di ricevibilità ne ha bisogno, e il valore predefinito di 10 m è solo
un'ipotesi sulla tua stazione.

**Controlla le coordinate del ricevitore** in Receiver details. Probabilmente
erano già giuste, ma ora ABMod le usa per più cose della sola mappa.

Tutto il resto continua a funzionare come prima. Le memorie che avevi restano
intatte e compaiono nel nuovo pannello.

## Tornare indietro

```bash
sudo ./install/rollback.sh /root/abmod-backup-AAAAmmgg-HHMMSS
```

Ripristina `owrx/` e `htdocs/` dall'archivio. Di proposito **non** ripristina la
configurazione: l'aggiornamento non l'ha mai toccata, quindi quella sulla
macchina è la tua ed è più recente. Le copie sono nella cartella del backup se
ti servono.

## Aggiornare ABMod in seguito

Scarica la versione nuova e rilancia `upgrade.sh`. Fa un backup ogni volta e
valgono gli stessi controlli.
