import csv
import os
import time
import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
MODEL_3CLS_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "resnet18", "models", "best_resnet18.pth"))
LABELS_3CLS_CSV = os.path.join(DATASET_DIR, "labels.csv")
LABELS_13CLS_CSV = os.path.join(DATASET_DIR, "labels_pieces.csv")

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, cv2.aruco.DetectorParameters())

LATO_GRIGLIA_MM = 256.0
LATO_IMG_PX = 800
CELL_SIZE = LATO_IMG_PX // 8
OFFSET_MM = 2.0

px_per_mm = LATO_IMG_PX / LATO_GRIGLIA_MM
off_px = OFFSET_MM * px_per_mm

PUNTI_DESTINAZIONE = np.array([
    [-off_px, -off_px],
    [LATO_IMG_PX + off_px, -off_px],
    [LATO_IMG_PX + off_px, LATO_IMG_PX + off_px],
    [-off_px, LATO_IMG_PX + off_px],
], dtype="float32")

COLONNE = "abcdefgh"
TRAVERSE = "87654321"

KEY_TO_PIECE = {
    ord("t"): "torre",
    ord("T"): "torre",
    ord("c"): "cavallo",
    ord("C"): "cavallo",
    ord("a"): "alfiere",
    ord("A"): "alfiere",
    ord("d"): "donna",
    ord("D"): "donna",
    ord("r"): "re",
    ord("R"): "re",
    ord("p"): "pedone",
    ord("P"): "pedone",
}


def load_csv_map(csv_path: str) -> dict[str, str]:
    data: dict[str, str] = {}
    if not os.path.exists(csv_path):
        return data
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rel = row.get("rel_path", "").strip()
            lbl = row.get("label", "").strip()
            if rel and lbl:
                data[rel] = lbl
    return data


def save_csv_map(csv_path: str, data: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rel_path", "label"])
        for rel_path in sorted(data.keys()):
            writer.writerow([rel_path, data[rel_path]])


def next_capture_index(dataset_dir: str) -> int:
    if not os.path.exists(dataset_dir):
        return 1
    existing = [
        d for d in os.listdir(dataset_dir)
        if d.startswith("scatto_") and os.path.isdir(os.path.join(dataset_dir, d))
    ]
    nums = []
    for name in existing:
        try:
            nums.append(int(name.split("_")[1]))
        except (IndexError, ValueError):
            pass
    return (max(nums) + 1) if nums else 1


def load_3class_model(model_path: str, device: torch.device) -> tuple[nn.Module, list[str]]:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modello 3 classi non trovato: {model_path}")
    ckpt = torch.load(model_path, map_location=device, weights_only=True)
    classes = ckpt["classes"]
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()
    return model, classes


def classify_cells_3cls(
    board_bgr: np.ndarray,
    model: nn.Module,
    classes: list[str],
    tf: transforms.Compose,
    device: torch.device,
) -> list[str]:
    batch_tensors = []
    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            cell_bgr = board_bgr[y1:y1 + CELL_SIZE, x1:x1 + CELL_SIZE]
            cell_rgb = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2RGB)
            batch_tensors.append(tf(Image.fromarray(cell_rgb)))
    batch = torch.stack(batch_tensors).to(device, non_blocking=True)
    with torch.no_grad():
        preds = model(batch).argmax(dim=1)
    return [classes[p.item()] for p in preds]


def save_board_cells(board_bgr: np.ndarray, dataset_dir: str, capture_idx: int) -> list[tuple[str, np.ndarray]]:
    capture_name = f"scatto_{capture_idx:04d}"
    capture_dir = os.path.join(dataset_dir, capture_name)
    os.makedirs(capture_dir, exist_ok=True)
    cv2.imwrite(os.path.join(capture_dir, f"{capture_name}_full.png"), board_bgr)

    saved: list[tuple[str, np.ndarray]] = []
    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            cell_img = board_bgr[y1:y1 + CELL_SIZE, x1:x1 + CELL_SIZE]
            square_name = f"{COLONNE[c]}{TRAVERSE[r]}"
            fname = f"{capture_name}_{square_name}.png"
            full_path = os.path.join(capture_dir, fname)
            cv2.imwrite(full_path, cell_img)
            rel_path = f"{capture_name}/{fname}"
            saved.append((rel_path, cell_img))
    return saved


