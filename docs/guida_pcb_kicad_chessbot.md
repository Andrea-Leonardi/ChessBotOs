# Guida Progettazione PCB Principale (KiCad → PCBWay) — ChessBot

> **Scheda:** `ChessBot_MainBoard_v1` (2 strati, FR-4, 1.6 mm, target $\le 100 \times 100\text{ mm}$)  
> **Hardware di riferimento:** ESP32 DevKit **38 pin** (interasse file `25.40 mm`), **3× TMC2209 V2.0** (modalità standalone con jumper `MS1/MS2`), 2 Endstop, 1 Servo Miuzei 25 kg (`6.0V`), E-Stop fisico NC, 2 Buck esterni (`5V` e `6V`).  
> **Componenti:** 100% **Through-Hole (THT)** + socket femmina per ESP32 e TMC2209 (facilissima da saldare come prima PCB!).

---

## 1. Schema a Blocchi dell'Alimentazione (Sicuro e Pulito)

```
 [Alimentatore 24V] ──► (J1: 24V_IN / GND)
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   (J2: E-Stop NC)     (J3: Buck 6V IN)    (J4: Buck 5V IN)
   [in serie a 24V]          │                   │
         │             [Buck XL4015 6V]    [Buck XL4015 5V]
         ▼                   │                   │
    [VMOT_24V]         (J5: 6V_SERVO)      (J6: 5V_LOGIC)
         │                   │                   │
   ┌─────┼─────┐             ▼                   ├────────────────┬─────────────────┐
   ▼     ▼     ▼      (J_SERVO pin +)            ▼                ▼                 ▼
 TMC_X TMC_Y TMC_Z    (Servo 25 kg)       [Diodo 1N5819]    (J_CAM_5V)      (J_CLOCK_5V)
 (+ 3x 100µF ≥35V)                               │         (ESP32-CAM)     (Console 4.0")
                                                 ▼
                                          ESP32 (pin 5V/VIN)
                                                 │
                                          ESP32 (pin 3V3) ──► VIO dei 3 TMC2209 + Pull-Up
```

**Perché questo schema è a prova di errore:**
* Premendo il fungo **E-Stop NC**, si interrompe fisicamente `VMOT_24V` ai 3 motori (arresto immediato garantito), mentre **ESP32, ESP32-CAM e Console restano accesi** così lo schermo può avvisarti dell'emergenza.
* Il **diodo Schottky `1N5819`** verso il pin `5V/VIN` dell'ESP32 impedisce corti/ritorni di corrente quando colleghi il cavo USB al PC per caricare il firmware.
* Tutti i `GND` (24V, 6V, 5V, ESP32, TMC2209) sono uniti in un unico **piano di massa comune (`GND`)** sulla faccia inferiore (`B.Cu`).

---

## 2. Mappa Pinout ESP32 38-Pin (100% Sicura al Boot)

Scelta evitando tutti i pin rischiosi dell'ESP32 (`GPIO 6–11` flash interna, `GPIO 0/2/12/15` strapping di boot, `GPIO 1/3` seriale USB).

| Funzione | Net Label in KiCad | Pin ESP32 (38 pin) | Note |
| :--- | :--- | :---: | :--- |
| **Motore Sinistro (`L1_L`) — STEP** | `X_STEP` | **`GPIO 25`** | Output sicuro |
| **Motore Sinistro (`L1_L`) — DIR** | `X_DIR` | **`GPIO 26`** | Output sicuro |
| **Motore Destro (`L1_R`) — STEP** | `Y_STEP` | **`GPIO 27`** | Output sicuro |
| **Motore Destro (`L1_R`) — DIR** | `Y_DIR` | **`GPIO 14`** | Output sicuro |
| **Motore Asse Z — STEP** | `Z_STEP` | **`GPIO 32`** | Output sicuro |
| **Motore Asse Z — DIR** | `Z_DIR` | **`GPIO 33`** | Output sicuro |
| **Enable Comune (tutti i 3 TMC)** | `MOTORS_EN` | **`GPIO 13`** | Con resistenza pull-up `10 kΩ` a `3V3` (motori spenti al boot!) |
| **Servo Pinza (Miuzei 25 kg)** | `SERVO_PWM` | **`GPIO 18`** | Con resistenza serie `330 Ω` di protezione |
| **Endstop Testa XY (`HW_Endstop_Head`)** | `END_XY` | **`GPIO 34`** | Input-only: **richiede pull-up `10 kΩ` a `3V3` + `100 nF` a `GND`** |
| **Endstop Z Basso (`HW_Endstop_Body_Bottom`)** | `END_Z` | **`GPIO 35`** | Input-only: **richiede pull-up `10 kΩ` a `3V3` + `100 nF` a `GND`** |
| **Alimentazione ESP32** | `ESP_5V` | **`5V` / `VIN`** | Dopo il diodo `1N5819` da `5V_LOGIC` |
| **Logica 3.3V** | `3V3` | **`3V3`** | Alimenta `VIO` dei 3 TMC2209, i jumper `MS1/MS2` e i pull-up |
| **Massa** | `GND` | **tutti i pin `GND`** | Collegati al piano di massa `GND` |

