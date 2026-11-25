# Configurazione

*[In English](../en/configuration.md)* · [torna al README](../../README.it.md)

Tutto quello che segue sta sotto **Settings**, e tutto ciò che sta sotto
Settings richiede un amministratore. Le impostazioni che ABMod aggiunge sono
raggruppate accanto a quelle a cui appartengono.

---

## Receiver details

Niente di nuovo qui, ma **le coordinate contano più di prima**. Decidono dove si
centra la mappa, cosa trasmette il beacon APRS, e il punto da cui il filtro di
ricevibilità misura ogni percorso. Un ricevitore che porta ancora le coordinate
della macchina da cui è stato clonato darà risposte sicure e sbagliate.

---

## Map settings

| Impostazione | Cosa fa |
| --- | --- |
| **Map tile URL** | Modello del server delle tessere, nel consueto schema `{z}/{x}/{y}`. Il valore predefinito è OpenStreetMap. |
| **Map tile attribution** | La citazione mostrata nell'angolo. Chi serve le tessere decide cosa debba comparire: leggi le sue condizioni prima di cambiare l'indirizzo. |
| **Map retention time** | Per quanto una stazione resta sulla mappa dopo l'ultimo ascolto. È anche l'età oltre la quale una posizione da aprs.fi viene ignorata. |

Nessuna chiave API, da nessuna parte.

---

## APRS: posizioni da aprs.fi (in entrata)

Mostra stazioni che non senti direttamente.

| Impostazione | Cosa fa |
| --- | --- |
| **aprs.fi API key** | Da "My account" su aprs.fi. La chiave resta sul server e non viene mai inviata al browser. Vuota disattiva tutto. |
| **Callsigns to watch** | Separati da virgola, per esempio `N0CALL-9, N0CALL-7`. aprs.fi risponde ad al massimo 20 nominativi per interrogazione, quindi elenchi più lunghi vengono divisi. |
| **Polling interval** | Predefinito 300 s. **Limitato a un minimo di 60 s**, perché le condizioni di aprs.fi chiedono non più di un'interrogazione al minuto. |

---

## APRS: igate (in uscita)

Inoltra ciò che il ricevitore sente verso APRS-IS. È il verso opposto rispetto
alle impostazioni qui sopra, e **trasmette sotto il tuo nominativo**.

| Impostazione | Cosa fa |
| --- | --- |
| **Station callsign** | Come il ricevitore si identifica su APRS-IS. Lasciarlo a `N0CALL` metterebbe la tua stazione in rete sotto un segnaposto. |
| **Send received APRS data** | L'interruttore principale. |
| **APRS-IS server** | `euro.aprs2.net` e simili. |
| **APRS-IS passcode** | **Un numero derivato dal tuo nominativo**, non la password di un sito. Accanto al campo c'è un pulsante che la calcola; l'SSID non conta, quindi `N0CALL`, `N0CALL-1` e `N0CALL-10` condividono la stessa passcode. Se è sbagliata il server accetta la connessione, la marca *unverified*, e scarta in silenzio tutto ciò che invii. |
| **Send the receiver position** | Trasmette dove sei. Controlla prima le coordinate: le rende pubbliche. |
| **Beacon interval** | Ogni quanto la posizione si ripete, in minuti. Una stazione fissa non ha bisogno di gridare: 30 è normale, sotto i 10 è poca educazione su una rete condivisa. Limitato fra 5 e 240. |
| **Beacon symbol, text, antenna height, gain, direction** | Cosa porta con sé il beacon. |

Due cose non evidenti:

- L'igate funziona solo per un **decoder in background**, quindi serve un
  servizio packet configurato e attivo. Da una sessione del browser non viene
  inoltrato nulla.
- **Due stazioni non possono essere verificate su APRS-IS con lo stesso
  nominativo nello stesso momento.** Se hai più di un ricevitore, dai a ciascuno
  un SSID diverso.
- **Una pagina dei settings lasciata aperta sovrascrive ciò che è cambiato nel
  frattempo.** Salvare un modulo caricato prima di una modifica riscrive i
  valori vecchi. Se la passcode smette di funzionare dopo aver salvato
  qualcos'altro, premi il pulsante accanto e risalva.

