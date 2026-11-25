# Tutto quello che ABMod aggiunge

*[In English](../en/features.md)* · [torna al README](../../README.it.md)

Ogni sezione dice cosa è cambiato e, dove la scelta non era ovvia, perché. Le
cifre citate sono misurate su un Raspberry Pi 3 sull'elenco dei ponti italiani,
non stimate.

---

## 1. Controllo degli accessi

OpenWebRX ha già un login per i settings. ABMod lo estende e corregge ciò che
mancava.

- **Le memorie richiedono il login.** Nascondere il pulsante non bastava: i
  comandi websocket dietro di esso rispondevano a chiunque li inviasse, quindi
  il controllo è sul server. Anche i cartellini sulla scala delle frequenze
  compaiono solo da collegati.
- **I settings richiedono un amministratore.** Due livelli, non uno: un utente
  normale legge e modifica le memorie, un amministratore arriva ai settings.
- **Una pagina di gestione utenti** in `/settings/users` — aggiungere,
  rimuovere, abilitare, disabilitare, cambiare password, dare o togliere i
  diritti di amministratore.
- **Non puoi chiuderti fuori.** La pagina rifiuta di rimuovere l'ultimo
  amministratore, o di togliere i diritti a quello con cui sei collegato.
- **Un logout che disconnette.** Quello originale era un segnaposto che
  rimandava a una pagina con scritto "logout happening here" e lasciava la
  sessione viva.
- **Le sessioni sopravvivono al riavvio.** Prima vivevano solo in memoria, e
  ogni riavvio — necessario per qualunque modifica sotto `owrx/` — disconnetteva
  tutti. Ora stanno su disco, modo `600`, e quelle scadute vengono scartate.
- **Chi sei, nel pannello di stato**, col logout accanto, invece che nella
  barra in alto.

## 2. Il pannello delle memorie

Un pannello nel ricevitore stesso, appoggiato all'archivio memorie di
OpenWebRX — non a un elenco parallelo.

- Ricerca, ordinamento per nome o frequenza, modifica, cancellazione.
- Un clic sintonizza **e** imposta la modulazione. Impostare la sola frequenza
  centrale non sposta il demodulatore, ed è il motivo per cui la prima versione
  sembrava sintonizzare nel posto sbagliato.
- Un menu a tendina commuta lo stesso pannello fra **memorie e piano bande**,
  così entrambi si modificano dal ricevitore.
- Con FM o NFM selezionata, una casella **"Decode 5 tone"** salva la memoria
  come `5tone`, che il ricevitore risolve in NFM più il decoder.

## 3. Piano bande modificabile

Il piano bande si modifica dal pannello e dalla sua pagina in
`/settings/bandplan`. Le modifiche lavorano sul JSON grezzo invece che su
oggetti interpretati, così le voci che usano modi non demodulabili da questo
ricevitore — DMR, D-Star — sopravvivono a un giro di andata e ritorno invece di
sparire in silenzio.

## 4. Save Defaults

Un amministratore può salvare frequenza centrale e frequenza di campionamento
attuali come valori d'avvio. Guadagno e squelch sono stati esclusi di proposito:
appartengono al file di configurazione, e lo squelch è un'impostazione del
singolo ascoltatore che non compare mai fra le proprietà del ricevitore.

Accanto, i **pulsanti di passo**: frecce singole spostano di 25 kHz, doppie di
1 MHz, in su e in giù.

## 5. Decoder 5 toni (SELCALL)

Decodifica **CCIR/EEA, ZVEI1, ZVEI2, DZVEI, EIA e CCITT insieme** e riporta
quale standard ha prodotto ciascuna sequenza. Una sola FFT per finestra è
condivisa fra tutti e sei; un Goertzel per standard costerebbe parecchie volte
tanto.

Il pannello ha un pulsante per standard, così mostri solo quelli sensati sulla
frequenza che ascolti — e **conta quello che il filtro sta nascondendo**, perché
un filtro che scarta in silenzio è indistinguibile da un decoder che ha fallito.

Misurato: **120 su 120** corrette sui sei standard alle loro durate, **10 su
10** a ogni durata da 40 a 250 ms, e **zero falsi positivi** su 30 secondi di
rumore. Circa il 13% di un core mentre lavora.

