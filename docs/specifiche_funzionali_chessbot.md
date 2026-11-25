# Specifiche Funzionali e User Experience — ChessBot

> **Stato documento:** v1.0 — Specifiche Confermate  
> **Documento di riferimento tecnico:** [riassunto_progetto_chessbot.md](./riassunto_progetto_chessbot.md)  
> **Scopo:** Definire cosa deve fare il robot, come ci interagisce l'utente (schermo, comandi, orologio) e quali requisiti funzionali hanno impatto su meccanica, elettronica e software.

---

## 1. Funzionalità Principali (Core — v1)

Queste sono le funzioni indispensabili per considerare il ChessBot completo e giocabile.

### 1.1 Giocare a Scacchi (Umano vs ChessBot)
* **Scelta del Colore *(confermato)*:**
  * `Bianco` (inizia l'umano).
  * `Nero` (inizia il robot).
  * `Casuale / Estrazione a sorte`: il sistema estrae il colore a schermo (es. animazione moneta/pedone che gira) e opzionalmente un breve movimento scenografico del braccio.
* **Scelta della Difficoltà *(confermato)*:**
  * Lista selezionabile via touch composta da **preset intuitivi** seguiti, dopo `Massimo`, dall'opzione `Personalizzato`:
    1. `Principiante` (~800 ELO)
    2. `Amatore` (~1200 ELO)
    3. `Intermedio` (~1500 ELO)
    4. `Avanzato` (~1900 ELO)
    5. `Esperto` (~2300 ELO)
    6. `Massimo` (Stockfish Full Strength)
    7. `Personalizzato` $\rightarrow$ aprendo questa voce si regola l'ELO via **slider / pulsanti `-`/`+` touch a step di 50** (es. da `600` a `3000` ELO, con incremento/decremento di `50`).
  * *Nota tecnica Stockfish:* Stockfish nativo accetta `UCI_LimitStrength` + `UCI_Elo` indicativamente da `1320` a `3190`; per i valori inferiori a `1320` (es. `600–1300`) il software mapperà automaticamente lo step su `Skill Level` + limite su profondità/nodi (o leggera imprecisione controllata) in modo trasparente per l'utente.
* **Esecuzione Fisica delle Mosse *(confermato)*:**
  * Mossa normale (presa pezzo $\rightarrow$ sollevamento $\rightarrow$ deposito $\rightarrow$ ritiro in posizione di parcheggio fuori dalla camera).
  * **Cattura:** rimozione del pezzo catturato in uno **slot preciso del Cimitero** tracciato in memoria, poi spostamento del pezzo attaccante.
  * **Arrocco:** spostamento sequenziale di Re e Torre.
  * **En Passant:** spostamento pedone + rimozione nel Cimitero del pedone catturato sulla casella adiacente.
  * **Promozione del Pedone *(confermato)*:**
    * *Se promuove l'umano:* l'umano effettua direttamente la sostituzione fisica del pezzo e preme l'orologio; il robot identifica automaticamente il pezzo scelto tramite la **rete neurale di riconoscimento pezzi** *(fallback a schermo via touch solo in caso di confidenza bassa o in fase di test prima che la rete sia attiva)*.
    * *Se promuove il robot:* sposta il pedone nel Cimitero e **pesca automaticamente dal Cimitero** il pezzo voluto grazie alla mappa a posizioni fisse (senza bisogno della videocamera). Se quel pezzo non è presente nel Cimitero (es. Donna ancora sulla scacchiera), si ferma e chiede a schermo all'umano di effettuare la sostituzione e confermare.
* **Regole di Fine Partita e Azioni in Gioco *(confermato)*:**
  * Riconoscimento automatico di **Scacco**, **Scacco Matto**, **Stallo**, **Patta** (ripetizione, 50 mosse, materiale insufficiente) e **Tempo Scaduto**.
  * Azioni attivabili dal menu di pausa: `Abbandona`, `Proponi Patta`. *(Scartato `Annulla Mossa / Takeback` per fedeltà alle regole reali degli scacchi).*
* **Gestione Errori e Recupero *(confermato)*:**
  * Se la camera rileva una **mossa illegale** o un'anomalia (mano nell'inquadratura, pezzo urtato/caduto), lo schermo mostra un avviso chiaro, emette un segnale acustico e invita a sistemare la scacchiera e ripremere il pulsante per rifare la scansione (senza interrompere la partita).