*(Rimangono liberi `GPIO 16, 17, 19, 21, 22, 23` — puoi mettere un piccolo header femmina/maschio "EXPANSION" se un domani vuoi collegarci altro!)*

---

## 3. Collegamenti Dettagliati Blocco per Blocco

### A. I 3 Driver `TMC2209 V2.0` (Ripeti identico per `X`, `Y`, `Z`)

> **⚠️ Controllo obbligatorio prima di saldare:** guarda la serigrafia stampata sotto i tuoi `TMC2209 V2.0` fisici e verifica che l'ordine dei 16 pin corrisponda a questo standard StepStick!

```text
   Lato Logica (Socket A, 1×8)           Lato Potenza (Socket B, 1×8)
   [1] EN   ◄── MOTORS_EN (+ 10k a 3V3)  [16] VMOT ◄── VMOT_24V (+ 100µF a GND!)
   [2] MS1  ◄── Jumper JP_MS1 verso 3V3  [15] GND  ◄── GND
   [3] MS2  ◄── Jumper JP_MS2 verso 3V3  [14] 2B   ──► Connettore Motore pin 4
   [4] NC/PDN   (lascia scollegato)      [13] 2A   ──► Connettore Motore pin 3
   [5] NC/CLK   (lascia scollegato)      [12] 1A   ──► Connettore Motore pin 2
   [6] NC/DIAG  (lascia scollegato)      [11] 1B   ──► Connettore Motore pin 1
   [7] STEP ◄── X_STEP / Y_STEP / Z_STEP [10] VIO  ◄── 3V3 (NON 5V!)
   [8] DIR  ◄── X_DIR  / Y_DIR  / Z_DIR  [ 9] GND  ◄── GND
```

* **Jumper Microstepping (`MS1` / `MS2`) per ciascun driver:** metti un pin header `2×2` (due coppie di pin):
  * Coppia 1: `MS1` $\leftrightarrow$ `3V3`
  * Coppia 2: `MS2` $\leftrightarrow$ `3V3`
  * Tabella microstep TMC2209 Standalone:
    * Nessun jumper = **1/8**
    * Solo `MS1` = **1/32**
    * Solo `MS2` = **1/64**
    * **Entrambi (`MS1` + `MS2`) = 1/16** *(consigliato per iniziare!)*
* **Condensatore `100 µF` ($\ge 35\text{V}$, meglio `50V`):** 1 per ogni driver, piazzato il più vicino possibile a `VMOT` (`+`) e `GND` (`-`).

### B. I 2 Endstop (`J_END_XY` e `J_END_Z`, connettori 2 pin)
Per ciascun endstop (`END_XY` su `GPIO 34` e `END_Z` su `GPIO 35`):
* Pin 1 connettore $\rightarrow$ `GND`
* Pin 2 connettore $\rightarrow$ `END_XY` (o `END_Z`)
* Collegare una resistenza **`10 kΩ`** tra `END_XY` e `3V3` (pull-up obbligatorio su GPIO 34/35).
* Collegare un condensatore ceramico **`100 nF`** tra `END_XY` e `GND` (filtra i disturbi elettromagnetici dei motori ed elimina falsi trigger!).

