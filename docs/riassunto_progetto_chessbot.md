# Contesto Progetto: Braccio Robotico Scacchistico ("ChessBot")

> **Istruzioni per l'LLM:** Questo documento riassume le specifiche tecniche, le scelte progettuali e lo stato di avanzamento del mio braccio robotico stampato in 3D che gioca a scacchi contro un avversario umano. Usa queste informazioni come base di conoscenza per i prossimi passi senza proporre soluzioni già scartate.

---

## 1. Obiettivo e Filosofia del Progetto
* **Scopo:** Progettare da zero (CAD in **Blender**, stampa 3D in **PETG**) e costruire un braccio robotico che giochi a scacchi fisicamente contro un umano tramite Computer Vision e Stockfish.
* **Vincoli chiave:**
  * Sistema **standalone** sul tavolo (nessun cavo USB collegato al PC fisso; comunicazione via Wi-Fi o elaborazione locale).
  * **Facilmente replicabile e accessibile** economicamente (scartati driver industriali costosi come i DM542T).
  * Il robot e la scacchiera sono **fisicamente scollegati** tra loro (richiede calibrazione visiva dinamica).

---

## 2. Scacchiera e Pezzi di Riferimento
* **Scacchiera:** In legno/compensato da $300 \times 300\text{ mm}$ (scelta per l'ottimo contrasto opaco con la visione artificiale).
* **Area di gioco effettiva:** Griglia $8 \times 8$ da $256 \times 256\text{ mm}$, con singole caselle da $32 \times 32\text{ mm}$ e cornice esterna di $\sim 22\text{ mm}$ per lato.
* **Pezzi:** In legno leggero (da appesantire alla base con rondelle/piombini per aumentare la stabilità). Altezza massima (Re): $62\text{ mm}$.

---

## 3. Architettura Meccanica e CAD (Blender)
* **Configurazione:** **SCARA Parallelo a 5 barre (Pantografo / 5-Bar Linkage)**. I motori principali restano sul carrello base, riducendo l'inerzia e scaricando le forze su una struttura chiusa.
* **Quote Cinematiche (da centro-foro a centro-foro):**
  * **Interasse motori ($L_0$):** $100\text{ mm}$ (origine $(0,0)$ a metà tra i due perni).
  * **Bracci primari ($L_1$):** $165\text{ mm} - 180\text{ mm}$ (riduzione integrata tramite cinghia/puleggia GT2 o ingranaggi 1:4 per evitare direct-drive impreciso).
  * **Bracci secondari ($L_2$):** $230\text{ mm} - 240\text{ mm}$.
  * **Offset scacchiera ($Y_{\text{offset}}$):** Linea dei perni motore a $90\text{ mm}$ dall'inizio della traversa 1 ($\sim 68 - 70\text{ mm}$ dal bordo esterno in legno).
  * **Zona "Cimitero" (pezzi mangiati):** Esterna alla scacchiera, attorno a $X = \pm 170\text{ mm}$, $Y = 200 - 210\text{ mm}$.
* **Struttura dei Bracci e Giunti:**
  * Ogni braccio usa **2 tubi in carbonio (Decathlon, $\varnothing 6\text{ mm}$ o $8\text{ mm}$) sovrapposti verticalmente** (interasse verticale $30 - 35\text{ mm}$), incollati dentro cappucci/giunti in PETG (struttura *Sandwich Box / double-shear* con nervature interne o `BoxBrace` centrale su $L_1$ anti-torsione). Scartata la struttura a 3 tubi a triangolo.
  * Cerniere a incastro (forcella esterna + blocco centrale) con cuscinetti **MR126ZZ** (perni da $6\text{ mm}$) o **608ZZ** (bulloni M8), e scassi asimmetrici a **"Collo di Cigno" (a C)** per evitare collisioni agli angoli estremi (`a8`/`h8`, `a1`/`e1`).
* **Asse Verticale ($Z$):**
  * Carrello porta-motori XY scorrevole su due barre lisce (con cuscinetti `LM8UU`) e azionato da una **vite trapezia T8** (autobloccante).
  * Il motore stepper Z è montato **in cima alle colonne** (vite che lavora in trazione).
  * Corsa utile: $\sim 135\text{ mm}$ (scavalcamento totale Re su Re) oppure $\sim 75\text{ mm}$ (passaggio nei corridoi).
* **Orientamento Testa (Doppio Parallelogramma Passivo):**
  * Sistema ausiliario sul lato sinistro con tubi in carbonio, cappucci con cuscinetti e una **piastrina folle (`AUX_Elbow_IdlePlate_L`)** libera di ruotare sul perno del gomito sinistro per mantenere la testa sempre a $0^\circ$.
  * *Nota cinematica risolta:* L'offset a $180^\circ$ (sinistra) crea un punto morto su `d1`; studiate e simulate due alternative: offset a $270^\circ$ (indietro) oppure piastrina folle a "L" ($225^\circ / 135^\circ$).
* **Pinza (Gripper):**
  * Azionata da 1 servo **Miuzei $25\text{ kg}$ $270^\circ$** tramite manovella corta (raggio eccentrico $3.5\text{ mm}$) e 2 biellette su dita sottili a "L" (fulcri M3). Demoltiplica $90^\circ$ di rotazione del servo in un'apertura precisa di $6^\circ - 10^\circ$ per afferrare il colletto dei pezzi dentro caselle da $32\text{ mm}$.
* **Nomenclatura CAD (Blender):** `[Sottosistema]_[Posizione]_[Componente]_[Lato]` (es. `Z_Base_Carriage_SYM`, `L1_Base_PulleyFork_L`, `L1_Mid_BoxBrace_SYM`, `AUX_Elbow_IdlePlate_L`, `HEAD_Main_Body`).

---

## 4. Elettronica, Motori e Stato del Cablaggio
* **Motori:**
  * 3x Stepper **NEMA 17 (`17HS19`)** lunghi $48\text{ mm}$ ($\sim 1.7\text{A} - 2.0\text{A}$) per i due assi XY e l'asse Z.
  * 1x Servo **$25\text{ kg}$ $270^\circ$** (Miuzei) per la pinza.
* **Alimentazione:**
  * Alimentatore principale da **$24\text{V}$** attualmente in uso (con massa comune / *Common Ground* unita all'Arduino/ESP32 e condensatore da $100\,\mu\text{F}$ almeno $35\text{V}$ su `VMOT`).
  * Convertitori Buck DC-DC (es. XL4015) per portare la tensione a $6.0\text{V}$ (servo) e $5\text{V}$ (logica).
* **Driver Stepper (Stato Attuale):**
  * I miei vecchi **TMC2208 V3.0** sono stati testati a banco e sono risultati **tutti guasti** (trimmer rotti o $V_{\text{ref}}$ bloccata a max $0.3\text{V}$).
  * Ho dei **DM542T**, ma li ho esclusi per ingombro e costo ($\sim 60\text{€}$ cad., scarsa replicabilità).
  * **Attualmente in uso per i test:** **A4988** con resistenze di sense `R100` ($0.10\,\Omega$), tarati a $V_{\text{ref}} = 0.80\text{V}$ ($I_{\max} = 1.0\text{A}$). Funzionano a $24\text{V}$, ma sono **estremamente rumorosi** (soprattutto sull'asse Z per risonanza del telaio).
  * **Upgrade deciso:** Acquistare un kit di **BIGTREETECH TMC2209 V1.3** ($\sim 4 - 5\text{€}$ cad., silenziosissimi con StealthChop2, $2.0\text{A}$ RMS, perfetti a $24\text{V}$, plug-and-play invertendo il verso rispetto agli A4988).
* **Homing e Finecorsa:**
  * **Asse Z:** Endstop meccanico posizionato in alto ($Z_{\max}$) per azzerare senza mai urtare i pezzi (scartati sensori IR/ultrasuoni sulla testa per scarsa precisione e interferenze).
  * **Assi XY:** 2 endstop sulla base fissa attivati dai bracci $L_1$ in apertura esterna con procedura software sincronizzata (apertura simultanea dei due motori per evitare collisioni o sovraestensioni).
* **Controllore e Architettura di Calcolo:**
  * Attualmente uso microcontrollori Arduino/ESP32 per il controllo motori e una **ESP32-CAM con sensore OV5640** via Wi-Fi per le immagini (calcoli su PC fisso).
  * Valutata anche la scheda all-in-one **Arduino Uno Q ($4\text{ GB}$ RAM)** (CPU Linux Qualcomm + MCU real-time STM32U585) come eventuale evoluzione standalone.

---

## 5. Visione Artificiale (CV) e Software
* **Acquisizione Immagini:** ESP32-CAM (OV5640) interrogata via HTTP su `/capture` ad alta risoluzione (UXGA $1600 \times 1200$ JPEG alta qualità), non serve streaming continuo a 60 FPS.
* **Marker ArUco sulla Scacchiera (Già stampati e incollati):**
  * Dizionario `DICT_4X4_50`, ID `0, 1, 2, 3` (dimensione $15 \times 15\text{ mm}$ con bordino bianco di $2\text{ mm}$), posizionati in senso orario agli angoli `a8` (0), `h8` (1), `h1` (2), `a1` (3), tutti orientati dritti nello stesso verso.
* **Omografia e Ritaglio (Script OpenCV pronto/in test):**
  * `cv2.getPerspectiveTransform` + `cv2.warpPerspective` (con compensazione dell'offset di $2\text{ mm}$ del bordino bianco) per ottenere un'immagine piatta $800 \times 800\text{ px}$ ($100 \times 100\text{ px}$ per casella).
  * Analisi limitata alla ROI centrale $60 \times 60\text{ px}$ per ignorare la parallasse delle teste dei pezzi alti ($62\text{ mm}$).
* **Calibrazione Dinamica Robot-Scacchiera (Pianificata):**
  * Poiché il robot è scollegato dalla scacchiera, posizionerò **2 marker ArUco (ID 4 e ID 5)** sulla base del robot, **alla stessa identica altezza della superficie della scacchiera** (zero parallasse) e distanti $100 - 150\text{ mm}$ tra loro, per calcolare dinamicamente origine $(O_{rx}, O_{ry})$ e rotazione $\theta_r$ del robot rispetto alla scacchiera prima di ogni mossa.
* **Pipeline Logica di Gioco:**
  1. **Rilevamento mossa (v1 - Frame Differencing):** Confronto `cv2.absdiff` tra foto prima e dopo la mossa sulle 64 ROI centrali $\rightarrow$ individuazione caselle variate (2 per mossa/cattura, 3 en passant, 4 arrocco) $\rightarrow$ stringa UCI (es. `e2e4`).
  2. **Validazione:** Libreria `python-chess` (`board.legal_moves`) come "macchina della verità" per bloccare falsi positivi da ombre/riflessi.
  3. **Motore Scacchistico:** Chiamata a **Stockfish** via `chess.engine` (protocollo UCI).
  4. **Traduzione Fisica:** Verifica `board.is_capture()` (per generare la doppia sequenza con deposito nel "Cimitero") e `board.piece_at()` (per regolare la quota $Z$ di presa in base all'altezza del pezzo).
  5. **Sviluppo futuro (v2 - Reti Neurali):** Interesse a sperimentare una CNN leggera (es. MobileNetV3 sui 64 ritagli con dataset auto-etichettato) o YOLOv8n/v11n per il riconoscimento diretto dei pezzi.

---

## 6. Stato Attuale e Prossimi Passi (To-Do)
* **Completato / In corso:**
  * Progettazione CAD della meccanica SCARA a 5 barre e nomenclatura pezzi.
  * Test a banco dei 3 stepper NEMA 17 (`17HS19`) a $24\text{V}$ con driver temporanei A4988 (`R100`, $V_{\text{ref}} = 0.80\text{V}$).
  * Stampa e applicazione dei 4 marker ArUco sulla scacchiera e primi script Python/OpenCV per acquisizione da ESP32 (OV5640) e raddrizzamento omografico.
* **Da fare prossimamente:**
  * Sostituire i driver A4988 con i **TMC2209** per eliminare il rumore.
  * Implementare l'homing sincronizzato XY + $Z_{\max}$ e la cinematica inversa sul firmware.
  * Aggiungere i 2 marker ArUco (ID 4 e 5) alla base del robot per la trasformazione di coordinate scacchiera $\rightarrow$ robot.
  * Completare lo script Python end-to-end (Frame Differencing $\rightarrow$ `python-chess` $\rightarrow$ Stockfish $\rightarrow$ invio coordinate al robot) e successivamente sperimentare la versione con rete neurale.