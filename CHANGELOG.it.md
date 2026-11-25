# Registro delle modifiche

*[Read in English](CHANGELOG.md)*

Tutto quello che segue è relativo a **OpenWebRX v1.2.2**, la versione su cui
ABMod è costruito e provato. Le ragioni delle scelte sono in
[tutte le funzionalità](docs/it/funzionalita.md); questo file è l'elenco.

Le date sono il giorno in cui la modifica è stata finita e messa su un
ricevitore vero.

## v1.0.2 — 25 novembre 2026

### Corretto

- **L'intestazione del pannello 5 toni copriva i primi risultati** quando
  compariva la nota "nascoste dal filtro". OpenWebRX dà al tbody di ogni
  pannello messaggi un suo riquadro di scorrimento - `display: block`,
  `overflow: auto` e `height: 150px` fissa - e ABMod ne sovrascriveva solo il
  display. Un'altezza su un `table-row-group` vale come *minimo*, quindi con
  poche righe il browser le stirava da 18px a 25px, e il riquadro scorreva di
  6px dentro un contenitore che già scorreva, spingendo la prima riga sotto
  l'intestazione fissa. Misurati **24px di sovrapposizione**, ora 0. Corretti
  tutti e tre, anche per il pannello 2 toni. La nota è anche su una riga invece
  che due, perché il pannello cresce verso l'alto dal fondo dello schermo e ogni
  riga in più sposta tutto.

### Documentato

- **Perché l'igate si ferma quando nessuno ascolta**, che è comportamento
  originale di OpenWebRX e non un guasto: il gestore dei servizi in background
  si registra sull'SDR come client `INACTIVE`, e la sorgente parte solo per un
  client `USER` o `BACKGROUND`, quindi i servizi non accendono mai la radio: si
  agganciano a una già accesa per un ascoltatore. Il rimedio è l'impostazione
  `always-on` del dispositivo, che esiste ma sta dietro "Additional optional
  settings", dove non la trova nessuno. Scritto con quello che costa: chiavetta
  accesa 24 ore su 24 e carico intorno a 2,4 su un Pi 3, che su un Pi a corto di
  alimentazione è ciò che fa cadere i dispositivi USB.

### Aggiunto