Tre cose che fa bene e che è facile sbagliare:

- **Una cifra ripetuta mandata come un tono lungo.** Molti sistemi mandano
  `3,1,1,0,1` come quattro toni, quello centrale di durata doppia. La durata di
  un tono singolo si misura dalla trasmissione stessa, mai da una tabella di
  durate nominali: un sistema che manda toni da 150 ms contro una tabella che
  dice 100 trasforma ogni tono singolo in due cifre.
- **L'apertura dello squelch.** Il colpo di rumore prima della chiamata aggiunge
  una cifra spuria all'inizio, quindi la sequenza si legge dalla fine della
  chiamata, non dall'inizio.
- **Il tono di ripetizione CCIR è a 2110 Hz**, non ai 2400 che diverse fonti
  riportano — 2400 è il tono di gruppo. Col valore sbagliato il terzo tono di
  ogni chiamata cade fuori tabella, la sequenza esce di quattro cifre, e non
  viene mai emessa.

## 6. Decoder 2 toni

Un decoder a sé, non una variante del precedente: una chiamata è un tono tenuto
circa un secondo seguito da un altro, diverso e più lungo.

**La frequenza misurata è il risultato; il piano toni è solo un'etichetta.** I
toni sono lunghi, quindi il picco FFT si affina interpolando una parabola fra i
suoi vicini — errore misurato da 0,0 a 0,3 Hz. I piani pubblicati non concordano
fra loro, quindi una coppia che non corrisponde a nulla viene comunque riportata
come "947,2 / 332,6 Hz" e resta utile.

Misurato: 5 su 5 chiamate vere col piano giusto, 6 su 6 casi negativi rifiutati
— un solo tono lungo, un secondo tono più corto del primo, due toni quasi
identici, rumore, silenzio, toni troppo brevi — e 23 volte più veloce del tempo
reale.

Sono incluse le tabelle dei gruppi Motorola Quick Call II da 1 a 6 e i toni
ZVEI. Aggiungono solo un nome, non filtrano mai, quindi un errore lì costa
un'etichetta e nient'altro.

## 7. La mappa, senza Google

OpenWebRX disegna la mappa con l'API di Google Maps, che richiede una chiave
legata a un account di fatturazione — e consegna quella chiave a ogni
visitatore, perché è il browser a caricare l'API con essa. ABMod disegna la
stessa mappa con **Leaflet su tessere OpenStreetMap**.

- Nessuna chiave, nessun account di fatturazione, niente da far trapelare.
- La sorgente delle tessere è configurabile, quindi si può usare qualunque
  fornitore che serva il consueto schema `{z}/{x}/{y}`. Chi serve le tessere
  decide quale attribuzione debba comparire: controlla le sue condizioni prima
  di cambiarla.
- **Terminatore giorno/notte** calcolato al posto dell'overlay specifico per
  Google, e verificato contro la posizione reale del sole prima di fidarsene.
- I **marcatori con i simboli APRS** continuano a funzionare, disegnati dagli
  sprite che OpenWebRX installa già.
- Anche il **selettore della posizione del ricevitore** nei settings è Leaflet:
  trascini il marcatore, clicchi sulla mappa, o scrivi le coordinate — i tre
  modi restano allineati.

## 8. APRS

**In entrata — posizioni da aprs.fi.** Un ricevitore sente solo ciò che è a
portata. Dai ad ABMod una chiave API aprs.fi e un elenco di nominativi da
seguire, e le loro ultime posizioni note compaiono sulla mappa accanto alle
stazioni che hai sentito tu.

**La chiave non raggiunge mai il browser.** aprs.fi la lega a un account e
limita le interrogazioni su quella; una chiave consegnata alla pagina sarebbe
usabile da ogni visitatore. È il ricevitore a interrogare e a spingere i
risultati sulla websocket già aperta. Le interrogazioni sono limitate a una al
minuto, come chiedono le condizioni di aprs.fi, e le posizioni più vecchie del
tempo di ritenzione della mappa vengono saltate.