---

## Receiving antenna

Usata dal filtro di ricevibilità.

| Impostazione | Cosa fa |
| --- | --- |
| **Height above ground** | Dov'è l'antenna, non dov'è il ricevitore. Decide quanto lontano arriva il tuo orizzonte e cosa il segnale deve scavalcare. |
| **Gain** | 2 dBi è una verticale semplice. |
| **Horizontal pattern** | Guadagno relativo al valore qui sopra, in dB, come numeri letti uniformemente attorno alla bussola **partendo da nord**. Otto valori sono uno ogni 45°, trentasei uno ogni 10°. Per esempio `0,-3,-10,-18,-25,-18,-10,-3` è una direttiva puntata a nord. **Lascialo vuoto per un'antenna omnidirezionale**, che è ciò che si assume quando non c'è nulla. |

---

## Listenability estimate

| Impostazione | Cosa fa |
| --- | --- |
| **Terrain data radius** | Quanto territorio attorno al ricevitore viene conservato. Circa 1,3 MB scaricati e 0,4 MB su disco per chilometro di raggio: 200 km sono circa 250 MB scaricati e 85 MB conservati. |
| **Assumed transmitter power** | Nessun elenco di ponti riporta la potenza delle stazioni, quindi un solo valore vale per tutte. 40 dBm sono 10 W. |
| **Assumed remote antenna height** | Sopra il suolo all'altro capo. Il suolo stesso viene dai dati altimetrici. |
| **Usable signal level** | Il livello al quale un segnale si considera ascoltabile. −116 dBm è circa quello che serve perché la FM stretta sia leggibile. |

### Scaricare i dati altimetrici

Sotto il campo del raggio la pagina dice quanti dati ci sono davvero: quante
tessere su quante, quanto disco occupano e, se ne mancano, quanto resta da
scaricare. Quando qualcosa manca compare un pulsante **Download**, e mentre
lavora la riga si aggiorna ogni pochi secondi. Uscire dalla pagina non lo
interrompe. Lo stesso controllo c'è nella pagina di importazione.

Due cose su quei numeri. Si riferiscono sempre al raggio **salvato**, non a
quello scritto nella casella: cambiato il raggio, premere *Apply and save* e
ricontrollare. E una tessera tutta mare non esiste alla sorgente, quindi su un
ricevitore costiero il conteggio non arriva mai al totale — è normale, non un
download fallito.

"Apply and save" di proposito **non** avvia il download. Il raggio è una
impostazione; i dati che descrive sono qualche centinaio di megabyte presi da un
servizio pubblico di tessere, e un salvataggio delle impostazioni che tira giù
250 MB in silenzio su una linea domestica, senza avanzamento e senza modo di
fermarlo, è una sorpresa che poi viene imputata a qualcos'altro.

---

## Utenti

In `/settings/users`. Aggiungere, rimuovere, abilitare, disabilitare, cambiare
password, dare o togliere i diritti di amministratore.

Due livelli: un utente normale legge e modifica le memorie, un amministratore
arriva ai settings. La pagina non ti lascia rimuovere l'ultimo amministratore né
togliere i diritti all'account con cui sei collegato.

Il primo utente va creato da riga di comando:

```bash
sudo openwebrx admin adduser <nome>
```

---

## I file, e quali sono tuoi

| Percorso | Cos'è |
| --- | --- |
| `/var/lib/openwebrx/settings.json` | Tutto quanto sopra. **Contiene le tue chiavi API: tienilo a modo `600`.** È per ricevitore; non copiarlo fra macchine senza correggere la posizione. |
| `/var/lib/openwebrx/bookmarks.json` | Le tue memorie. |
| `/var/lib/openwebrx/users.json` | Account e impronte delle password. |
| `/var/lib/openwebrx/sessions.json` | I login attivi. Modo `600`; si può cancellare, tutti rifanno il login. |
| `/var/lib/openwebrx/terrain/` | Tessere altimetriche. Si può cancellare; i settings generali propongono di riscaricarle. |

L'installatore non tocca mai i primi tre.
