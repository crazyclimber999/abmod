# Registro delle modifiche

*[Read in English](CHANGELOG.md)*

Tutto quello che segue è relativo a **OpenWebRX v1.2.2**, la versione su cui
ABMod è costruito e provato. Le ragioni delle scelte sono in
[tutte le funzionalità](docs/it/funzionalita.md); questo file è l'elenco.

Le date sono il giorno in cui la modifica è stata finita e messa su un
ricevitore vero.

## v1.0.13 — 2026-11-26

### Corretto

- **Un ricevitore che aveva già la frequenza APRS come default salvato non
  parcheggiava mai.** Se parcheggiare o no si decideva confrontando la
  frequenza di riposo col default salvato, quindi una stazione con 144.800 come
  default - cioè l'assetto ovvio per chi gatea la maggior parte del tempo -
  saltava il parcheggio anche dopo che un visitatore aveva spostato il centro e
  se n'era andato, e il gateway restava morto fino al riavvio dopo. Ora il
  confronto è con il punto in cui la radio è davvero puntata.
- **Tornando dal parcheggio il ricevitore andava sulla frequenza parcheggiata,
  non sul default.** `sdr.props` è una pila il cui livello più alto è l'oggetto
  del profilo, quello che sta dentro la configurazione viva: ogni
  risintonizzazione, parcheggio compreso, ci scrive dentro. Chiesto quale fosse
  il default, la configurazione rispondeva con il punto in cui la radio era
  puntata. Ora la frequenza salvata si legge da `settings.json`, che scrive
  solo Save Defaults, quindi chi salva un default nuovo mentre il ricevitore è
  parcheggiato si ritrova quello al ritorno.
- **L'orologio del parcheggio APRS parte anche all'avvio.** Fino a ora lo
  avviava solo un ascoltatore che se ne andava, quindi un ricevitore appena
  riavviato che nessuno aveva ancora visitato non parcheggiava mai - cioè
  proprio la situazione per cui la regola esiste. Ora parte una volta quando il
  ricevitore si accende, e continua a non fare niente se la regola è spenta.

## v1.0.12 — 26 novembre 2026

### Aggiunto

- **Il ricevitore può mettersi sulla frequenza APRS quando nessuno ascolta.**
  L'igate e un ascoltatore vogliono il ricevitore su due frequenze diverse, e
  non le vogliono mai nello stesso momento: il servizio packet gira solo dove
  una voce del piano bande cade dentro la finestra campionata, quindi un
  ascoltatore che si sintonizza altrove spegne il gateway. Con questa opzione
  attiva, l'ultimo ascoltatore che se ne va avvia un orologio - dieci minuti
  per difetto - e alla scadenza il ricevitore si sposta sulla frequenza APRS
  configurata; appena qualcuno si collega torna sulla frequenza centrale
  salvata per il profilo, prima che a quel client venga detto qualcosa, così
  quello che vede è già vero.

  Vengono scritte solo le proprietà in esecuzione, mai `settings.json`: un
  ricevitore parcheggiato che viene riavviato torna sul suo default, che è il
  verso giusto per uno stato temporaneo. L'attesa serve perché un ascoltatore
  che ricarica la pagina se ne va e torna in pochi secondi, e parcheggiare nel
  frattempo gli costerebbe un riavvio della chiavetta.

  Tre impostazioni sotto General settings → APRS: igate, spente per difetto.
  Serve *Keep device running at all times* sul dispositivo, e il modulo lo
  scrive nel log invece di parcheggiare una radio che è spenta. Il prezzo è
  detto chiaramente nella pagina: **qualunque** visitatore che si collega
  ferma il gateway, non solo chi gestisce la stazione.

### Corretto