**In uscita — l'igate.** OpenWebRX sa inoltrare ciò che sente ad APRS-IS e
trasmettere la propria posizione. Quelle impostazioni esistevano ma stavano in
una pagina diversa da tutto il resto dell'APRS; ora sono raccolte insieme,
complete dei campi per altezza, guadagno e direzione d'antenna.

Due cose da sapere, perché nessuna delle due è evidente:

- L'igate funziona solo per un **decoder in background**. Da una sessione del
  browser non viene inoltrato nulla, quindi serve un servizio packet configurato
  e attivo.
- La **passcode è un numero derivato dal tuo nominativo**, non la password di un
  sito. Senza, il server accetta la connessione e la marca *unverified*, poi
  scarta in silenzio tutto ciò che invii.

## 9. Importare un elenco di ponti

In `/settings/bookmarkimport`, raggiungibile dall'editor delle memorie.

**Formati.** `.xls` tramite `xlrd`, `.xlsx` con la sola libreria standard,
`.csv` con il separatore riconosciuto automaticamente e ripiego utf-8 /
latin-1. Da un indirizzo web o da un file che carichi. Un file di esempio è
scaricabile.

**Nulla è dato per scontato sul formato.** Le colonne si mappano da menu a
tendina, indovinate dalle intestazioni del file come punto di partenza. Il nome
si compone di due parti, con un separatore che scegli, e qualunque altra colonna
può essere aggiunta fra parentesi quadre.

**Filtro per regione**, con una casella per regione e il conteggio delle righe
di ciascuna.

**Traduzione delle modulazioni.** Nessun elenco pubblicato usa i nomi del
ricevitore. Ogni valore della sorgente si mappa su un modo — oppure su *(ignore
import)* per escludere del tutto quelle righe. I modi che il ricevitore non sa
demodulare sono elencati ma non selezionabili, così è chiaro *perché* non si può
scegliere DMR invece di sembrare una dimenticanza.

**Anteprima di ogni riga**, 25 per pagina, numerate, con i comandi di
navigazione — non solo le prime 25, perché quello che stai controllando è
l'effetto della mappatura sulle altre mille.

**Salva tutta la configurazione come predefinita**: indirizzo della sorgente,
riga di intestazione, mappatura colonne, unità, regioni, tabella delle
modulazioni e le soglie del filtro.

**Una memoria per canale.** Un elenco nazionale riusa la stessa frequenza decine
di volte — su 145.750 MHz si contendono il posto 24 ponti diversi in quello
italiano. Tiene quello che si sente meglio e scarta gli altri. A richiesta, una
stazione importata può prendere il posto di una memoria che avevi già su quella
frequenza.

**Dice sempre cosa sta lasciando fuori**: quante righe ha tolto il filtro di
ricevibilità, e quante stanno per annullarsi a vicenda perché i nomi non sono
abbastanza distinti.

## 10. Si sente davvero?

Il pezzo più impegnativo. A richiesta, l'importatore calcola cosa fa al segnale
il terreno fra te e ogni stazione.

**I dati altimetrici** sono SRTM a un arcosecondo, da un servizio pubblico che
non richiede registrazione, conservati ridotti a tre arcosecondi — 2,9 MB a
tessera invece di 25,9, circa 85 MB per un raggio di 200 km. Sono validati
contro quote note prima di essere usati.

Si scaricano dai **settings generali**, sotto il raggio che decide quanti
tenerne, e anche dalla pagina di importazione. La pagina dice quante tessere ci
sono e quante mancano, e lo scarico è un pulsante invece di qualcosa che
"Apply and save" fa in silenzio — un salvataggio delle impostazioni che tira
giù qualche centinaio di megabyte senza avanzamento e senza modo di fermarlo è
una sorpresa che poi viene imputata a qualcos'altro.

**Il modello** è quello classico: profilo del terreno lungo l'ortodromia, Terra
con raggio efficace 4/3 per la rifrazione atmosferica, ostacoli trattati come
coltelli col metodo di Deygout, poi perdita di spazio libero e guadagno della
tua antenna in quella direzione. La risposta è un **margine in decibel**, non un
sì o un no.

E conta. Una prima versione che pretendeva piena visibilità ottica dichiarava
irraggiungibile un ponte a quattro chilometri in pianura. In VHF un ostacolo
attenua, non interrompe.