- **Un pacchetto Debian, così un ricevitore installa ABMod con
  `apt-get install`.** I 31 file che ABMod sostituisce passano per le
  **diversions di dpkg** invece di essere copiati sopra: l'originale resta
  accanto al sostituto come `<nome>.openwebrx-original`,
  `apt-get remove abmod` lo ripristina davvero, e un aggiornamento successivo
  di `openwebrx` scrive sul nome deviato invece di sovrascrivere la modifica in
  silenzio. I 19 file nuovi si installano e basta.

  **Si rifiuta di installarsi sopra un ABMod messo a mano**, elencando i file,
  perché deviare un file già modificato registrerebbe la copia modificata come
  originale — e il danno si vede solo al momento della rimozione, molto dopo.
  Prima `apt-get install --reinstall openwebrx`, poi il pacchetto.

  `Depends: openwebrx (>= 1.2.2), openwebrx (<< 1.2.3)`, che tiene OpenWebRX
  alla versione su cui ABMod è costruito. Sostituisce file interi, quindi un
  OpenWebRX diverso è un insieme di file diverso: il vincolo lo dichiara invece
  di nasconderlo.

  `packaging/build-deb.sh` lo costruisce su qualunque macchina con `dpkg-dev`,
  compreso il ricevitore, e si rifiuta di produrre un pacchetto di cui non può
  garantire: controlla l'elenco dei file deviati contro l'`openwebrx` installato
  sulla macchina di build, conta cosa è finito nell'archivio contro l'albero
  sorgente, e scarta i file AppleDouble di macOS. `packaging/repo/build-repo.sh`
  trasforma il risultato in un repository APT firmato, e
  `packaging/publish-pages.sh` lo pubblica su GitHub Pages all'indirizzo
  [crazyclimber999.github.io/abmod](https://crazyclimber999.github.io/abmod/) —
  poi scarica quello che Pages serve davvero e fallisce se manca qualcosa. Una
  GitHub Action costruisce e controlla il pacchetto a ogni push; non contiene
  segreti e non firma, perché una chiave di firma in un secret compra comodità
  con l'unica cosa che la chiave serve a dimostrare. Vedi
  [installare con apt-get](docs/it/apt.md).

## v1.0.1 — 25 novembre 2026

### Corretto

- **La casella della frequenza centrale perdeva il raster da 12,5 kHz.** Veniva
  scritta con tre decimali di megahertz, cioè risoluzione al kilohertz, quindi
  145,0125 MHz diventava 145,012 — che non è un canale. E non era solo
  estetica: i pulsanti di passo rileggono quella casella, quindi una riscrittura
  portava la frequenza sintonizzata 500 Hz fuori e ogni passo successivo si
  teneva l'errore. Ora un'unica funzione formatta tutte le frequenze che
  l'interfaccia scrive, stampando il testo più corto che si rilegge come la
  stessa frequenza, così sopravvive anche un raster da 6,25 kHz. Provato su
  tutto il raster da 12,5 kHz fra 144 e 146 MHz: 161 frequenze, tutte tornano
  identiche. La casella ora segue anche il selettore dell'unità, invece di dare
  per scontati i megahertz.
- **Rimosso il percorso morto `recallmemory`**, da tutti e due i lati. Il
  server autorizzava il messaggio, lo smistava, sintonizzava l'SDR e rispondeva
  `memory_recalled`, e il browser aveva un handler in attesa di quella
  risposta — ma quel messaggio non lo ha mai mandato nessuno: cliccare una
  memoria muove il demodulatore lato client, che è il comportamento giusto ed
  è il motivo per cui la copia lato server era stata scritta e poi
  abbandonata. Via da `connection.py` (`_recall_memory`, `_find_memory`,
  `write_memory_recalled`) e da `openwebrx.js` (`on_memory_recalled` e il suo
  case).

## v1.0.0 — 25 novembre 2026

Prima versione pubblicata. In funzione su due ricevitori Raspberry Pi 3.

### Aggiunto

**Controllo degli accessi**

- Una pagina di gestione utenti in `/settings/users`: aggiungere, rimuovere,
  abilitare, disabilitare, cambiare password, concedere o togliere i diritti di
  amministratore.
- Due livelli di permessi. L'utente semplice legge e modifica le memorie,
  l'amministratore arriva ai settings.
- Sessioni salvate su disco, permessi `600`, con quelle scadute scartate in
  lettura.
- L'utente collegato e il logout nel pannello di stato del ricevitore.

**Memorie**

- Un pannello delle memorie dentro il ricevitore, appoggiato all'archivio di
  OpenWebRX, con ricerca, ordinamento, modifica e cancellazione.
- Un clic sintonizza e imposta la modulazione.
- Lo stesso pannello passa fra memorie e piano bande.
- Una pagina di settings per il piano bande in `/settings/bandplan`, che
  modifica il JSON grezzo perché le voci con modi che questo ricevitore non
  demodula sopravvivano al giro.
- Selezione con caselle e cancellazione multipla nell'editor delle memorie, con
  seleziona-tutto, intervalli con shift-clic e i nomi dei primi cinque mostrati
  prima di cancellare qualunque cosa.
- Una pseudo-modulazione `5tone`: salvata sulla memoria, risolta in NFM più il
  decoder 5 toni quando ci si sintonizza.

**Importare un elenco di ponti** (`/settings/bookmarkimport`)

- Legge `.xls`, `.xlsx` e `.csv`, da un indirizzo web o da un file caricato.
- Mappatura delle colonne con menu a tendina, indovinata dalle intestazioni del
  file; nome in due parti con separatore a scelta, e qualunque altra colonna
  aggiunta fra parentesi.
- Filtro per regione con il conteggio delle righe di ciascuna.
- Traduzione delle modulazioni valore per valore, compreso *(ignore import)*. I
  modi che il ricevitore non demodula sono elencati ma non selezionabili.
- Anteprima di tutte le righe che verranno importate, 25 per pagina.
- Tutta la configurazione salvabile come predefinita.
- Una memoria per frequenza: si tiene la stazione che si sente meglio e si
  scartano le altre, eventualmente sostituendo una memoria già presente su
  quella frequenza.
- Il conteggio di ciò che viene lasciato fuori, sempre.

**Stima di ricevibilità**

- Dati altimetrici: SRTM a un arcosecondo da un servizio pubblico di tessere
  che non richiede registrazione, conservati ridotti a tre arcosecondi,
  validati contro quote note.
- Un modello di propagazione: profilo del terreno lungo l'ortodromia, raggio
  terrestre efficace 4/3, diffrazione su crinali col metodo di Deygout,
  attenuazione di spazio libero e guadagno dell'antenna in quella direzione. Il
  risultato è un margine in dB.
- Un indicatore di oltre-orizzonte invece di una stima: là fuori l'ostacolo è
  la curvatura della Terra e quel che accade è meteorologia.
- Descrizione dell'antenna nei settings: altezza dal suolo, guadagno e un
  diagramma orizzontale facoltativo.
- Il punto più alto del quadrato di un locatore a sei caratteri come posizione
  della stazione remota, il centro per uno a quattro.
- Stato e scarico dei dati altimetrici nei settings generali, sotto il raggio
  che decide quanti tenerne, e nella pagina di importazione.

**Decoder**

- Un decoder **5 toni (SELCALL)** che copre CCIR/EEA, ZVEI1, ZVEI2, DZVEI, EIA
  e CCITT contemporaneamente da una sola FFT condivisa, riportando quale
  standard ha prodotto ogni sequenza, con un filtro per standard che conta
  quello che sta nascondendo.
- Un decoder **2 toni** con interpolazione parabolica del picco FFT, così la
  frequenza misurata è il risultato e la tabella dei toni solo un'etichetta.

**La mappa**

- Disegnata con Leaflet su tessere OpenStreetMap invece che con l'API di Google
  Maps: nessuna chiave, nessun account di fatturazione, niente consegnato ai
  visitatori. La sorgente delle tessere è configurabile.
- Un terminatore giorno/notte calcolato al posto dell'overlay specifico di
  Google.
- Il selettore della posizione del ricevitore nei settings ricostruito su
  Leaflet: trascinare, cliccare o scrivere, tutti e tre allineati.

**APRS**

- Posizioni prese da aprs.fi per un elenco di nominativi da seguire,
  interrogato dal ricevitore e spinto giù per il websocket, così la chiave API
  non arriva mai al browser. Limitato a una richiesta al minuto.
- Le impostazioni dell'igate raccolte nella pagina APRS con le altre, comprese
  altezza, guadagno e direzione dell'antenna.
- Intervallo del beacon configurabile.
- Un pulsante che calcola la passcode APRS-IS dal nominativo, nel browser, e un
  avviso quando nel campo c'è qualcosa che non è una passcode.

**Save Defaults**

- Un amministratore può salvare frequenza centrale e sample rate attuali come
  valori di avvio.
- Pulsanti di passo in frequenza: 25 kHz sulle frecce singole, 1 MHz sulle
  doppie.

### Modificato

- I bundle JavaScript compilati vengono inviati con `Cache-Control: max-age=0`
  invece di `max-age=3600`. Il browser rivalida e riceve un 304 senza corpo
  quando nulla è cambiato — misurati 0 byte contro 229 KB — così un
  aggiornamento non resta mai invisibile per un'ora.
- I pannelli dei messaggi sono una tabella sola invece di due, così le
  intestazioni restano sopra le loro colonne.

### Corretto

- **Le memorie si leggevano senza fare login.** Nascondere il pulsante lasciava
  i comandi websocket dietro di esso a rispondere a chiunque li inviasse; ora il
  controllo è sul server, e le etichette sulla scala delle frequenze compaiono
  solo da collegati.
- **Il logout non disconnetteva.** Quello originale rimandava a una pagina che
  diceva che il logout stava avvenendo e lasciava la sessione viva.
- **Le sessioni non muoiono più al riavvio.** Stavano in memoria, e qualunque
  modifica sotto `owrx/` richiede un riavvio, che disconnetteva tutti.
- **Non si può più restare fuori dai settings**: l'ultimo amministratore non si
  può rimuovere, e non si possono togliere i diritti all'utente con cui si è
  collegati.
- **Una corsa in avvio.** Un websocket che arrivava durante l'avvio poteva
  toccare `multiprocessing.connection` mentre un altro thread lo stava
  importando, con un `ImportError` che faceva cadere quella connessione. Il
  modulo viene caricato prima che parta qualunque thread.
