# Installare con apt-get

*[Read in English](../en/apt.md)* · [torna al README](../../README.it.md)

La terza strada, accanto a [installare da zero](installazione.md) e
[aggiornare un ricevitore esistente](aggiornamento.md): un pacchetto Debian,
così il ricevitore prende ABMod come prende tutto il resto.

```bash
sudo apt-get install abmod
```

Rimuoverlo rimette i file originali di OpenWebRX:

```bash
sudo apt-get remove abmod
```

---

## Cosa fa davvero il pacchetto

ABMod sostituisce **31 file che appartengono al pacchetto `openwebrx`** e
aggiunge **19 suoi**. dpkg si rifiuta, giustamente, di far scompattare un
pacchetto sopra i file di un altro, quindi i 31 passano per le **diversions di
dpkg**.

Una diversion dice a dpkg "da ora questo percorso è di qualcun altro". Il file
originale viene rinominato in `<nome>.openwebrx-original` e conservato, la
versione di ABMod prende il percorso vero, e rimuovere il pacchetto fa il
contrario. Ne derivano due cose che uno script di copia non potrebbe dare:

- **`apt-get remove abmod` ripristina davvero l'originale.** Non da un backup
  preso al momento dell'installazione, ma dai file che dpkg stesso ha messo da
  parte.
- **Un aggiornamento futuro di `openwebrx` non può sovrascrivere la modifica in
  silenzio.** Scrive sul nome deviato, dove resta innocuo.

### Si rifiuta di installarsi sopra un ABMod messo a mano

Se `install.sh` o `upgrade.sh` hanno già copiato ABMod su quei 31 file, il
pacchetto si ferma prima di cambiare qualunque cosa e lo dice. Non è prudenza
fine a sé stessa: deviare un file già modificato registrerebbe il file
*modificato* come originale, e un `apt-get remove` successivo lo
ripristinerebbe chiamandolo originale. È un pasticcio silenzioso che si vede
molto più tardi.

Prima rimetti gli originali — non tocca impostazioni, memorie o utenti — e poi
installa:

```bash
sudo apt-get install --reinstall openwebrx
```

```bash
sudo apt-get install abmod
```

Nel minuto in mezzo il ricevitore gira con OpenWebRX liscio.

### openwebrx resta fermo alla versione su cui ABMod è costruito

Il pacchetto dichiara `Depends: openwebrx (>= 1.2.2), openwebrx (<< 1.2.3)`.
Dato che sostituisce file interi invece di applicare patch, un OpenWebRX
diverso è un insieme di file diverso e le copie di ABMod sarebbero sbagliate in
modi difficili da vedere. Quindi, finché ABMod è installato, apt tiene
openwebrx dov'è.

È il modo onesto di dire come stanno le cose, non un limite nascosto. Se vuoi
aggiornare OpenWebRX: rimuovi ABMod, aggiorna, e installa un ABMod costruito
sulla versione nuova.

---

## Costruire il pacchetto

Su qualunque macchina Debian con `dpkg-dev` — va bene il ricevitore stesso,
scrive solo in una cartella temporanea:

```bash
./packaging/build-deb.sh
```

Produce `abmod_1.0.0_all.deb`. Il pacchetto è `Architecture: all`, perché
dentro c'è solo Python, JavaScript e HTML, quindi uno costruito su un portatile
si installa su un Raspberry Pi senza modifiche.

La build si rifiuta di produrre un pacchetto di cui non può garantire. Controlla
l'elenco dei file deviati contro l'`openwebrx` effettivamente installato sulla
macchina di build, conta i file finiti nell'archivio contro l'albero sorgente, e
fallisce su entrambe le differenze. Se modifichi `src/` è tutto automatico; se
l'elenco va rigenerato:

```bash
./packaging/list-diverted.sh pi@ricevitore
```

---

## Il repository: crazyclimber999.github.io/abmod

Servito da GitHub Pages dal branch `gh-pages`, ed è per questo che i pacchetti
e i loro indici stanno là e non in `main`. Il file `.nojekyll` su quel branch
non è un ornamento: senza, Pages passa l'albero per Jekyll, che scarta le
cartelle che iniziano per underscore ed è libero di riscrivere quello che
considera una pagina.

Su ogni ricevitore, una volta sola:

```bash
sudo curl -fsSL https://crazyclimber999.github.io/abmod/abmod-archive-keyring.asc -o /usr/share/keyrings/abmod.asc
```

```bash
echo "deb [signed-by=/usr/share/keyrings/abmod.asc] https://crazyclimber999.github.io/abmod/ bullseye main" | sudo tee /etc/apt/sources.list.d/abmod.list
```

```bash
sudo apt-get update && sudo apt-get install abmod
```

### Pubblicare una versione nuova

```bash
packaging/publish-pages.sh
```

Costruisce il pacchetto, ne costruisce un repository firmato, spinge il
risultato su `gh-pages`, e poi **scarica quello che Pages serve davvero** e
fallisce se manca qualcosa. Una pubblicazione che dichiara successo senza quel
controllo ti ha raccontato le sue intenzioni, non lo stato del mondo.

`--dry-run` costruisce e committa in locale senza pushare.

Deve girare su una macchina Debian, perché costruire un `.deb` richiede
`dpkg-deb` e indicizzare un repository richiede `dpkg-scanpackages`: in pratica
il ricevitore. Se lo lanci altrove te lo dice.

### Dove sta la chiave di firma, e perché non in CI

La GitHub Action costruisce il pacchetto e fa i suoi controlli a ogni push, e
non contiene nessun segreto. Non firma e non pubblica.

Firmare in CI vorrebbe dire mettere la chiave privata in un secret della
repository. Una chiave il cui unico compito è dimostrare che i pacchetti
vengono da te vale più della comodità di non digitare un comando, quindi quello
scambio qui non è fatto per inerzia. È uno scambio difendibile — lo fanno quasi
tutte le distribuzioni — ma va fatto sapendo cosa si scambia.

Resta la chiave dove la metti tu, con i costi veri:

- **Sul ricevitore**, dove gira lo script di pubblicazione: la più semplice, una
  macchina sola, e la chiave sta su una scatola raggiungibile da internet.
- **In un secret di GitHub**: una Action pubblica al tag e tu non digiti niente,
  e la chiave ti è uscita dalle mani.
- **Sulla tua macchina**, col repository costruito sul ricevitore e solo il file
  `Release` riportato indietro per firmarlo: la chiave non si muove, al prezzo
  di una pubblicazione in due passi.

Lo script non crea nessuna chiave, ed è voluto: una chiave di firma vuole una
passphrase, e scegliere la passphrase di un altro non è un favore. Creane una
con

```bash
gpg --full-generate-key
```

prendi i default, usa un nome e un indirizzo che ti va bene pubblicare, e metti
una passphrase. Lo script la trova da sé se è l'unica.

### Senza nessun repository

Il pacchetto si installa benissimo da file, senza hosting e senza firma:

```bash
sudo apt-get install ./abmod_1.0.0_all.deb
```

`apt-get` e non `dpkg -i`, così le dipendenze vengono risolte. È la risposta
giusta per uno o due ricevitori che amministri tu: il repository si ripaga
quando smetti di voler copiare un file a mano.

---

## Controllare cosa è stato installato

```bash
dpkg -l abmod
```

```bash
dpkg-divert --list | grep abmod | wc -l
```

Il secondo deve dire **31**. Se dice 0 mentre il pacchetto è installato,
qualcosa è andato storto e sono attivi i file originali: il ricevitore
funziona, ma non è ABMod.