### C. Connettore Servo Pinza (`J_SERVO`, pin header maschio `1×3` passo 2.54 mm)
Ordine standard cavi servo (marrone/nero – rosso – arancione/giallo):
* Pin 1: `GND`
* Pin 2: `6V_SERVO` (dal Buck #1 a `6.0V` — **pista larga `2.0 mm`!**)
* Pin 3: `SERVO_PWM` (passando attraverso una resistenza serie da **`330 Ω`** da `GPIO 18`)
* *(Consigliato)* aggiungi un condensatore **`470 µF` (16V)** tra `6V_SERVO` e `GND` vicino al connettore servo per assorbire i picchi di spunto del 25 kg!

---

## 4. Lista Componenti & Footprint Già Inclusi in KiCad (Zero Librerie Esterne!)

Puoi costruire l'intera scheda usando solo simboli e footprint nativi di **KiCad 8/9**:

| Rif. | Componente | Q.tà | Footprint KiCad (nativo) | Note di Posizionamento |
| :--- | :--- | :---: | :--- | :--- |
| `U1A`, `U1B` | **Socket ESP32 38 pin** | 2 | `Connector_PinSocket_2.54mm:PinSocket_1x19_P2.54mm_Vertical` | Posiziona le 2 file parallele a esattamente **`25.40 mm`** centro-centro! |
| `D1–D3` | **Socket TMC2209 V2.0** (2 file ciascuno) | 6 | `Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical` | Per ogni driver, 2 file parallele a esattamente **`12.70 mm`** centro-centro! |
| `JP1–JP3` | **Header Jumper `MS1/MS2`** | 3 | `Connector_PinHeader_2.54mm:PinHeader_2x02_P2.54mm_Vertical` | Vicino al lato logica di ogni TMC2209 |
| `J_M1–J_M3` | **Connettori Motori NEMA 17** | 3 | `Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical` *(oppure `PinHeader_1x04_P2.54mm`)* | Vicino ai pin `1B, 1A, 2A, 2B` di ogni TMC2209 |
| `J1–J8` | **Morsetti a vite 2 poli (KF301)** | 8 | `TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal` | `24V_IN`, `E-Stop`, `Buck6V IN/OUT`, `Buck5V IN/OUT`, `ESP32-CAM 5V`, `Console 5V` |
| `J_END1–2` | **Connettori 2 pin Endstop** | 2 | `Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical` | Lato ESP32 |
| `J_SERVO` | **Connettore 3 pin Servo** | 1 | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical` | Vicino a `6V_SERVO` |
| `C1–C3` | **Condensatori `100 µF` 50V** | 3 | `Capacitor_THT:CP_Radial_D8.0mm_P3.50mm` | Attaccati a `VMOT`/`GND` di ogni TMC2209 |
| `C4` | **Condensatore `470 µF` 16V** | 1 | `Capacitor_THT:CP_Radial_D8.0mm_P3.50mm` | Vicino a `J_SERVO` (`6V_SERVO`/`GND`) |
| `C5–C6` | **Condensatori ceramici `100 nF`** | 2 | `Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm` | Filtro su `END_XY` e `END_Z` |
| `R1–R3` | **Resistenze `10 kΩ` (1/4W)** | 3 | `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal` | Pull-up su `MOTORS_EN`, `END_XY`, `END_Z` |
| `R4` | **Resistenza `330 Ω` (1/4W)** | 1 | `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal` | In serie a `SERVO_PWM` |
| `D_USB` | **Diodo Schottky `1N5819`** | 1 | `Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal` | Protezione su `5V_LOGIC` → `ESP_5V` (fascia catodo lato ESP32!) |
| `H1–H4` | **Fori fissaggio M3 agli angoli** | 4 | `MountingHole:MountingHole_3.2mm_M3` | A `5 mm` dai 4 bordi della PCB |

---

## 5. Passo-Passo in KiCad fino all'Ordine su PCBWay

### Fase 1 — Schema Elettrico (`Schematic Editor`)
1. Crea un nuovo progetto KiCad (`File → New Project`, chiamalo `ChessBot_MainBoard`).
2. Apri lo **Schematic Editor**, premi `A` per aggiungere i simboli (`Conn_01x19` ×2 per ESP32, `Conn_01x08` ×6 per i 3 TMC, `Screw_Terminal_01x02` ×8, `C_Polarized`, `C`, `R`, `D_Schottky`, `MountingHole`).
3. Collega i pin usando **`L` (Net Label)** con i nomi esatti delle tabelle sopra (`VMOT_24V`, `X_STEP`, `GND`, `3V3`, ecc.) — lo schema resta ordinatissimo!
4. Assegna i footprint dalla tabella §4 (`Tools → Assign Footprints`) e controlla con **ERC** (icona coccinella in alto) che non ci siano errori.

### Fase 2 — Layout PCB (`PCB Editor`)
1. Apri il **PCB Editor** e premi **`F8`** (*Update PCB from Schematic*) per importare tutti i componenti.
2. **Disegna il bordo scheda:** seleziona il layer **`Edge.Cuts`** e disegna un rettangolo (es. **`95 × 85 mm`** — resta sotto `100 × 100 mm` per pagare solo 5 $ su PCBWay!).
3. **Posiziona i componenti con logica:**
   * Metti i **2 socket dell'ESP32** (`U1A` e `U1B`) con la porta USB dell'ESP32 rivolta verso un bordo esterno (così ci arrivi col cavo USB per programmarlo!). Verifica con lo strumento righello (`Ctrl+Shift+M`) che tra i centri delle due file ci siano **esattamente `25.40 mm`**.
   * Metti i **3 TMC2209** affiancati lungo la parte alta/destra con le loro due file a **esattamente `12.70 mm`** centro-centro, i **condensatori `100 µF`** subito dietro `VMOT`/`GND` e i **connettori motore** subito accanto a `1B/1A/2A/2B`.
   * Scrivi sul layer **`F.Silkscreen`** (testo `T`) delle etichette chiarissime vicino a ogni morsetto (`+24V`, `GND`, `ESTOP`, `X_MOT`, `Y_MOT`, `Z_MOT`, `EN` / `VMOT` sui socket dei driver!) — ti salverà da errori di inserimento al rovescio!
4. **Configura le larghezze piste (`File → Board Setup → Net Classes`):**
   * Classe `Power` (`24V_IN`, `VMOT_24V`, `6V_SERVO`, `5V_LOGIC`, `GND`, tracce motore `1A/1B/2A/2B`): larghezza **`2.0 mm`** (o `1.5 mm` sui pin stretti dei TMC, allargando subito a `2.0 mm`).
   * Classe `Default` (tutti i segnali logici): larghezza **`0.35 mm`**, clearance **`0.25 mm`**.
5. **Sbroglia le piste (`X`)** usando **`F.Cu` (rosso, sopra)** per piste orizzontali e **`B.Cu` (blu, sotto)** per piste verticali (premi `V` per cambiare layer con un via).
6. **Piano di massa `GND`:** aggiungi una **Filled Zone (`Ctrl+Shift+Z`)** su **`B.Cu`** assegnata alla net **`GND`** che copre tutta la scheda, poi premi **`B`** per riempirla. Tutti i pad `GND` si collegheranno da soli!
7. **Verifica finale:**
   * Esegui il **DRC** (icona coccinella): devi arrivare a **0 errori** e **0 pin non connessi (unrouted)**.
   * **Stampa su carta A4 in scala 1:1 (`File → Print`, scala `1.00`)** e appoggiaci sopra fisicamente il tuo ESP32 38 pin e un TMC2209 V2.0 per confermare al 100% gli interassi (`25.40 mm` e `12.70 mm`)!

### Fase 3 — Export Gerber e Ordine su PCBWay
1. In KiCad PCB Editor: **`File → Fabrication Outputs → Gerbers (.gbr)...`**
   * Seleziona i layer: `F.Cu`, `B.Cu`, `F.Silkscreen`, `B.Silkscreen`, `F.Mask`, `B.Mask`, `Edge.Cuts`.
   * Spunta *Use Protel filename extensions* (opzionale, PCBWay legge bene tutto) $\rightarrow$ clicca **Plot**.
   * Subito sotto clicca **Generate Drill Files...** (formato Excellon, mm) $\rightarrow$ **Generate Drill File**.
2. Comprimi tutti i file generati nella cartella di output in un unico file **`.zip`**.
3. Su **PCBWay.com** $\rightarrow$ *Quote Now* $\rightarrow$ carica lo **`.zip`**:
   * Impostazioni standard già perfette: `2 Layers`, `FR-4`, spessore `1.6 mm`, `1 oz Cu`, colore Solder Mask a scelta (es. **Nero opaco** o **Verde** — il nero opaco con serigrafia bianca fa un figurone!).
   * Controlla l'anteprima nel **Gerber Viewer** di PCBWay prima di pagare.

---

> **Consiglio utile:** se vuoi, una volta fatto lo schema o il layout in KiCad, puoi salvarmi il file `.kicad_sch` / `.kicad_pcb` dentro `ChessBotOs` e posso farti io una **revisione automatica di tutte le connessioni, netlist e pin** prima che tu ordini su PCBWay!