**La tua antenna** si descrive nei settings: altezza dal suolo, guadagno, e un
diagramma orizzontale facoltativo dato come numeri letti uniformemente attorno
alla bussola partendo da nord. Lascia vuoto il diagramma e l'antenna è
omnidirezionale.

**Dove sta la stazione remota.** Un locatore a sei caratteri è un rettangolo di
circa cinque chilometri — troppo grossolano per scegliere un punto. Un ponte sta
in alto, quindi si usa il punto più alto del quadrato invece del centro: per il
quadrato che contiene il Resegone sono 1643 m invece di 1130, e la cima è dove
sta davvero l'antenna. Per un locatore a quattro caratteri, che copre un grado
intero, il punto più alto sarebbe una montagna qualsiasi, quindi si usa il
centro.

**Oltre l'orizzonte lo dichiara** invece di indovinare. La perdita di un coltello
cresce lentamente con la distanza, mentre l'ostacolo vero laggiù è la curvatura
terrestre, che diffrange molto peggio; lasciato a sé il modello dichiarava
ricevibile un ponte a 270 km. Quello che succede oltre l'orizzonte è
meteorologia, non geometria.

Misurato su 1584 ponti: 5,4 ms ciascuno, quattro secondi in tutto. Entro 150 km
ce ne sono 397 e **l'orografia ne esclude 103** — un quarto di quelli che un
filtro a sola distanza importerebbe.

**Cosa non può sapere**: edifici e alberi, e la potenza della stazione remota,
che nessun elenco di ponti riporta. La potenza di trasmissione è un'ipotesi che
imposti tu. È una stima, buona, ma una stima.

## 11. Cancellazione multipla

Una volta importato un elenco di ponti l'editor delle memorie arriva a centinaia
di righe. Ogni riga ha ora una casella, l'intestazione ha il seleziona-tutto, lo
**shift-clic seleziona un intervallo**, e il pulsante elenca i primi cinque nomi
prima di cancellare qualunque cosa. La cancellazione parte come una sola
richiesta invece di una per riga.

Se la lista è cambiata da quando la pagina è stata caricata, lo dice invece di
dichiarare riuscita una cancellazione di nulla.

## 12. Cose più piccole

- **Il JavaScript compilato non viene più tenuto in cache per un'ora.** Upstream
  invia i bundle con `Cache-Control: max-age=3600`, che autorizza il browser a
  tenerseli senza chiedere — quindi un aggiornamento poteva essere legittimamente
  invisibile per sessanta minuti, e una correzione già installata sembrava una
  correzione fallita. Ora `max-age=0`: il browser rivalida e riceve un 304 senza
  corpo quando nulla è cambiato, misurato a 0 byte contro 229 KB.
- **Una corsa all'avvio, risolta.** Una websocket in arrivo durante l'avvio
  poteva incrociare `multiprocessing.connection` mentre un altro thread lo stava
  importando, sollevando `ImportError` e perdendo quella connessione. Il modulo
  viene ora caricato prima che parta qualsiasi thread.
- **I pannelli dei messaggi si impaginano correttamente.** Upstream li divide in
  due tabelle, che divergono della larghezza della barra di scorrimento e
  lasciano ogni intestazione fuori asse rispetto alla sua colonna.

---

## Cosa ABMod deliberatamente non cambia

- **La tua configurazione.** `settings.json`, memorie e utenti non vengono mai
  toccati dall'installatore.
- **I comandi di sintonia restano aperti.** Qualunque visitatore può
  risintonizzare il ricevitore, cambiare il guadagno o aprire lo squelch, per
  tutti. È il comportamento di OpenWebRX ed è normale per un WebSDR pubblico.
  Sappi però che la modifica raggiunge la configurazione salvata, quindi un
  amministratore che salvi una qualsiasi pagina dei settings la rende permanente.
  Se preferisci evitarlo, è l'unica cosa che vale la pena aggiungere da sé.
- **DMR, D-Star, YSF e NXDN richiedono ancora un codec.** OpenWebRX ha i modi;
  manca un codec AMBE per codecserver, che è una decisione di licenza più che di
  programmazione.
