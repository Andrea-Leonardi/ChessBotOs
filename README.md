# ChessBotOs

Sistema di visione, controllo e motore scacchistico per un robot giocatore di scacchi fisico.

---

## Struttura del progetto

```text
ChessBotOs/
├── .gitignore
├── README.md
└── test/
    ├── ArUco/                  # Rilevamento scacchiera con marker ArUco e creazione dataset
    │   ├── MarkerMaker.py          # Genera i 4 marker ArUco (ID 0..3) pronti per la stampa A4
    │   ├── MakerIdentification.py  # Raddrizza la scacchiera in 800x800 con griglia di verifica
    │   ├── DatasetCollector.py     # Acquisisce da camera e salva le 64 celle (100x100) in datasets/
    │   ├── DatasetLabeler.py       # Interfaccia rapida per etichettare le celle (bianco / nero / vuota)
    │   └── stampa_A4_markers_15mm.png
    ├── esp32_cam_stream/       # Firmware ESP32-S3 (Goouuu N16R8 + OV5640) per streaming web
    │   ├── esp32_cam_stream.ino
    │   ├── board_config.h
    │   ├── camera_index.h
    │   ├── camera_pins.h
    │   ├── app_httpd.cpp
    │   └── credentials.example.h   # Template credenziali Wi-Fi (copiare in credentials.h)
    ├── pinzaInput/             # Test movimento servo/pinza su Arduino
    └── stockfish/              # Test integrazione motore Stockfish
```

---

## 1. Telecamera ESP32-S3 (`test/esp32_cam_stream`)

Firmware per **Goouuu ESP32-S3-N16R8** con sensore **OV5640**:
- **Wi-Fi**: copia `credentials.example.h` in `credentials.h` (ignorato da Git) e inserisci SSID e password. Se lasciato vuoto o non raggiungibile, avvia automaticamente l'hotspot `ESP32S3-CAM` (password `12345678`, IP `http://192.168.4.1`).
- **Risoluzioni quadrate (1:1)**: nel menu a tendina *Resolution* sono disponibili `1500x1500 (Square)`, `1024x1024 (Square)` e `800x800 (Square)` con crop hardware centrato.
- **Salvataggio a piena risoluzione**: il pulsante *Save* salva l'immagine alla risoluzione reale del sensore (`naturalWidth` x `naturalHeight`).
- **Autofocus OV5640**: integra il driver `ESP32_OV5640_AF` (richiede la libreria *OV5640 Auto Focus for ESP32 Camera* e un modulo con motorino VCM alimentato).

---

## 2. Rilevamento Scacchiera & Creazione Dataset (`test/ArUco`)

Ambiente Python consigliato (`conda activate chess_bot` con `opencv-python` e `numpy`):

1. **Verifica allineamento**:
   ```powershell
   python test/ArUco/MakerIdentification.py
   ```
2. **Raccolta immagini delle celle (`SPAZIO` per scattare, `Q` per uscire)**:
   ```powershell
   python test/ArUco/DatasetCollector.py
   ```
   Salva ogni scatto nella cartella `datasets/scatto_XXXX/` (ignorata da Git) suddiviso in 64 immagini `100x100` px (`a8`..`h1`) più `scatto_XXXX_full.png`.
3. **Etichettatura rapida delle celle**:
   ```powershell
   python test/ArUco/DatasetLabeler.py
   ```
   Tasti: **`B`** = Bianco, **`N`** = Nero, **`V`** = Vuota, **`Z`** = Indietro, **`S`** = Salta, **`Q`** = Esci.
   Salva in tempo reale in `datasets/labels.csv` (`rel_path,label`) e riprende automaticamente dall'ultima cella non etichettata.

---

## Note su file esclusi da Git (`.gitignore`)

- `credentials.h` (credenziali Wi-Fi personali)
- `datasets/` / `dataset/` (immagini acquisite e file `labels.csv`)
- `stockfish-windows-x86-64-universal/` (eseguibile Stockfish locale > 100 MB)