### 1.2 Orologio da Scacchi Integrato *(confermato)*
L'orologio ha un **doppio ruolo chiave**: rende l'esperienza autentica e funge da **trigger affidabile per la telecamera** (evita scatti con la mano dell'umano in mezzo).

* **Cadenze selezionabili:**
  * Preset classici: `Blitz 3+2`, `Blitz 5+0`, `Blitz 5+3`, `Rapid 10+0`, `Rapid 15+10`, `Classic 30+0`.
  * Modalità `Personalizzata` (minuti + incremento Fischer in secondi via touch).
  * Modalità `Senza Tempo` (il pulsante dell'orologio resta comunque attivo come tasto *"Fine Turno / Conferma Mossa"*).
* **Logica del Tempo per il Robot — Fair Clock:**
  * Il tempo del robot scorre **solo durante il calcolo di Stockfish** e va in pausa durante il movimento meccanico dello SCARA (evita sconfitte al tempo dovute alla velocità fisica del braccio).
* **Commutazione turno:**
  * **Umano $\rightarrow$ Robot:** l'umano preme fisicamente il pulsante dell'orologio dopo aver eseguito la mossa (ferma il proprio timer, avvia la scansione `/capture` e, una volta validata la mossa, avvia il pensiero del robot).
  * **Robot $\rightarrow$ Umano:** appena il braccio termina la mossa e rientra in posizione di **home / parcheggio (*Park Pose*)**, il timer dell'umano riparte automaticamente accompagnato da un **breve segnale acustico (mini bip)** per segnalare l'inizio del turno.

### 1.3 Sistemazione Automatica della Scacchiera (Auto-Setup) e Gestione Cimitero *(confermato)*

#### A. Gestione Cimitero e Pezzi Catturati (in partita)
Poiché l'Auto-Setup parte dai pezzi già riposizionati sulla scacchiera, in partita **non serve** conservare in modo ordinato tutti e 30 i pezzi catturati: basta conoscere la posizione precisa **solo dei pezzi promuovibili del robot** (`1 Donna, 2 Torri, 2 Alfieri, 2 Cavalli` $\rightarrow$ **massimo 7 slot**!).

* **Piattino di scarto per l'umano (con marker ArUco dedicato, es. ID `6`):**
  * Quando l'umano cattura un pezzo del robot, lo poggia su un singolo piattino di scarto posizionato liberamente vicino alla scacchiera (localizzato dinamicamente dal suo marker ArUco, coerente col principio *fisicamente scollegato*).
  * Prima di eseguire la propria mossa, il robot (che sa già da `python-chess` che pezzo è stato catturato) preleva il pezzo dal piattino:
    * Se è un **pezzo promuovibile** (`Q, R, B, N`): lo sistema in uno dei **7 slot precisi** della propria *Riserva Promozioni*, tenendone traccia in memoria (così se dovrà promuovere, saprà esattamente dove pescarlo senza videocamera).
    * Se è un **pedone**: non essendo mai recuperabile per promozioni, il robot lo deposita/rilascia nella **zona di scarico libera** (o l'umano può direttamente metterlo da parte a mano per risparmiare un movimento al robot).
* **Pezzi dell'umano catturati dal robot:**
  * Dato che l'umano gestisce a mano le proprie eventuali promozioni, il robot può depositare/rilasciare i pezzi catturati dell'umano nella **zona di scarico libera** (es. vaschetta o fascia laterale oltre il cimitero ordinato, senza sprecare slot precisi nel workspace). *(Volendo, anche per i pezzi dell'umano si possono tenere ordinati o in scarico libero — la parte critica per la meccanica è che gli slot precisi obbligatori scendono da 30 a soli **7**!).*

#### B. Auto-Setup — Livello 2 (Riordino da Disordine su Scacchiera)
Funzione richiamabile a **fine partita** o dal **menu principale**:
1. Lo schermo chiede al giocatore: *"Posiziona tutti i 32 pezzi sulla scacchiera (anche in ordine casuale, uno per casella) e premi Conferma"*.
2. Il robot acquisisce la foto dall'ESP32-CAM e la **rete neurale** identifica tipo e colore di ogni pezzo sulle 64 caselle (sfruttando la stessa omografia $800 \times 800\text{ px}$ già calibrata, senza dover inquadrare i cimiteri).
3. Il software esegue un **controllo di coerenza** (verifica presenza di tutti i 32 pezzi corretti; se manca un pezzo o c'è un dubbio di riconoscimento, segnala la casella a schermo prima di muovere).
4. Il robot calcola la sequenza minima di spostamenti (usando una delle 32 caselle vuote come appoggio temporaneo per risolvere eventuali scambi/cicli) e dispone tutti i pezzi nella posizione iniziale regolamentare.

---

## 2. Funzionalità Extra e Roadmap *(confermato)*

| Funzionalità | Descrizione | Versione | Priorità |
| :--- | :--- | :--- | :--- |
| **Modalità Suggerimento (Hint)** | Richiamabile durante il turno umano (dal menu pausa o comando dedicato): Stockfish suggerisce la mossa migliore a schermo (es. `e2 → e4`) *(e opzionalmente il braccio può indicarla sopra le caselle)*. | **v1** | Alta |
| **Modalità Allenamento / Puzzle (FEN)** | Caricamento di posizioni FEN o puzzle (preset su robot oppure incollati dalla Web UI); lo schermo guida il posizionamento dei pezzi o il robot li dispone a partire dai pezzi sulla scacchiera. | **v1** | Alta |
| **Web UI Locale & Esportazione PGN** | Interfaccia web leggera via Wi-Fi (da telefono/PC) per: scaricare il **PGN** delle partite, vedere anteprima camera/ArUco in debug, caricare FEN/Puzzle e monitorare lo stato del robot. | **v1** | Alta |
| **Gioco Online (Lichess Board API)** | Collegamento a Lichess via Wi-Fi: giochi sulla scacchiera fisica contro avversari umani online e il braccio esegue in tempo reale le loro mosse (sfruttando le API ufficiali gratuite di Lichess). | **v2** | **Altissima** |
| **Modalità Vocale / Blindfold** | Sfruttando microfono e speaker integrati nel display ESP32-S3 4.0", possibilità di annunciare le mosse a voce e giocare persino *blindfold* (alla cieca). | **v2** | Media |
| **Bot vs Bot (Modalità Demo)** | Il robot gioca una partita contro sé stesso (ottimo per dimostrazioni o stress-test meccanici). | **v2** | Media |
| ~~Profilo Velocità Braccio~~ | *Scartata:* il braccio userà un unico profilo di velocità/accelerazione ben tarato (fluido e silenzioso con i TMC2209). | *Scartata* | — |

---

## 3. Interfaccia Utente Fisica (HMI: Console Orologio e Comandi) *(confermato)*

Estetica **pulita, minimale e curata**: niente LED RGB di stato né pulsanti superflui — tutta la comunicazione visiva passa da una UI grafica ben progettata sullo schermo.

### 3.1 Console / Orologio da Scacchi (Posizionata a Fianco della Scacchiera)
Un modulo compatto e minimalista stampato in PETG con forma da vero orologio da scacchi, posizionato comodamente accanto alla scacchiera:
* **Schermo & MCU All-in-One (unico controllo menu):** **diymore ESP32-S3 Display 4.0" IPS Capacitivo** ($320 \times 480$, laminazione OCA, touch `FT6336U`, Dual-Core 240 MHz, 16 MB Flash, Wi-Fi). Tutta la navigazione nei menu, la scelta della difficoltà/orologio, la pausa e le impostazioni avvengono direttamente tramite **touch capacitivo** (nessun encoder o pulsante aggiuntivo per contenere costi, ingombri e cablaggi).
* **Pulsante superiore "Fine Turno / Orologio":** grande pulsante singolo ergonomico sulla parte alta della console (guidato verticalmente con innesto a croce su **1 switch meccanico MX Keychron K10** snap-in) per confermare la mossa e commutare il tempo *(scartato il bilanciere a due lati perché il robot commuta il tempo via software senza toccare fisicamente l'orologio)*.
* **Audio integrato (Speaker + Microfono a bordo):** invece di un semplice buzzer, l'altoparlante integrato riproduce suoni puliti e discreti (tick di ripartenza turno umano al rientro in *Park Pose*, avvisi per scacco/errori/fine partita; il microfono abilita future funzioni vocali/blindfold in v2).
* **Connessione e Alimentazione *(confermato)*:** dati **wireless via Wi-Fi**; **alimentazione 5V via cavo USB-C sottile** dalla linea Buck 5V sulla base del robot (scartata batteria LiPo per costo, peso e sicurezza).

### 3.2 Comandi Fisici sul Robot
* **Arresto di Emergenza (E-Stop) fisico:** vero pulsante a fungo industriale NC montato sulla base del robot, cablato in hardware per interrompere immediatamente il movimento dei motori (`VMOT` o linea `EN` dei TMC2209) indipendentemente dal software.
* **Nessun LED RGB di stato** e nessun altro pulsante aggiuntivo sul corpo macchina.

---

## 4. Flusso Utente Tipico (User Journey)

```
[Accensione]
     │
     ▼
[Homing Automatico] (Endstop testa XY → Endstop Z in basso → Park Pose)
     │
     ▼
[Check Visione & Calibrazione]
  (Rileva ArUco 0-3 scacchiera + ArUco 4-5 base robot)
  ├─ OK ──────────────────────────────┐
  └─ Marker mancante → Avviso su      │
     schermo + retry fino a OK        │
                                      ▼
                             [MENU PRINCIPALE]
     ┌───────────────┬─────────────────┬─────────────────┬──────────────────┐
     ▼               ▼                 ▼                 ▼                  ▼
[Nuova Partita]  [Puzzle / FEN]  [Sistema Scacchiera]  [Calibrazione/Test] [Impostazioni]
     │               │                 │                 - Test Homing       - Volume audio
     ▼               ▼                 ▼                 - Test Pinza        - Info Wi-Fi / IP
1. Colore        Carica preset    1. Prompt: metti i 32  - Check ArUco         (link Web UI)
   (B / N / Caso) o FEN da Web UI    pezzi sulla board   - Jog manuale XY/Z
2. Difficoltà    → gioca puzzle   2. Rete neurale riconosce
3. Orologio                          tutti i pezzi (check 32)
4. Check pronta                   3. Riordino automatico
   → VIA!                            nelle case iniziali
     │
     ▼
[LOOP DI PARTITA]
  • Turno Umano: timer umano scorre → esegue mossa → preme Pulsante Orologio
    (Menu Pausa touch: Suggerimento/Hint · Proponi Patta · Abbandona)
  • Scansione: foto ESP32-CAM → Frame Differencing (+ Rete Neurale su promozioni)
    → validazione python-chess
     └─ Se mossa illegale: avviso + suono → correggi → ripremi Pulsante
  • Turno Robot: Stockfish calcola (timer robot attivo) → braccio esegue mossa
    (timer in pausa, Fair Clock; preleva eventuale pezzo dal Piattino ArUco ID 6)
    → torna in Park Pose → mini segnale audio + riparte timer umano
     │
     ▼
[FINE PARTITA]
  Schermata risultato (Matto / Stallo / Tempo / Abbandono)
  → Prompt immediato: "Sistemare la scacchiera ora?" [Sì] [No]
```

---

## 5. Impatto delle Feature su Meccanica, Elettronica e Software

Punti da tenere allineati con il progetto CAD/HW attuale:
1. **Cimitero compatto + Piattino di scarto (ArUco ID 6):** grazie all'Auto-Setup Livello 2 su scacchiera, servono **solo massimo 7 slot precisi** nel workspace SCARA ($X \approx \pm 170\text{ mm}$) per la *Riserva Promozioni* del robot (`Q, 2R, 2B, 2N`), più **1 piattino di scarto** (con marker ArUco ID `6` posizionato alla stessa quota/altezza nota della scacchiera e con offset centro-marker $\rightarrow$ punto di presa) e **1 punto/zona di scarico libera** per pedoni e pezzi non promuovibili. *Enorme risparmio di spazio nel workspace!*
2. **Altezza/Raggio di presa pezzi diversi:** la tabella delle quote $Z$ di presa per ogni tipo di pezzo (`P, N, B, R, Q, K`) è già prevista e servirà sia in gioco sia durante l'Auto-Setup.
3. **Park Pose fuori campo camera:** va definita una posizione di riposo in cui bracci e testa non coprono né la scacchiera né i marker ArUco (0–5).
4. **Orientamento scacchiera quando l'umano gioca Nero *(confermato)*:** la **scacchiera resta sempre ferma** (la scacchiera è simmetrica a $180^\circ$, la casa in basso a destra è sempre bianca). Il software ruota semplicemente di $180^\circ$ la mappatura logica ArUco $\rightarrow$ caselle (`a1 ↔ h8`), così i pezzi Neri vengono posizionati lato umano (anche automaticamente con l'Auto-Setup) e i Bianchi lato robot senza mai spostare la scacchiera.
5. **Architettura Elettronica Modulare a 3 Nodi ESP32 + PC Esterno (v1) *(confermato)*:**
   * **Cervello Centrale (v1):** **PC esterno** via Wi-Fi (esegue OpenCV, Rete Neurale, `python-chess`, Stockfish, Web UI e, in v2, Lichess API). *Evoluzione futura pianificata:* migrazione del cervello su **Arduino Uno Q** per rendere il tutto 100% standalone.
   * **Nodo 1 — `ESP32-CAM (OV5640)`:** montato in alto, fornisce scatti `/capture` ad alta risoluzione su richiesta HTTP.
   * **Nodo 2 — `ESP32 Motori`:** montato sulla base robot, controlla i 3 stepper (TMC2209), i 2 endstop (`HW_Endstop_Head` e `HW_Endstop_Body_Bottom`), il servo della pinza e la cinematica inversa / esecuzione traiettorie.
   * **Nodo 3 — `ESP32-S3 Console/Orologio`:** dentro il box orologio a lato scacchiera (alimentato 5V via cavo USB-C dalla base), integra display 4.0" IPS touch capacitivo, speaker/microfono e legge il pulsante singolo superiore di fine turno, comunicando via Wi-Fi con il cervello centrale.

---

## 6. Riepilogo Decisioni Consolidate (v1.0)

- [x] **Posizione HMI/Orologio:** Console modulare da fianco scacchiera (con grande pulsante singolo superiore per il tempo; dati Wi-Fi, alimentazione 5V via cavo USB-C dalla base); E-Stop fisico a fungo sul robot; nessun LED RGB né tasti extra.
- [x] **Tipo di schermo e controllo:** **diymore ESP32-S3 Display 4.0" IPS Capacitivo** ($320 \times 480$, speaker + microfono integrati) controllato interamente via **touch capacitivo** *(scartato encoder rotativo)* + **pulsante singolo superiore** per confermare la mossa/fermare il tempo *(scartato bilanciere a due lati perché il robot non tocca fisicamente l'orologio)*.
- [x] **Orologio durante il movimento del robot:** *Fair Clock* (il tempo scorre solo in calcolo; riparte all'umano a rientro in home/park con mini bip).
- [x] **Gioco con il Nero:** la scacchiera resta sempre ferma; il software ruota la mappatura logica di $180^\circ$ (`a1 ↔ h8`) e l'Auto-Setup dispone i Neri lato umano e i Bianchi lato robot.
- [x] **Cimitero & Auto-Setup:** Auto-Setup **Livello 2** (32 pezzi messi sulla scacchiera dall'umano $\rightarrow$ rete neurale li riconosce e li riordina); in partita **piattino di scarto con ArUco ID 6** + max **7 slot precisi** per pezzi promuovibili del robot + **zona scarico libera** per pedoni/pezzi dell'umano.
- [x] **Priorità feature extra:** **v1** = `Hint`, `Puzzle (FEN)`, `Web UI / PGN`; **v2** = `Lichess Online` *(priorità altissima)*, `Bot vs Bot`; **Scartate** = `Takeback`, `Profilo Velocità`.
- [x] **Architettura di calcolo e nodi:** **Opzione 1** — PC esterno via Wi-Fi come cervello centrale + **3 nodi ESP32 modulari** (`ESP32-CAM`, `ESP32 Motori`, `ESP32 Console/Orologio wireless`); migrazione futura su **Arduino Uno Q** quando si passerà al full standalone.