def label_non_empty_cells(
    non_empty: list[tuple[str, np.ndarray, str]],
    labels_3cls: dict[str, str],
    labels_13cls: dict[str, str],
) -> None:
    """Mostra una finestra rapida per etichettare solo le celle rilevate come non vuote."""
    win_name = "Etichetta Celle Rilevate"
    display_size = 380
    banner_h = 120
    idx = 0

    while 0 <= idx < len(non_empty):
        rel_path, img, pred_color = non_empty[idx]
        zoomed = cv2.resize(img, (display_size, display_size), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((display_size + banner_h, display_size, 3), dtype=np.uint8)
        canvas[:display_size, :] = zoomed
        cv2.rectangle(canvas, (0, display_size), (display_size, display_size + banner_h), (30, 30, 30), -1)

        cv2.putText(canvas, f"[{idx + 1}/{len(non_empty)}] {rel_path}", (10, display_size + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        col_bgr = (255, 220, 0) if pred_color == "bianco" else (0, 140, 255)
        cv2.putText(canvas, f"Rilevato: {pred_color.upper()}", (10, display_size + 46),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, col_bgr, 1, cv2.LINE_AA)

        cv2.putText(canvas, "T:Torre C:Cavallo A:Alfiere", (10, display_size + 72),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (210, 210, 210), 1, cv2.LINE_AA)
        cv2.putText(canvas, "D:Donna R:Re P:Pedone | V:Vuota", (10, display_size + 92),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (210, 210, 210), 1, cv2.LINE_AA)
        cv2.putText(canvas, "Z:Indietro | B/N:Cambia Colore | Q:Fine", (10, display_size + 112),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (150, 150, 150), 1, cv2.LINE_AA)

        cv2.imshow(win_name, canvas)
        key = cv2.waitKey(0) & 0xFF

        if key in KEY_TO_PIECE:
            piece = KEY_TO_PIECE[key]
            labels_3cls[rel_path] = pred_color
            labels_13cls[rel_path] = f"{pred_color}_{piece}"
            save_csv_map(LABELS_3CLS_CSV, labels_3cls)
            save_csv_map(LABELS_13CLS_CSV, labels_13cls)
            print(f"  -> {rel_path}: {pred_color}_{piece}")
            idx += 1
        elif key in (ord("v"), ord("V")):
            labels_3cls[rel_path] = "vuota"
            labels_13cls[rel_path] = "vuota"
            save_csv_map(LABELS_3CLS_CSV, labels_3cls)
            save_csv_map(LABELS_13CLS_CSV, labels_13cls)
            print(f"  -> {rel_path}: vuota (corretto)")
            idx += 1
        elif key in (ord("b"), ord("B")):
            non_empty[idx] = (rel_path, img, "bianco")
        elif key in (ord("n"), ord("N")):
            non_empty[idx] = (rel_path, img, "nero")
        elif key in (ord("z"), ord("Z"), 8):
            if idx > 0:
                idx -= 1
        elif key in (ord("q"), ord("Q"), 27):
            break

    cv2.destroyWindow(win_name)


def draw_live_overlay(board_bgr: np.ndarray, preds: list[str], status_msg: str) -> np.ndarray:
    vis = board_bgr.copy()
    for idx, lbl in enumerate(preds):
        r, c = divmod(idx, 8)
        x1, y1 = c * CELL_SIZE, r * CELL_SIZE
        x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
        if lbl == "bianco":
            color = (255, 220, 0)
        elif lbl == "nero":
            color = (0, 140, 255)
        else:
            color = (0, 180, 0)
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2 if lbl != "vuota" else 1)

    if status_msg:
        cv2.rectangle(vis, (0, 0), (540, 30), (15, 15, 15), -1)
        cv2.putText(vis, status_msg, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 180), 1, cv2.LINE_AA)
    return vis


def main() -> None:
    os.makedirs(DATASET_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"SmartPieceCollector su {device}")

    model_3cls, classes_3cls = load_3class_model(MODEL_3CLS_PATH, device)
    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    labels_3cls = load_csv_map(LABELS_3CLS_CSV)
    labels_13cls = load_csv_map(LABELS_13CLS_CSV)
    capture_idx = next_capture_index(DATASET_DIR)

    cap = cv2.VideoCapture(0)  # Cambia 0 con 1 o con l'URL IP se usi una camera esterna
    if not cap.isOpened():
        print("Errore: impossibile aprire la telecamera!")
        return

    print("Comandi:")
    print("  [SPAZIO] -> Scatta, auto-classifica le vuote ed etichetta solo i pezzi rilevati")
    print("  [Q]      -> Esci")

    status_msg = "SPAZIO: Scatta & Etichetta | Q: Esci"
    status_until = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        corners, ids, _ = DETECTOR.detectMarkers(frame)
        board_clean = None
        preds_3cls = None

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            marker_map = {id_val: corner[0] for corner, id_val in zip(corners, ids.flatten())}

            if all(k in marker_map for k in (0, 1, 2, 3)):
                punti_sorgente = np.array([
                    marker_map[0][2],
                    marker_map[1][3],
                    marker_map[2][0],
                    marker_map[3][1],
                ], dtype="float32")

                M = cv2.getPerspectiveTransform(punti_sorgente, PUNTI_DESTINAZIONE)
                board_clean = cv2.warpPerspective(frame, M, (LATO_IMG_PX, LATO_IMG_PX))
                preds_3cls = classify_cells_3cls(board_clean, model_3cls, classes_3cls, tf, device)

                n_pieces = sum(1 for p in preds_3cls if p != "vuota")
                msg = status_msg if time.time() < status_until else f"Pezzi rilevati: {n_pieces} | SPAZIO: Scatta"
                vis = draw_live_overlay(board_clean, preds_3cls, msg)
                cv2.imshow("SmartPieceCollector - Scacchiera", vis)

        cv2.imshow("Telecamera Originale", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(" "):
            if board_clean is not None and preds_3cls is not None:
                saved_cells = save_board_cells(board_clean, DATASET_DIR, capture_idx)
                non_empty = []
                auto_empty = 0

                for (rel_path, cell_img), pred_lbl in zip(saved_cells, preds_3cls):
                    if pred_lbl == "vuota":
                        labels_3cls[rel_path] = "vuota"
                        labels_13cls[rel_path] = "vuota"
                        auto_empty += 1
                    else:
                        non_empty.append((rel_path, cell_img, pred_lbl))

                save_csv_map(LABELS_3CLS_CSV, labels_3cls)
                save_csv_map(LABELS_13CLS_CSV, labels_13cls)
                print(f"[scatto_{capture_idx:04d}] Vuote auto: {auto_empty} | Da etichettare: {len(non_empty)}")

                if non_empty:
                    label_non_empty_cells(non_empty, labels_3cls, labels_13cls)

                status_msg = f"Salvato scatto_{capture_idx:04d} ({len(non_empty)} pezzi)"
                status_until = time.time() + 2.5
                capture_idx += 1
            else:
                status_msg = "Marker 0,1,2,3 non tutti visibili!"
                status_until = time.time() + 2.0
        elif key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
