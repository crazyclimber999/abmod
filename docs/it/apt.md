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

## Pubblicare un repository

Un repository APT è solo file su un web server, non c'è niente di dinamico.
Questo lo costruisce:

```bash
./packaging/repo/build-repo.sh --out ./apt --key <id-della-tua-chiave-gpg> abmod_1.0.0_all.deb
```

Poi copi quella cartella dove è raggiungibile via HTTP, e su ogni ricevitore:

```bash
sudo curl -fsSL https://tuo.host/abmod-archive-keyring.asc -o /usr/share/keyrings/abmod.asc
```

```bash
echo "deb [signed-by=/usr/share/keyrings/abmod.asc] https://tuo.host/ bullseye main" | sudo tee /etc/apt/sources.list.d/abmod.list
```

```bash
sudo apt-get update && sudo apt-get install abmod
```

**Firmalo.** Senza `--key` il repository non è firmato, ogni ricevitore va
istruito con `[trusted=yes]` per poterlo usare, e quel flag non salta una
formalità: disattiva il controllo che il pacchetto che stai installando sia
quello che è stato pubblicato. Su una macchina che fa da servizio di rete,
raggiunta da fuori, è l'angolo sbagliato da tagliare.

### Dove metterlo

Tre possibilità oneste, con quello che costano davvero:

**Il tuo spazio web.** Qualunque hosting statico che già controlli. Niente da
configurare oltre all'upload, l'indirizzo è tuo, e continua a funzionare anche
se GitHub no. Se ce l'hai, è questa.

**GitHub Pages.** Gratis e affidabile, ma Pages non serve una repository
privata — quindi vorrebbe dire pubblicare il pacchetto, e il pacchetto contiene
i sorgenti. Se la repository è privata per scelta, questa strada non è
disponibile senza cambiare quella scelta.

**Un ricevitore che serve gli altri.** Un Pi con un web server e sotto la
cartella del repository. Va benissimo in rete locale ed è utile per un gruppo
di ricevitori; inutile per chi sta fuori, e vuol dire che un ricevitore è anche
un piccolo web server.

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
