# ChessBotOs

Sistema di visione, controllo e motore scacchistico per un robot giocatore di scacchi fisico.

---

## Struttura del progetto

```text
ChessBotOs/
├── .gitignore
├── README.md
└── test/
    ├── aruco_markers/          # Marker ArUco e calibrazione prospettica della scacchiera
    │   ├── MarkerMaker.py          # Genera i 4 marker ArUco (ID 0..3) pronti per la stampa A4
    │   ├── MakerIdentification.py  # Raddrizza la scacchiera in 800x800 con griglia di verifica
    │   └── stampa_A4_markers_15mm.png
    ├── dataset_tools/          # Acquisizione, etichettatura e controllo qualità del dataset
    │   ├── DatasetCollector.py     # Acquisisce da camera e salva le 64 celle (100x100) in datasets/
    │   ├── DatasetLabeler.py       # Etichettatura rapida 3 classi (bianco / nero / vuota)
    │   ├── PieceLabeler.py         # Etichettatura del tipo di pezzo sulle celle non vuote (13 classi)
    │   ├── SmartPieceCollector.py  # Scatto + auto-classificazione celle vuote + etichettatura pezzi
    │   ├── TargetedPieceCollector.py # Acquisizione mirata per singolo pezzo (scarta celle vuote)
    │   └── ReviewLabels.py         # Revisione rapida di celle mancanti, sbilanciate o sospette
    ├── resnet18/               # Modelli ResNet-18 (CUDA): training, inferenza live e visualizzazioni
    │   ├── train_resnet18.py       # Training 3 classi (bianco / nero / vuota)
    │   ├── train_resnet18_pieces.py# Training 13 classi (6 pezzi x 2 colori + vuota)
    │   ├── infer_live.py           # Inferenza live da webcam (3 classi)
    │   ├── infer_live_pieces.py    # Inferenza live da webcam (13 classi)
    │   ├── visualize_resnet_layers.py # Genera mappe di attivazione dei layer e CAM
    │   ├── models/                 # Pesi salvati (best_resnet18.pth, best_resnet18_pieces.pth)
    │   └── visualizations/         # Immagini statiche delle attivazioni per livello
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

## 2. Marker ArUco & Dataset (`test/aruco_markers`, `test/dataset_tools`)

Ambiente Python consigliato (`conda activate chess_bot` con `opencv-python`, `numpy`, `torch`, `torchvision`, `pillow`):

1. **Verifica allineamento**:
   ```powershell
   python test/aruco_markers/MakerIdentification.py
   ```
2. **Raccolta immagini delle celle (`SPAZIO` per scattare, `Q` per uscire)**:
   ```powershell
   python test/dataset_tools/DatasetCollector.py
   ```
   Salva ogni scatto in `datasets/scatto_XXXX/` (ignorata da Git) suddiviso in 64 immagini `100x100` px (`a8`..`h1`) più `scatto_XXXX_full.png`.
3. **Etichettatura**:
   - **3 classi** (`B` Bianco, `N` Nero, `V` Vuota -> `datasets/labels.csv`):
     ```powershell
     python test/dataset_tools/DatasetLabeler.py
     ```
   - **13 classi** (`T/C/A/D/R/P` sulle celle non vuote -> `datasets/labels_pieces.csv`):
     ```powershell
     python test/dataset_tools/PieceLabeler.py
     ```
4. **Raccolta assistita e mirata**:
   - `SmartPieceCollector.py`: usa il modello a 3 classi per auto-salvare le celle vuote e chiedere solo i pezzi rilevati.
   - `TargetedPieceCollector.py`: imposta un pezzo target all'avvio, scarta le celle vuote e salva solo le celle con il pezzo.
   - `ReviewLabels.py`: isola celle mancanti, scatti sbilanciati o disaccordi col modello per correzioni rapide.

---

## 3. Riconoscimento Pezzi con ResNet-18 (`test/resnet18`)

- **Addestramento su CUDA**:
  ```powershell
  python test/resnet18/train_resnet18.py
  python test/resnet18/train_resnet18_pieces.py
  ```
- **Inferenza live da webcam**:
  ```powershell
  python test/resnet18/infer_live.py
  python test/resnet18/infer_live_pieces.py
  ```
- **Visualizzazione dei layer CNN**:
  ```powershell
  python test/resnet18/visualize_resnet_layers.py
  ```
  Genera immagini statiche in `test/resnet18/visualizations/` con le mappe di attivazione dai primi filtri (`Conv1`) fino alla Class Activation Map finale (`Layer4` / *Dove guarda*).

---

## Note su file esclusi da Git (`.gitignore`)

- `credentials.h` (credenziali Wi-Fi personali)
- `datasets/` / `dataset/` (immagini acquisite e file CSV delle etichette)
- `stockfish-windows-x86-64-universal/` (eseguibile Stockfish locale > 100 MB)