- **Il DMR non produceva nulla se era acceso un modo digitale.** La catena dei
  soli metadati finiva con un flusso audio in SHORT, come quella originale di
  digiham - che lì ha un AGC, pezzo di cui questa non ha bisogno.
  `ClientDemodulatorChain._connect` ricostruisce il buffer audio ogni volta che
  cambia il formato d'uscita del demodulatore e passa il nuovo lettore al
  demodulatore secondario; i decoder 5 e 2 toni di ABMod leggono l'audio in
  FLOAT, quindi con un buffer in SHORT sollevavano `ValueError: invalid reader
  format`.

  `Chain.replace` rilancia quell'errore, e `setDemodulator` si interrompeva a
  metà: il demodulatore vecchio era già stato fermato e sostituito con un
  segnaposto, quello nuovo non veniva mai agganciato, e da lì in poi
  `self.demodulator` era `None` - quindi anche la chiamata successiva falliva,
  con `AttributeError: 'NoneType' object has no attribute 'setSampleRate'`. Il
  ricevitore restava senza demodulatore: nessun metadato, nessun audio e
  niente mostrato in pagina.

  Ora la catena esce in FLOAT, come tutti i modi analogici, così il buffer non
  viene mai ricostruito e non c'è nulla da ricollegare. Trovato su un
  ricevitore vero: nelle prove precedenti avevo sempre scelto il DMR senza
  modo secondario attivo, che è l'unico percorso che funzionava.

### Modificato

- **Il sorgente è tutto in inglese.** Commenti e nomi locali nell'importatore
  delle memorie, nell'editor multiplo, negli aiuti per il terreno e il
  passcode, nel rivelatore CTCSS e nei pannelli del ricevitore erano ancora in
  italiano in più punti. Solo rinomine e commenti. Restano in italiano i nomi
  di intestazione nell'indovino delle colonne dell'importatore: quelli sono
  intestazioni di fogli di calcolo da riconoscere, non lingua del progetto.

## v1.0.11 — 26 novembre 2026

### Aggiunto

- **DMR senza il codec AMBE: identificativi e talkgroup, senza voce.** Il DMR
  ha bisogno di due cose, e una sola delle due è gratis. digiham, che si
  sincronizza sulle trame TDMA e tira fuori sia i pacchetti voce sia la
  segnalazione, è nei repository Debian. Il decodificatore AMBE+2 no:
  codecserver ha un unico driver, `libambe3k.so`, che non è affatto un codec
  software - pilota un chip AMBE-3000 su porta seriale. Senza quell'hardware
  `MbeSynthesizer.hasAmbe()` è falso, e a quel punto il modo viene ritirato per
  intero, segnalazione compresa, anche se la segnalazione non passa dal codec.

  Non è obbligatorio che vada così. Nella catena originale i metadati escono
  per una strada loro - `self.decoder.setMetaWriter(buffer)`, il decoder, non
  il sintetizzatore - quindi una catena che si ferma al decoder dice ancora chi
  sta trasmettendo, su quale talkgroup e in quale timeslot, risolto su RadioID
  dal parser che c'è già e mostrato nel pannello che il modo DMR ha già. ABMod
  costruisce quella catena quando il codec manca e quella originale quando c'è,
  così una chiavetta AMBE-3000 accenderebbe l'audio senza altre modifiche. La
  mancanza di audio viene annunciata nel log del ricevitore, perché un modo che
  normalmente ha il suono e all'improvviso non ce l'ha sembra un guasto.

  Il filtro dei timeslot, il pannello dei metadati e le voci del piano bande
  funzionano come prima: il modo resta `dmr`, con lo stesso nome e la stessa
  larghezza di banda.

## v1.0.10 — 26 novembre 2026

### Corretto

- **L'indicatore DS spariva ricaricando la pagina**, anche col ricevitore
  ancora sotto il limite del tuner. Veniva mandato con la configurazione
  iniziale, che viene messa insieme prima che il dispositivo sia agganciato e
  quindi non puo ancora dire quale ingresso sia in uso. Ora parte da
  `handleSdrAvailable`, che gira alla prima connessione e di nuovo dopo ogni
  riavvio della sorgente.

## v1.0.9 — 26 novembre 2026

### Corretto

