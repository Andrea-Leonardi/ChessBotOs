# ChessBotOs

Computer vision, hardware control, and chess engine system for a physical chess-playing robot.

---

## Project Structure

```text
ChessBotOs/
├── .gitignore
├── README.md
└── test/
    ├── aruco_markers/          # ArUco markers and perspective calibration of the chessboard
    │   ├── MarkerMaker.py          # Generates the 4 ArUco markers (ID 0..3) ready for A4 printing
    │   ├── MakerIdentification.py  # Warps the chessboard to 800x800 with a verification grid
    │   └── stampa_A4_markers_15mm.png
    ├── dataset_tools/          # Dataset acquisition, labeling, and quality review tools
    │   ├── DatasetCollector.py     # Captures from camera and saves the 64 cells (100x100) to datasets/
    │   ├── DatasetLabeler.py       # Fast 3-class labeling UI (white / black / empty)
    │   ├── PieceLabeler.py         # Piece-type labeling on non-empty cells (13 classes)
    │   ├── SmartPieceCollector.py  # Capture + auto-classify empty cells + label detected pieces
    │   ├── TargetedPieceCollector.py # Targeted single-piece capture (discards empty cells)
    │   └── ReviewLabels.py         # Quick review of missing, imbalanced, or suspect cells
    ├── resnet18/               # ResNet-18 models (CUDA): training, live inference, and visualizations
    │   ├── train_resnet18.py       # 3-class training (white / black / empty)
    │   ├── train_resnet18_pieces.py# 13-class training (6 pieces x 2 colors + empty)
    │   ├── infer_live.py           # Live webcam inference (3 classes)
    │   ├── infer_live_pieces.py    # Live webcam inference (13 classes)
    │   ├── visualize_resnet_layers.py # Generates layer activation maps and CAMs
    │   ├── models/                 # Saved weights (best_resnet18.pth, best_resnet18_pieces.pth)
    │   └── visualizations/         # Static activation images per layer
    ├── esp32_cam_stream/       # ESP32-S3 firmware (Goouuu N16R8 + OV5640) for web streaming
    │   ├── esp32_cam_stream.ino
    │   ├── board_config.h
    │   ├── camera_index.h
    │   ├── camera_pins.h
    │   ├── app_httpd.cpp
    │   └── credentials.example.h   # Wi-Fi credentials template (copy to credentials.h)
    ├── pinzaInput/             # Arduino gripper/servo movement test
    └── stockfish/              # Stockfish engine integration test
```

---

## 1. ESP32-S3 Camera (`test/esp32_cam_stream`)

Firmware for **Goouuu ESP32-S3-N16R8** with **OV5640** sensor:
- **Wi-Fi**: copy `credentials.example.h` to `credentials.h` (ignored by Git) and enter your SSID and password. If left empty or unreachable, it automatically starts the `ESP32S3-CAM` hotspot (password `12345678`, IP `http://192.168.4.1`).
- **Square resolutions (1:1)**: the *Resolution* dropdown provides `1500x1500 (Square)`, `1024x1024 (Square)`, and `800x800 (Square)` with centered hardware crop.
- **Full-resolution capture**: the *Save* button saves the image at the sensor's actual resolution (`naturalWidth` x `naturalHeight`).
- **OV5640 Autofocus**: integrates the `ESP32_OV5640_AF` driver (requires the *OV5640 Auto Focus for ESP32 Camera* library and a module with a powered VCM motor).

---

## 2. ArUco Markers & Dataset (`test/aruco_markers`, `test/dataset_tools`)

Recommended Python environment (`conda activate chess_bot` with `opencv-python`, `numpy`, `torch`, `torchvision`, `pillow`):

1. **Alignment check**:
   ```powershell
   python test/aruco_markers/MakerIdentification.py
   ```
2. **Capture board cell images (`SPACE` to capture, `Q` to quit)**:
   ```powershell
   python test/dataset_tools/DatasetCollector.py
   ```
   Saves each capture in `datasets/scatto_XXXX/` (ignored by Git) split into 64 `100x100` px images (`a8`..`h1`) plus `scatto_XXXX_full.png`.
3. **Labeling**:
   - **3 classes** (`B` White, `N` Black, `V` Empty -> `datasets/labels.csv`):
     ```powershell
     python test/dataset_tools/DatasetLabeler.py
     ```
   - **13 classes** (`T/C/A/D/R/P` on non-empty cells -> `datasets/labels_pieces.csv`):
     ```powershell
     python test/dataset_tools/PieceLabeler.py
     ```
4. **Assisted and targeted collection**:
   - `SmartPieceCollector.py`: uses the 3-class model to auto-save empty cells and prompt only for detected pieces.
   - `TargetedPieceCollector.py`: sets a target piece at startup, discards empty cells, and saves only cells containing the piece.
   - `ReviewLabels.py`: isolates missing cells, imbalanced shots, or model disagreements for fast corrections.

---

## 3. Piece Recognition with ResNet-18 (`test/resnet18`)

- **Training on CUDA**:
  ```powershell
  python test/resnet18/train_resnet18.py
  python test/resnet18/train_resnet18_pieces.py
  ```
- **Live webcam inference**:
  ```powershell
  python test/resnet18/infer_live.py
  python test/resnet18/infer_live_pieces.py
  ```
- **CNN layer visualization**:
  ```powershell
  python test/resnet18/visualize_resnet_layers.py
  ```
  Generates static images in `test/resnet18/visualizations/` showing activation maps from early filters (`Conv1`) to the final Class Activation Map (`Layer4` / *Where it looks*).

---

## Files Excluded from Git (`.gitignore`)

- `credentials.h` (personal Wi-Fi credentials)
- `datasets/` / `dataset/` (captured images and label CSV files)
- `stockfish-windows-x86-64-universal/` (local Stockfish executable > 100 MB)
