# Lista Componenti (BOM) — ChessBot

> **Stato documento:** v1.1 — Allineata al CAD [ChessBot.blend](../ChessBot.blend) *(quantità viteria esatte da compilare più avanti)*  
> **Documenti collegati:** [riassunto_progetto_chessbot.md](./riassunto_progetto_chessbot.md) · [specifiche_funzionali_chessbot.md](./specifiche_funzionali_chessbot.md)  
> **Legenda stato:** `✅ Già disponibile / Stampato` · `🛒 Da acquistare` · `🔍 Da verificare se già presente` · `🖨️ Da stampare (PETG)`

---

## 1. Elettronica — Robot & Visione (Nodi 1 e 2)

| Stato | Componente | Q.tà | Note / Specifiche |
| :---: | :--- | :---: | :--- |
| ✅ | **ESP32-CAM + Sensore OV5640** | 1 | *Nodo 1 (Visione).* Montato su `Structure_CamHolder` in cima al profilo 2020; scatti UXGA via HTTP `/capture`. |
| ✅ | **ESP32** (scheda dev) | 1 | *Nodo 2 (Controller Motori).* Gestisce i 3 TMC2209, i 2 endstop, il servo pinza e la comunicazione Wi-Fi col PC. |
| ✅ | **Motori Stepper NEMA 17 (`17HS19`)** | 3 | 2 su `Body_Main` (assi XY) + 1 su `Structure_Top` (asse Z con ingranaggi 20T:60T). |
| ✅ | **Driver Stepper TMC2209 V2.0** | 3 | Silenziosi (StealthChop2) a 24V. Verificare presenza dissipatori. |
| ✅ | **Servo Miuzei 25 kg 270°** | 1 | Montato su `Head_ClawsStructure` per azionamento pinza a 6.0V. |
| ✅ | **Finecorsa (Endstop) meccanici** | 2 | `HW_Endstop_Head` (home XY sulla testa) + `HW_Endstop_Body_Bottom` (zero asse Z in basso per adattarsi a scacchiere di spessore diverso). |
| 🛒 | **Pulsante Arresto di Emergenza (E-Stop) a fungo** | 1 | Contatto NC industriale (es. Ø 22 mm, $\ge 5\text{A}$), montato sulla base robot per tagliare in hardware `VMOT` (24V) o `EN` dei TMC2209. |
| ✅ | **Alimentatore 24V DC** | 1 | Alimentazione principale motori. |
| ✅ | **Convertitori Buck DC-DC (`MP1584EN`)** | 2 | Già disponibili! 1 tarato a **6.0V** dedicato al Servo Miuzei 25 kg + 1 tarato a **5.0V** per ESP32 Motori, ESP32-CAM, Console Orologio 4.0" e Ventola 5V. *(Due separati per non superare ~1.5A continui per modulo ed evitare reset dell'ESP32 sugli spunti del servo).* |
| 🔍 | **Condensatori elettrolitici $100\,\mu\text{F}$ (50V) + $470\,\mu\text{F}$ (16V)** | 3 + 1 | 3× `100 µF` su `VMOT` dei TMC2209 + 1× `470 µF` su `6V_SERVO` per assorbire i picchi del servo 25 kg. |
| 🛒 | **PCB Principale (`Motherboard_chessbot`) via PCBWay** | 1 | Scheda 2 strati THT (KiCad 10.0) con socket femmina per ESP32 38 pin + 3× TMC2209 V2.0 + alloggi `MP1584EN` + portafusibile `5×20 mm` + morsetti. |
| 🛒 | **Cablaggio, morsetti, socket e minuteria PCB** | 1 set | Socket femmina `1×19` (×2) e `1×8` (×6), morsetti KF301 2 poli, JST-XH (4p/2p), portafusibile `5×20 mm` + fusibile 5A–10A, diodo `1N5819`, 3× resistenze `10 kΩ`, 1× `330 Ω`, 2× condensatori `100 nF`, cavi AWG 18–26. |
| 🛒 | **Interruttore principale ON/OFF (da pannello)** | 1 | Collegato al morsetto `MAIN_POWER_SW` sulla PCB (in serie ai 24V dopo il fusibile `F1`) per spegnere l'intero robot. |
| ✅ | **Ventola 5V di raffreddamento** | 1 | Già disponibile! Collegata al connettore `J17 (FAN_5V)` sulla PCB principale. |

---

## 2. Elettronica — Console Orologio (Nodo 3 — Dati Wi-Fi, Alimentazione via Cavo)

| Stato | Componente | Q.tà | Note / Specifiche |
| :---: | :--- | :---: | :--- |
| 🛒 | **diymore ESP32-S3 Display 4.0" IPS Capacitivo** | 1 | *Nodo 3 (HMI All-in-One).* 320×480 IPS OCA (350 nits), touch capacitivo `FT6336U`, Dual-Core 240 MHz, 16 MB Flash, Wi-Fi, **speaker e microfono integrati**. Gestisce tutta l'interfaccia via touch (nessun encoder o expander I²C necessario!). |
| ✅ | **Switch meccanico Keychron K10 (Cherry/Gateron MX)** | 1 | Già disponibile (ricambio tastiera Keychron K10). Montaggio *snap-in* (`14×14 mm`) nel corpo stampato per il grande pulsante singolo superiore (usa solo **1 GPIO** libero; nessuna molla o vite extra necessaria!). |
| 🛒 | **Cavo alimentazione 5V USB-C (base → console)** | 1 | Cavo sottile 5V/GND dalla linea Buck 5V della base fino alla porta USB-C del display *(scartata batteria LiPo per costo, peso e sicurezza)*. |