- **Il passaggio al campionamento diretto lasciava il ricevitore sulla
  frequenza sbagliata.** La modalita veniva decisa e il connector riavviato
  *prima* che la nuova frequenza centrale fosse scritta, quindi ripartiva sulla
  vecchia frequenza con la nuova modalita e andava poi risintonizzato sul
  socket di controllo: cosa che, per un tuner a cui si chiede di arrivare a
  6 MHz, non funzionava mai. Misurato su un ricevitore vero: finiva a 15,001
  MHz, ne la frequenza da cui veniva ne quella richiesta.

  Ora la frequenza entra per prima nelle proprieta. Il connector costruisce la
  sua riga di comando da quelle, quindi riparte gia sintonizzato e gia nella
  modalita giusta, e non serve nessuna risintonizzazione.

- **Il waterfall si bloccava dopo il passaggio.** La connessione originale
  ascolta solo il passaggio a RUNNING, che basta finche una sorgente non si
  ferma mai con un ascoltatore attaccato. Riavviare il dispositivo per il
  campionamento diretto fa esattamente quello, quindi la vecchia catena dsp
  restava collegata a un processo sparito e `handleSdrAvailable` riconfigurava
  quella catena morta invece di costruirne una nuova. Ora la connessione
  smonta il dsp anche su STOPPING, e la ricostruzione su RUNNING fa il resto.

- **L'indicatore DS viene aggiornato a ogni sintonia**, non solo quando la
  modalita cambia, cosi resta onesto anche se un altro ascoltatore ha mosso la
  radio.

## v1.0.8 — 26 novembre 2026

### Aggiunto

- **Il campionamento diretto si attiva da solo sotto il limite del tuner.** Un
  R820T non scende sotto i 24 MHz circa; sotto, l'unica via d'ingresso e
  l'ADC. Sintonizzando il ricevitore la, il dispositivo passa al campionamento
  diretto sul ramo Q, e risalendo torna indietro.

  La decisione si prende sulla **cima** della finestra campionata, non sul suo
  centro: una finestra centrata a 23 MHz arriva a 24,25 e il tuner la copre
  tutta, quindi decidere sul centro regalerebbe spettro buono a un ingresso che
  non ha nessun filtro davanti.

  Costa un riavvio, e non viene nascosto. Il campionamento diretto e
  un'opzione della riga di comando del connector, mentre la frequenza viaggia
  a caldo sul socket di controllo: il processo deve ripartire.
  `ConnectorSource` manda ogni cambio di proprieta su quel socket e non
  riavvia mai, e cambiare profilo fa lo stesso. Il ricevitore perde quindi
  qualche secondo di audio, e lo dice nel log prima di farlo.

  Misurato prima sull'hardware, con `rtl_connector` stesso: a 6 e 7 MHz col
  campionamento diretto attivo ci sono righe discrete a **29 dB sopra il
  fondo**, contro un controllo sui 2 metri che si comporta esattamente come
  deve. Un ramo Q scollegato non lo fa.

  Mentre e attivo, accanto al pulsante Set compare un riquadro **DS** delle sue
  stesse dimensioni, cosi il ricevitore dice da quale ingresso sta ascoltando
  invece di lasciartelo dedurre dalla frequenza. Viaggia con la configurazione,
  quindi e giusto anche per chi si collega a un ricevitore gia la sotto.

## v1.0.7 — 25 novembre 2026

### Rimosso

- **La casella del prefisso nel pannello 5 toni**, aggiunta nella 1.0.6 e
  tolta su richiesta: chi gestisce la rete preferisce vedere tutto quello che
  il decoder produce e giudicarlo da se. I pulsanti per standard e il
  conteggio di quello che nascondono restano come erano.

  Il controllo di purezza spettrale dentro il decoder non e toccato, e non e
  un filtro sui risultati: decide se in una finestra da 25 ms ci sia o no un
  tono, ed e quello che sulla stessa registrazione ha portato le chiamate vere
  trovate da 1 a 9.

## v1.0.6 — 25 novembre 2026

### Aggiunto

