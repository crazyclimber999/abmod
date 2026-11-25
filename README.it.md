# ABMod per OpenWebRX

*[Read in English](README.md)*

Un insieme di modifiche a **OpenWebRX**, il ricevitore SDR open source via web,
pensate per stazioni radioamatoriali che vogliono memorie che valga la pena
tenere, la decodifica delle chiamate selettive, una mappa che non chiede chiavi
API, e un modo di importare un elenco nazionale di ponti senza annegarci.

ABMod **non è un fork**. È un insieme di file modificati e aggiunti che si
appoggiano a un'installazione esistente di OpenWebRX, e si rimuove ripristinando
il backup che l'installatore prende da solo.

---

## Due strade

**Non hai ancora OpenWebRX** → [Installazione da zero](docs/it/installazione.md)

```bash
git clone https://github.com/crazyclimber999/abmod.git abmod
cd abmod
sudo ./install/install.sh
```

**Hai già OpenWebRX** → [Aggiornamento di un ricevitore esistente](docs/it/aggiornamento.md)

```bash
git clone https://github.com/crazyclimber999/abmod.git abmod
cd abmod
sudo ./install/upgrade.sh
```

In entrambi i casi nulla viene modificato finché non è stato preso un backup
**e riletto**, e alla fine lo script verifica che il ricevitore abbia davvero
risposto. Se non l'ha fatto, un comando rimette tutto com'era:

```bash
sudo ./install/rollback.sh /root/abmod-backup-AAAAmmgg-HHMMSS
```

Il tuo `settings.json`, le tue memorie e i tuoi utenti non vengono toccati da
nessuno dei due script.

---

## Cosa aggiunge

Il racconto completo, con le ragioni delle scelte, è in
[tutte le funzionalità](docs/it/funzionalita.md).

**Controllo degli accessi.** Le memorie richiedono il login, i settings un
amministratore. Una pagina di gestione utenti, ruoli veri, un logout che
disconnette davvero — quello originale era un segnaposto che non faceva nulla —
e sessioni che sopravvivono a un riavvio.

**Memorie che servono a qualcosa.** Un pannello nel ricevitore con ricerca,
ordinamento, modifica e sintonia con un clic. Il piano bande modificabile
accanto. Selezione e cancellazione multipla nell'editor, perché un elenco in
cui è entrato un database di ponti arriva a centinaia di righe.

**Importare un elenco di ponti.** Legge `.xls`, `.xlsx` o `.csv` da un indirizzo
web o da un file, mappa le colonne con menu a tendina, filtra per regione,
traduce i nomi delle modulazioni usati dalla sorgente, mostra in anteprima ogni
riga che verrà importata, e salva tutta la configurazione come predefinita.

**Decidere cosa si sente davvero.** A richiesta, l'importatore misura il terreno
fra te e ogni stazione — dati altimetrici reali, profilo del percorso,
diffrazione sopra i crinali, altezza e diagramma della tua antenna — e tiene
solo ciò che dovrebbe essere ricevibile. Sull'elenco italiano significa passare
da 1031 memorie a 167, e quelle che scarta sono dietro le montagne.

**Chiamate selettive.** Un decoder **5 toni (SELCALL)** che copre CCIR/EEA,
ZVEI1, ZVEI2, DZVEI, EIA e CCITT contemporaneamente, con filtro per standard, e
un decoder **2 toni** che misura la frequenza reale dei toni invece di
indovinarla da una tabella.

**Una mappa senza Google.** Leaflet su OpenStreetMap: nessuna chiave API,
nessun account di fatturazione, niente consegnato ai visitatori. Compreso il
terminatore giorno/notte, e il selettore di posizione nei settings funziona allo
stesso modo.

**APRS, nei due versi.** Posizioni prese da aprs.fi per le stazioni fuori
portata — la chiave API resta sul server — e le impostazioni dell'igate APRS-IS
raccolte in un unico posto accanto a quelle.

---

## Requisiti

- **OpenWebRX v1.2.2.** ABMod è stato costruito e provato su quella versione.
  Lo script di aggiornamento avvisa e chiede conferma su qualunque altra.
- **Python 3.7+** con `numpy`, che OpenWebRX richiede già di suo.
- `python3-xlrd`, solo per importare il vecchio formato binario `.xls`.
  L'installatore lo propone; `.xlsx` e `.csv` non richiedono nulla.
- Circa **85 MB di disco** se usi il filtro di ricevibilità, per i dati
  altimetrici entro il raggio che scegli.

Provato su un Raspberry Pi 3 con Raspberry Pi OS (bullseye).

---

L'elenco delle modifiche rispetto all'originale è nel
[registro delle modifiche](CHANGELOG.it.md).

---

## Riconoscimenti

**OpenWebRX** è opera di **Jakob Ketterl, DD5JFK**, e dei suoi collaboratori.

- Autore: [Jakob Ketterl, DD5JFK](http://www.justjakob.de/)
- Sito: [www.openwebrx.de](https://www.openwebrx.de)
- Sorgenti: [github.com/jketterl/openwebrx](https://github.com/jketterl/openwebrx)
- Lista di discussione: [groups.io/g/openwebrx](https://groups.io/g/openwebrx)

Quei riconoscimenti restano come sono, qui e nell'interfaccia del ricevitore.
Niente in ABMod li sostituisce.

**ABMod** è di **IU2QDA** — [www.iu2qda.it](https://www.iu2qda.it).

Sono usati anche: [Leaflet](https://leafletjs.com/) per la mappa; le tessere
cartografiche dei collaboratori di
[OpenStreetMap](https://www.openstreetmap.org/copyright); i dati di posizione
di [aprs.fi](https://aprs.fi/); i simboli APRS del progetto
[aprs-symbols](https://github.com/hessu/aprs-symbols); i dati altimetrici SRTM
della NASA, distribuiti come tessere pubbliche.

L'importatore è stato scritto sull'elenco dei ponti italiani pubblicato da
**IK2ANE**, che è opera sua e ha condizioni proprie — gratuito per radioamatori,
uso privato, citando gli autori, senza uso commerciale. **Nessun dato dei ponti
è incluso in questo repository.**

---

## Licenza

OpenWebRX è sotto **GNU Affero General Public License v3**, quindi lo è anche
ABMod. Il testo completo è in [LICENSE.txt](LICENSE.txt), preso identico da
upstream.

L'AGPL qui conta più del solito. Far funzionare una versione modificata come
servizio di rete — che è esattamente ciò che è un WebSDR — obbliga a offrirne i
sorgenti a chi la usa. Pubblicare questo repository è ciò che soddisfa quel
vincolo, e l'interfaccia del ricevitore riporta un collegamento qui.