---

## 3. Meccanica — Telaio, Asse Z e Bracci SCARA (da `ChessBot.blend`)

| Stato | Componente | Q.tà | Note / Specifiche |
| :---: | :--- | :---: | :--- |
| ✅ | **Profili estrusi 2020 (400 mm)** | 4 | 3 verticali a triangolo per la torre Z (`Front`, `RearLeft`, `RearRight`) + 1 prolunga superiore (`CamTower`) per la telecamera. |
| ✅ | **Barre in alluminio e fibra di carbonio Ø 6 mm** | varie | Bracci doppi sovrapposti $L_1$/$L_2$, doppio parallelogramma passivo e perni giunti. |
| ✅ | **Cuscinetti `MR126ZZ` (6×12×4 mm)** | 40 | Cerniere bracci, testa, parallelogramma e **scorrimento lineare diretto di `Body_Main` sui 3 profili 2020** (`Body_Slide_Clamp`). |
| ✅ | **Vite trapezoidale T8 (350 mm) + Dado + 2 Cuscinetti orizzontali** | 1 set | `HW_Bearing_PillowBlock_Bottom/Top` + `HW_Leadscrew_Nut_T8`; azionata in alto tramite ingranaggi stampati 20T:60T (nessun giunto elastico necessario). |
| ✅ | **Cinghia GT2 (larghezza 6 mm)** | 1 rotolo | Trasmissione riduzione 16T:100T (1:6.25) sui due assi XY (`Body_Pulley_16T_MOD` $\rightarrow$ `Body_Pulley_100T`). |
| 🔍 | **Rondelle di spessoramento M6 (rasamenti)** | ~20–30 | Sottili (0.5–1 mm) se necessarie tra anello interno dei `MR126ZZ` e parti in PETG. |
| 🔍 | **Colla epossidica bicomponente (2K) / cianoacrilato** | 1 | Fissaggio tubi Ø 6 mm nei giunti stampati. |
| 🛒 | **Gommini antiscivolo adesivi** | 1 set | Sotto `Structure_Bottom`, sotto la console orologio e sotto il piattino di scarto. |

*(Nota: confermato dal CAD che **non servono** barre lisce Ø 8 mm, cuscinetti `LM8UU`, giunto elastico 5→8 mm, né squadrette standard se i profili sono vincolati direttamente da `Structure_Bottom` e `Structure_Top` con viti M4.)*

---

## 4. Viteria e Ferramenta *(quantità esatte da compilare più avanti)*

| Stato | Componente | Q.tà | Note / Specifiche |
| :---: | :--- | :---: | :--- |
| ✅ | **Viti e bulloni M2 / M3 / M4** | *TBD* | Già disponibili in assortimento; fissaggio diretto su PETG tramite foro stretto auto-maschiato a caldo con la vite stessa *(niente inserti in ottone salvo casi di smontaggio frequente)*. |
| 🔍 | **Dadi M2 / M3 / M4 (standard / Nyloc)** | *TBD* | Presenti nel CAD su copertura bracci, testa pinza (`HW_Nut_M2_Head_Rotator`) e clamp. |

---

## 5. Parti Stampate in 3D (PETG)

| Stato | Sottosistema / Parti | Note |
| :---: | :--- | :--- |
| ✅ | **Struttura Robot, Asse Z, Bracci e Pinza** | Già progettati in `ChessBot.blend`, stampati e testati meccanicamente (`Structure_Bottom/Top/CamHolder`, ingranaggi `gear20/gear60`, `Body_Main`, `Body_Slide_Clamp`, pulegge `16T/100T`, giunti bracci, parallelogramma, pinza `Head_Claw*`). |
| 🖨️ | **Vano Elettronica Base + Alloggio E-Stop** | Da modellare/stampare per alloggiare ordinatamente ESP32 Motori, 3× TMC2209, buck converter, connettore cavo 5V console e fungo E-Stop. |
| 🖨️ | **Console Orologio** | Case compatto e inclinato per **ESP32-S3 Display 4.0" IPS**, grande pulsante singolo superiore guidato verticalmente, griglia microfono/speaker e ingresso cavo USB-C 5V ([ChessBot_ClockConsole.blend](../ChessBot_ClockConsole.blend)). |
| 🖨️ | **Accessori Gioco** | Piattino di scarto (con sede piana per ArUco ID `6`), eventuale guida/vassoio per i **7 slot promozioni** + vaschetta scarico libero. |
| 🔍 | **Filamento PETG (1.75 mm)** | Quantità residua necessaria per console orologio, vano elettronica e accessori (~0.5–1 kg). |

---

## 6. Scacchiera, Pezzi e Visione Artificiale

| Stato | Componente | Q.tà | Note / Specifiche |
| :---: | :--- | :---: | :--- |
| ✅ | **Scacchiera in legno 300×300 mm** | 1 | Griglia 256×256 mm (caselle 32 mm), con **ArUco ID 0–3** già applicati agli angoli. |
| ✅ | **Set 32 pezzi scacchi in legno** | 1 | Altezza max (Re) 62 mm. |
| 🛒 | **Rondelle / piombini + feltrini adesivi** | 32 | Per appesantire la base dei 32 pezzi leggeri in legno. |
| 🖨️ | **Marker ArUco aggiuntivi (`DICT_4X4_50`)** | 3 | Stampa su carta opaca: **ID `4` e `5`** sulla base robot (stessa quota della scacchiera) + **ID `6`** sul piattino di scarto. |