- **Un filtro per prefisso nel pannello 5 toni.** Su una rete dove ogni
  chiamata inizia con le stesse cifre, scriverle nella casellina accanto ai
  pulsanti degli standard nasconde tutto il resto. Sul canale per cui e stato
  costruito porta la precisione CCIR dal 75% al 100%.

  E un filtro, non una regola che il decoder applica da se, e la differenza
  conta. L'euristica ovvia — scartare le sequenze fatte di meno di tre toni
  distinti — sulla stessa registrazione arrivava al 90% e **non** e stata
  adottata: chi gestisce la rete ha confermato che `31111` e un indirizzo
  valido, e un sistema di chiamata selettiva che perde in silenzio una
  chiamata vera costa molto piu di una riga di troppo che si vede a occhio che
  non e tua. Il prefisso si vede, si toglie, resta salvato nel browser, e il
  conteggio sotto continua a dire tutto quello che sta nascondendo.

## v1.0.5 — 25 novembre 2026

### Modificato

- **Il subtono ora resta sullo schermo** una volta letto, invece di sparire
  quando cade la portante. Il CTCSS esiste solo mentre qualcuno trasmette, ma
  e una proprieta del canale, non del momento: cancellarlo a fine passaggio
  voleva dire mostrarlo per due secondi e poi togliere proprio l'informazione
  che serviva. Viene sostituito se se ne sente uno diverso, e dimenticato
  quando cambi sintonia: un tono appartiene alla frequenza su cui lo hai
  sentito. La riga di log nomina quella frequenza.

## v1.0.4 — 25 novembre 2026

### Corretto

- **Il blocco CTCSS era annidato dentro il gestore dei messaggi websocket**,
  quindi il suo stato viveva in quella funzione invece che a livello di file.
  Funzionava — chi lo alimenta sta nella stessa funzione — ma niente poteva
  ispezionarlo o riusarlo, e una variabile che sembra globale senza esserlo è
  una trappola per la modifica successiva. Spostato fuori.

## v1.0.3 — 25 novembre 2026

### Aggiunto

- **Il subtono CTCSS, letto dall'audio e mostrato nel ricevitore** sotto la
  frequenza, e scritto nel log del ricevitore quando cambia. Viene rivelato nel
  browser con un banco di Goertzel sui 39 toni standard, su audio decimato a
  1 kHz, in finestre da due secondi: un tono continuo non ha fretta, e la
  lunghezza compra la risoluzione che le coppie piu vicine della tabella
  richiedono.

  Che funzionasse e stato misurato, non supposto. La catena NFM di OpenWebRX e
  `FmDemod → Limit → NfmDeemphasis → Agc`: nessun passa-alto, e la de-enfasi e
  un passa-basso, quindi esalta le frequenze subaudio invece di toglierle. Le
  radio di solito filtrano il CTCSS perche non lo si senta; questa no. Su sei
  minuti di traffico vero il tono e uscito a **107,2 Hz, 34,7 volte il rumore
  circostante e a 0,20 Hz dal nominale** - misurato su audio preso dal
  websocket e decodificato dall'ADPCM, cioe esattamente quello che riceve un
  browser: la compressione non lo rovina.

### Corretto

- **Il decoder 5 toni riportava quasi solo spazzatura, e perdeva quasi tutte le
  chiamate vere.** Confrontava il tono vincente solo col secondo *fra gli
  undici dello stesso standard*, senza mai chiedersi se quel tono staccasse dal
  fondo a banda larga. La voce ha energia ovunque, quindi ognuno dei sei
  standard trovava il proprio tono "dominante" nello stesso respiro di parlato:
  ecco perche arrivavano sei sequenze diverse nello stesso istante.

  Il cancello aggiunto e la purezza spettrale: il bin piu forte contro la
  **mediana di tutta la banda 500-3000 Hz**. Misurato su sei minuti di traffico
  registrato, con la verita nota che su quel canale le chiamate sono CCIR e
  iniziano per 31: una chiamata vera arriva a 122, il parlato si ferma a 38, il
  canale muto a 6. La soglia e 20.

  Non toglie solo spazzatura. Senza il cancello le finestre di rumore si
  intercalavano ai toni veri e corrompevano le sequenze prima che venissero
  emesse, quindi le chiamate non uscivano affatto. Su quella registrazione il
  decoder e passato da **1 chiamata vera e 108 false a 9 vere e 3 false**, e la
  precisione CCIR dal 9% al 75%.

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
